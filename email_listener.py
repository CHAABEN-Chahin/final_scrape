import argparse
import email
import imaplib
import os
import time
from email.message import Message

from parser import WorkflowEmailParseError, parse_email_message
from scraper_pipeline import execute_workflow


def connect_imap(host: str, port: int, username: str, password: str) -> imaplib.IMAP4_SSL:
    client = imaplib.IMAP4_SSL(host, port)
    client.login(username, password)
    return client


def fetch_unseen_ids(client: imaplib.IMAP4_SSL, folder: str) -> list[bytes]:
    status, _ = client.select(folder)
    if status != "OK":
        raise RuntimeError(f"Unable to select mailbox folder: {folder}")

    status, data = client.search(None, "UNSEEN")
    if status != "OK" or not data:
        return []

    ids = data[0].split()
    return ids


def fetch_message(client: imaplib.IMAP4_SSL, message_id: bytes) -> Message:
    status, data = client.fetch(message_id, "(RFC822)")
    if status != "OK" or not data or data[0] is None:
        raise RuntimeError(f"Failed to fetch message id: {message_id!r}")

    raw_email = data[0][1]
    return email.message_from_bytes(raw_email)


def process_unseen_messages(
    client: imaplib.IMAP4_SSL,
    folder: str,
    output_dir: str,
) -> None:
    ids = fetch_unseen_ids(client, folder)
    if not ids:
        print("No new emails.")
        return

    print(f"Found {len(ids)} new email(s).")
    for message_id in ids:
        try:
            message = fetch_message(client, message_id)
            parsed = parse_email_message(message)

            print(
                "Processing email:",
                f"project={parsed['project_name']}, url={parsed['url']}",
            )

            result = execute_workflow(
                project_name=parsed["project_name"],
                source_url=parsed["url"],
                output_dir=output_dir,
            )
            print(f"Workflow complete. Output file: {result['output_file']}")

        except WorkflowEmailParseError as exc:
            print(f"Skipping email {message_id.decode(errors='ignore')}: {exc}")
        except Exception as exc:
            print(f"Error while processing email {message_id.decode(errors='ignore')}: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor an inbox and trigger scraping workflow from incoming emails."
    )
    parser.add_argument("--host", default=os.getenv("EMAIL_HOST", "imap.gmail.com"))
    parser.add_argument("--port", type=int, default=int(os.getenv("EMAIL_PORT", "993")))
    parser.add_argument("--username", default=os.getenv("EMAIL_USER", ""))
    parser.add_argument("--password", default=os.getenv("EMAIL_PASS", ""))
    parser.add_argument("--folder", default=os.getenv("EMAIL_FOLDER", "INBOX"))
    parser.add_argument("--poll-interval", type=int, default=30)
    parser.add_argument("--output-dir", default="workflow_output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.username or not args.password:
        raise SystemExit("EMAIL_USER and EMAIL_PASS (or --username/--password) are required.")

    print("Connecting to IMAP server...")
    client = connect_imap(args.host, args.port, args.username, args.password)
    print("Connected. Listening for new emails...")

    try:
        while True:
            process_unseen_messages(
                client=client,
                folder=args.folder,
                output_dir=args.output_dir,
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
