import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from ai_pipeline import run_ai_preparation
from filter import filter_scraped_markdown
from run_with_retries import OUTPUT_FILE, run_with_retries


def slugify(name: str) -> str:
    safe = [ch.lower() if ch.isalnum() else "_" for ch in name.strip()]
    collapsed = "".join(safe)
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed.strip("_") or "project"


def run_scraper_with_retry(url: str) -> str:
    success = asyncio.run(run_with_retries(url))
    if not success:
        raise RuntimeError("Scraping failed after max retries.")

    if not OUTPUT_FILE.exists():
        raise RuntimeError("Expected scrape output file was not generated.")

    markdown = OUTPUT_FILE.read_text(encoding="utf-8")
    if not markdown.strip():
        raise RuntimeError("Scrape output is empty after reported success.")

    return markdown


def execute_workflow(project_name: str, source_url: str, output_dir: str = "workflow_output") -> dict:
    markdown = run_scraper_with_retry(source_url)
    filtered = filter_scraped_markdown(markdown=markdown, source_url=source_url)
    ai_payload = run_ai_preparation(project_name=project_name, filtered_payload=filtered)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result = {
        "project_name": project_name,
        "source_url": source_url,
        "timestamp_utc": timestamp,
        "filtered": filtered,
        "ai_preparation": ai_payload,
    }

    file_name = f"{slugify(project_name)}_{timestamp}.json"
    full_path = output_path / file_name
    full_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    result["output_file"] = str(full_path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scrape + filter + AI preparation pipeline for one Facebook URL."
    )
    parser.add_argument("project_name", help="Project name from email subject")
    parser.add_argument("url", help="Facebook URL extracted from email")
    parser.add_argument(
        "--output-dir",
        default="workflow_output",
        help="Directory where pipeline JSON results are stored",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    output = execute_workflow(
        project_name=args.project_name,
        source_url=args.url,
        output_dir=args.output_dir,
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
