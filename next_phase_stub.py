import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

PROCESSED_QUEUE_DIR = Path("workflow_queue") / "processed"
NEXTPHASE_PENDING_DIR = Path("next_phase_queue") / "pending"
NEXTPHASE_DISPATCHED_DIR = Path("next_phase_queue") / "dispatched"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ensure_dirs() -> None:
    NEXTPHASE_PENDING_DIR.mkdir(parents=True, exist_ok=True)
    NEXTPHASE_DISPATCHED_DIR.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _fallback_from_workflow_output(workflow_output_file: str) -> dict:
    if not workflow_output_file:
        return {}

    path = Path(workflow_output_file)
    if not path.exists() or not path.is_file():
        return {}

    try:
        workflow = load_json(path)
    except Exception:
        return {}

    ai = workflow.get("ai_preparation", {})
    llm = ai.get("llm", {}) if isinstance(ai, dict) else {}
    structured = llm.get("structured", {}) if isinstance(llm, dict) else {}
    info = structured.get("important_info", {}) if isinstance(structured, dict) else {}

    return {
        "conclusion_two_sentences": str(structured.get("summary_two_sentences", "")).strip(),
        "price": str(info.get("prize_or_budget", "")).strip(),
        "deadline": str(info.get("deadline", "")).strip(),
        "domain": str(info.get("domain", "")).strip(),
    }


def dispatch_ready_items(limit: int) -> int:
    ensure_dirs()
    processed_jobs = sorted(PROCESSED_QUEUE_DIR.glob("*.json"))
    dispatched_count = 0

    for job_file in processed_jobs:
        if dispatched_count >= limit:
            break

        job_data = load_json(job_file)
        final_decision = job_data.get("final_decision", {})
        next_phase_payload = job_data.get("next_phase_payload")
        workflow_output_file = str(job_data.get("workflow_output_file", ""))

        if not final_decision.get("next_phase_ready"):
            continue
        if not isinstance(next_phase_payload, dict):
            continue

        fallback = _fallback_from_workflow_output(workflow_output_file)
        conclusion_two_sentences = str(next_phase_payload.get("conclusion_two_sentences", "")).strip() or fallback.get(
            "conclusion_two_sentences", ""
        )
        price = str(next_phase_payload.get("price", "")).strip() or fallback.get("price", "")
        deadline = str(next_phase_payload.get("deadline", "")).strip() or fallback.get("deadline", "")
        domain = str(next_phase_payload.get("domain", "")).strip() or fallback.get("domain", "")

        next_phase_item = {
            "created_at_utc": utc_stamp(),
            "source_job_file": str(job_file),
            "message_id": job_data.get("message_id", ""),
            "platform": next_phase_payload.get("platform", job_data.get("platform", "")),
            "category": next_phase_payload.get("category", next_phase_payload.get("platform", job_data.get("platform", ""))),
            "project_name": next_phase_payload.get("project_name", ""),
            "source_url": next_phase_payload.get("source_url", ""),
            "conclusion_two_sentences": conclusion_two_sentences,
            "price": price,
            "deadline": deadline,
            "domain": domain,
            "workflow_output_file": workflow_output_file,
            "final_decision": final_decision,
        }

        target_name = f"{utc_stamp()}_{job_file.stem}.json"
        pending_target = NEXTPHASE_PENDING_DIR / target_name
        save_json(pending_target, next_phase_item)

        dispatched_target = NEXTPHASE_DISPATCHED_DIR / job_file.name
        job_file.rename(dispatched_target)

        dispatched_count += 1
        print(f"Dispatched to next phase queue: {pending_target.name}")

    return dispatched_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect validated jobs and place them in next phase pending queue."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of jobs to dispatch in this run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = dispatch_ready_items(limit=args.limit)
    print(f"Total dispatched: {count}")


if __name__ == "__main__":
    main()
