import argparse
import asyncio
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

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


def read_output_content() -> str:
    if not OUTPUT_FILE.exists():
        return ""
    return OUTPUT_FILE.read_text(encoding="utf-8")


def normalize_facebook_url(url: str) -> str:
    parsed = urlparse(url)
    # Ignore fragments because they can hold noisy tracking state.
    return urlunparse(parsed._replace(fragment=""))


def extract_embedded_target_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    candidates: list[str] = []
    for key in ("share_url", "next"):
        for value in params.get(key, []):
            first_decode = unquote(value)
            second_decode = unquote(first_decode)
            for decoded in (first_decode, second_decode):
                if "facebook.com" in decoded:
                    candidates.append(normalize_facebook_url(decoded))

    return candidates


def build_candidate_urls(url: str) -> list[str]:
    ordered = [normalize_facebook_url(url)]
    ordered.extend(extract_embedded_target_urls(url))

    unique: list[str] = []
    for candidate in ordered:
        if candidate not in unique:
            unique.append(candidate)

    return unique


def classify_output(content: str) -> str:
    stripped = content.strip()
    if stripped == "":
        return "empty"

    normalized = content.lower()
    login_markers = [
        "facebook",
        "log in",
        "forgot",
        "see more on facebook",
        "email or phone number",
        "password",
        "create new account",
    ]
    login_hits = sum(1 for marker in login_markers if marker in normalized)

    post_markers = [
        "shared with public",
        "all reactions",
        "like",
        "comment",
        "#",
        "## ",
        "### ",
        "· [",
        "photo",
    ]
    post_hits = sum(1 for marker in post_markers if marker in normalized)

    has_substantial_content = len(stripped) >= 800

    if login_hits >= 5 and post_hits <= 1:
        return "login_wall_only"

    if login_hits >= 3 and post_hits >= 2 and has_substantial_content:
        return "mixed_useful"

    if post_hits >= 2 or has_substantial_content:
        return "useful"

    # Default fallback: non-empty content that is not clearly login-wall-only.
    return "useful"


def compute_retry_delay(case: str, attempt: int) -> int:
    if case == "empty":
        # Empty often recovers quickly.
        return min(12 + attempt * 2, 25)
    if case == "login_wall_only":
        # Login walls usually need more time between attempts.
        return min(25 + attempt * 3, 45)
    return RETRY_DELAY_SECONDS


async def run_with_retries(url: str) -> bool:
    candidate_urls = build_candidate_urls(url)
    print("Candidate URLs (will rotate each attempt):")
    for candidate in candidate_urls:
        print(f"- {candidate}")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempt_url = candidate_urls[(attempt - 1) % len(candidate_urls)]
        print(f"Attempt {attempt}/{MAX_ATTEMPTS}")
        print(f"Using URL: {attempt_url}")
        reset_output_file()

        try:
            await scrape_facebook_post(attempt_url)
        except Exception as exc:
            print(f"Scraper raised an exception: {exc}")

        content = read_output_content()
        output_case = classify_output(content)

        if output_case in ("useful", "mixed_useful"):
            if output_case == "mixed_useful":
                print("Scrape succeeded: useful content found with some login-wall fragments.")
            else:
                print("Scrape succeeded: useful content found.")
            return True

        if output_case == "empty":
            print("Scrape failed: fb_post_output.md is empty.")
        elif output_case == "login_wall_only":
            print("Scrape failed: fb_post_output.md appears to be login-wall only.")
        else:
            print("Scrape failed: content was not classified as useful.")

        if attempt < MAX_ATTEMPTS:
            wait_seconds = compute_retry_delay(output_case, attempt)
            print(f"Waiting {wait_seconds} seconds before retry...")
            await asyncio.sleep(wait_seconds)

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
