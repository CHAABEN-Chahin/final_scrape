import re
from typing import Iterable

IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HEADING_NAME_PATTERN = re.compile(r"^#{1,6}\s*\*\*(.+?)\*\*\s*$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

LOGIN_NOISE_MARKERS = {
    "log in",
    "forgot password",
    "forgot account",
    "email or phone number",
    "password",
    "create new account",
    "see more on facebook",
}

TRAILING_NOISE_LINES = {
    "all reactions:",
    "like",
    "comment",
    "join",
    "or",
}


def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen = set()
    ordered = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def clean_markdown_line(line: str) -> str:
    no_images = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line)
    no_links = MARKDOWN_LINK_PATTERN.sub(lambda m: m.group(1), no_images)
    no_tags = re.sub(r"\s+", " ", no_links)
    return no_tags.strip(" -\t")


def extract_images(markdown: str) -> list[str]:
    urls = []
    for image_url in IMAGE_PATTERN.findall(markdown):
        if image_url.startswith("http://") or image_url.startswith("https://"):
            urls.append(image_url)
    return unique_keep_order(urls)


def extract_poster_name(lines: list[str]) -> str:
    for line in lines:
        match = HEADING_NAME_PATTERN.match(line.strip())
        if match:
            return clean_markdown_line(match.group(1))

    for idx, line in enumerate(lines):
        normalized = line.lower()
        if "shared with public" in normalized and idx > 0:
            candidate = clean_markdown_line(lines[idx - 1])
            if candidate and candidate.lower() not in TRAILING_NOISE_LINES:
                return candidate

    for idx, line in enumerate(lines):
        if line.strip().lower() == "join" and idx + 1 < len(lines):
            candidate = clean_markdown_line(lines[idx + 1])
            if candidate:
                return candidate

    return ""


def extract_post_text(lines: list[str]) -> str:
    cleaned_lines = []
    for raw_line in lines:
        line = clean_markdown_line(raw_line)
        if not line:
            continue

        normalized = line.lower()
        if any(marker in normalized for marker in LOGIN_NOISE_MARKERS):
            continue

        if normalized in TRAILING_NOISE_LINES:
            continue

        if line.startswith("#"):
            continue

        if line.startswith("http://") or line.startswith("https://"):
            continue

        cleaned_lines.append(line)

    # Keep meaningful text blocks and avoid metadata-like short fragments.
    text_lines = [line for line in cleaned_lines if len(line) >= 25]
    return "\n".join(text_lines).strip()


def filter_scraped_markdown(markdown: str, source_url: str) -> dict:
    lines = markdown.splitlines()
    poster_name = extract_poster_name(lines)
    images = extract_images(markdown)
    post_text = extract_post_text(lines)

    return {
        "source_url": source_url,
        "poster_name": poster_name,
        "post_text": post_text,
        "images": images,
    }
