import argparse
import asyncio
from pathlib import Path

from scrape_linkedin_public import scrape_linkedin_post

OUTPUT_FILE = Path(__file__).with_name("linkedin_post_output.md")
MAX_ATTEMPTS = 10
RETRY_DELAY_SECONDS = 20


def reset_output_file() -> None:
    OUTPUT_FILE.write_text("", encoding="utf-8")


def read_output_content() -> str:
    if not OUTPUT_FILE.exists():
        return ""
    return OUTPUT_FILE.read_text(encoding="utf-8")


def classify_output(content: str) -> str:
    stripped = content.strip()
    if not stripped:
        return "empty"

    normalized = stripped.lower()
    login_markers = [
        "sign in",
        "join now",
        "linkedin",
        "forgot password",
        "email or phone",
    ]
    marker_hits = sum(1 for marker in login_markers if marker in normalized)

    useful_markers = ["like", "comment", "repost", "shared", "posted", "#"]
    useful_hits = sum(1 for marker in useful_markers if marker in normalized)

    if marker_hits >= 3 and useful_hits <= 1 and len(stripped) < 900:
        return "login_wall_only"

    return "useful"


def compute_retry_delay(case: str, attempt: int) -> int:
    if case == "empty":
        return min(12 + attempt * 2, 25)
    if case == "login_wall_only":
        return min(25 + attempt * 3, 45)
    return RETRY_DELAY_SECONDS


async def run_linkedin_with_retries(url: str) -> bool:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"LinkedIn attempt {attempt}/{MAX_ATTEMPTS}")
        reset_output_file()

        try:
            await scrape_linkedin_post(url)
        except Exception as exc:
            print(f"LinkedIn scraper exception: {exc}")

        output_case = classify_output(read_output_content())
        if output_case == "useful":
            print("LinkedIn scrape succeeded: useful content found.")
            return True

        if output_case == "empty":
            print("LinkedIn scrape failed: output is empty.")
        else:
            print("LinkedIn scrape failed: login-wall-only content.")

        if attempt < MAX_ATTEMPTS:
            wait_seconds = compute_retry_delay(output_case, attempt)
            print(f"Waiting {wait_seconds} seconds before LinkedIn retry...")
            await asyncio.sleep(wait_seconds)

    print("All LinkedIn attempts failed.")
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run LinkedIn scraper logic with retries until output is useful."
    )
    parser.add_argument("url", help="LinkedIn URL to scrape")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    success = asyncio.run(run_linkedin_with_retries(args.url))
    raise SystemExit(0 if success else 1)
