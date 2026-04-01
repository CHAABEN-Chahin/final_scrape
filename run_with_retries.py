import argparse
import asyncio
from pathlib import Path

from scrape_public import scrape_facebook_post

OUTPUT_FILE = Path(__file__).with_name("fb_post_output.md")
MAX_ATTEMPTS = 10
RETRY_DELAY_SECONDS = 20


def reset_output_file() -> None:
    # Make failure detection deterministic for each attempt.
    OUTPUT_FILE.write_text("", encoding="utf-8")


def output_has_content() -> bool:
    if not OUTPUT_FILE.exists():
        return False
    return OUTPUT_FILE.read_text(encoding="utf-8").strip() != ""


async def run_with_retries(url: str) -> bool:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"Attempt {attempt}/{MAX_ATTEMPTS}")
        reset_output_file()

        try:
            await scrape_facebook_post(url)
        except Exception as exc:
            print(f"Scraper raised an exception: {exc}")

        if output_has_content():
            print("Scrape succeeded: fb_post_output.md is not empty.")
            return True

        print("Scrape failed: fb_post_output.md is empty.")
        if attempt < MAX_ATTEMPTS:
            print(f"Waiting {RETRY_DELAY_SECONDS} seconds before retry...")
            await asyncio.sleep(RETRY_DELAY_SECONDS)

    print("All attempts failed.")
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run scrape_public.py logic with retries until output is non-empty."
    )
    parser.add_argument("url", help="Facebook URL to scrape")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    success = asyncio.run(run_with_retries(args.url))
    raise SystemExit(0 if success else 1)
