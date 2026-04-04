import argparse
import email
import imaplib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path

from env_loader import load_env
from parser import WorkflowEmailParseError, parse_email_message
from scraper_pipeline import execute_workflow

load_env()

QUEUE_ROOT = Path("workflow_queue")
PENDING_DIR = QUEUE_ROOT / "pending"
PROCESSED_DIR = QUEUE_ROOT / "processed"
FAILED_DIR = QUEUE_ROOT / "failed"


def ensure_queue_dirs() -> None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_id(raw: bytes) -> str:
    return raw.decode(errors="ignore").strip() or "unknown"


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _move_with_metadata(job_file: Path, destination_dir: Path, metadata: dict) -> Path:
    with job_file.open("r", encoding="utf-8") as f:
        job = json.load(f)
    job.update(metadata)

    target = destination_dir / job_file.name
    _save_json(target, job)
    job_file.unlink(missing_ok=True)
    return target


def connect_imap(host: str, port: int, username: str, password: str) -> imaplib.IMAP4_SSL:
    client = imaplib.IMAP4_SSL(host, port)
    client.login(username, password)
    return client


def fetch_unseen_ids(
    client: imaplib.IMAP4_SSL,
    folder: str,
    allowed_prefixes: list[str],
    max_age_days: int,
) -> list[bytes]:
    status, _ = client.select(folder)
    if status != "OK":
        raise RuntimeError(f"Unable to select mailbox folder: {folder}")

    since_date = (datetime.now(timezone.utc) - timedelta(days=max(1, max_age_days))).strftime("%d-%b-%Y")
    matched_ids: set[bytes] = set()
    for prefix in allowed_prefixes:
        status, data = client.search(None, "UNSEEN", "SINCE", since_date, "SUBJECT", f'"{prefix}"')
        if status != "OK" or not data:
            continue
        matched_ids.update(data[0].split())

    return sorted(matched_ids)


def fetch_message(client: imaplib.IMAP4_SSL, message_id: bytes) -> Message:
    status, data = client.fetch(message_id, "(RFC822)")
    if status != "OK" or not data or data[0] is None:
        raise RuntimeError(f"Failed to fetch message id: {message_id!r}")

    raw_email = data[0][1]
    return email.message_from_bytes(raw_email)


def mark_as_seen(client: imaplib.IMAP4_SSL, message_id: bytes) -> None:
    client.store(message_id, "+FLAGS", "\\Seen")


def enqueue_email_job(message_id: bytes, parsed: dict) -> Path:
    message_id_text = _safe_id(message_id)
    job_name = f"{utc_stamp()}_{message_id_text}.json"
    job_path = PENDING_DIR / job_name
    payload = {
        "queued_at_utc": utc_stamp(),
        "message_id": message_id_text,
        "platform": parsed["platform"],
        "project_name": parsed["project_name"],
        "url": parsed["url"],
        "email_subject": parsed.get("subject", ""),
        "email_from": parsed.get("from", ""),
    }
    _save_json(job_path, payload)
    return job_path


def ingest_unseen_into_queue(
    client: imaplib.IMAP4_SSL,
    folder: str,
    allowed_prefixes: list[str],
    max_age_days: int,
) -> None:
    ids = fetch_unseen_ids(client, folder, allowed_prefixes, max_age_days)
    if not ids:
        print(
            f"No new emails within last {max_age_days} day(s) "
            f"for prefixes {allowed_prefixes}."
        )
        return

    print(f"Found {len(ids)} matching recent unread email(s).")
    for message_id in ids:
        try:
            message = fetch_message(client, message_id)
            parsed = parse_email_message(message)
            job_path = enqueue_email_job(message_id, parsed)
            mark_as_seen(client, message_id)
            print(f"Queued: {job_path.name}")
        except WorkflowEmailParseError as exc:
            mark_as_seen(client, message_id)
            print(f"Ignored email {_safe_id(message_id)}: {exc}")
        except Exception as exc:
            print(f"Failed to ingest email {_safe_id(message_id)}: {exc}")


def process_waiting_list(output_dir: str) -> None:
    pending_jobs = sorted(PENDING_DIR.glob("*.json"))
    if not pending_jobs:
        return

    print(f"Processing waiting list: {len(pending_jobs)} job(s).")
    for job_file in pending_jobs:
        try:
            with job_file.open("r", encoding="utf-8") as f:
                job = json.load(f)

            platform = job.get("platform", "facebook")
            project_name = job["project_name"]
            url = job["url"]
            print(f"Running job: {job_file.name} | platform={platform} | project={project_name}")

            result = execute_workflow(
                platform=platform,
                project_name=project_name,
                source_url=url,
                output_dir=output_dir,
            )

            target = _move_with_metadata(
                job_file,
                PROCESSED_DIR,
                {
                    "processed_at_utc": utc_stamp(),
                    "status": "processed",
                    "platform": platform,
                    "workflow_output_file": result.get("output_file", ""),
                    "final_decision": result.get("ai_preparation", {}).get("final_decision", {}),
                    "next_phase_payload": result.get("ai_preparation", {}).get("next_phase_payload"),
                },
            )
            print(f"Processed: {target.name}")
        except Exception as exc:
            target = _move_with_metadata(
                job_file,
                FAILED_DIR,
                {
                    "failed_at_utc": utc_stamp(),
                    "status": "failed",
                    "stage": "workflow_execution",
                    "error": str(exc),
                    "manual_review_required": True,
                },
            )
            print(f"Moved to failed queue for manual review: {target.name}")


def process_unseen_messages(
    client: imaplib.IMAP4_SSL,
    folder: str,
    output_dir: str,
    allowed_prefixes: list[str],
    max_age_days: int,
) -> None:
    ingest_unseen_into_queue(client, folder, allowed_prefixes, max_age_days)
    process_waiting_list(output_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor an inbox and trigger scraping workflow from incoming emails."
    )
    parser.add_argument("--host", default=os.getenv("EMAIL_HOST", "imap.gmail.com"))
    parser.add_argument("--port", type=int, default=int(os.getenv("EMAIL_PORT", "993")))
    parser.add_argument("--username", default=os.getenv("EMAIL_USER", ""))
    parser.add_argument("--password", default=os.getenv("EMAIL_PASS", ""))
    parser.add_argument("--folder", default=os.getenv("EMAIL_FOLDER", "INBOX"))
    parser.add_argument(
        "--subject-prefixes",
        default=os.getenv(
            "EMAIL_SUBJECT_PREFIXES",
            os.getenv("EMAIL_SUBJECT_PREFIX", "facebook -,linkedin -"),
        ),
        help="Comma-separated subject prefixes to accept.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=int(os.getenv("EMAIL_MAX_AGE_DAYS", "7")),
    )
    parser.add_argument("--poll-interval", type=int, default=30)
    parser.add_argument("--output-dir", default="workflow_output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.username or not args.password:
        raise SystemExit("EMAIL_USER and EMAIL_PASS (or --username/--password) are required.")

    prefixes = [p.strip().lower() for p in args.subject_prefixes.split(",") if p.strip()]

    print("Connecting to IMAP server...")
    client = connect_imap(args.host, args.port, args.username, args.password)
    ensure_queue_dirs()
    print("Connected. Listening for new emails...")

    try:
        while True:
            process_unseen_messages(
                client=client,
                folder=args.folder,
                output_dir=args.output_dir,
                allowed_prefixes=prefixes,
                max_age_days=args.max_age_days,
            )
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        print("Stopped by user.")
    finally:
        try:
            client.close()
        except Exception:
            pass
        client.logout()


if __name__ == "__main__":
    main()
