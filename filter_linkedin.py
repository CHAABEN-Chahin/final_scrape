import re
import json
from typing import Iterable
from urllib import request
from html import unescape
from pathlib import Path

IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
META_IMAGE_PATTERN = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)["\']',
    flags=re.IGNORECASE,
)

NOISE_MARKERS = {
    "sign in",
    "join now",
    "forgot password",
    "download the app",
}

NOISE_IMAGE_MARKERS = (
    "static.licdn.com/aero-v1/sc/h/",
    "emoji",
    "favicon",
    "logo",
)

CANDIDATES_FILE = Path(__file__).with_name("linkedin_image_candidates.json")


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
    return re.sub(r"\s+", " ", no_links).strip(" -\t")


def is_noise_image_url(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in NOISE_IMAGE_MARKERS)


def fetch_public_html(url: str) -> str:
    req = request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    )
    with request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_meta_images_from_url(source_url: str) -> list[str]:
    try:
        html = fetch_public_html(source_url)
    except Exception:
        return []

    candidates = []
    for image_url in META_IMAGE_PATTERN.findall(html):
        image_url = unescape(image_url)
        if image_url.startswith("http://") or image_url.startswith("https://"):
            if not is_noise_image_url(image_url):
                candidates.append(image_url)

    return unique_keep_order(candidates)


def load_scraper_image_candidates(source_url: str) -> list[str]:
    if not CANDIDATES_FILE.exists() or not CANDIDATES_FILE.is_file():
        return []
    try:
        payload = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    if str(payload.get("source_url", "")).strip() != str(source_url).strip():
        return []

    urls = payload.get("image_candidates", [])
    if not isinstance(urls, list):
        return []

    cleaned = []
    for url in urls:
        if isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
            if not is_noise_image_url(url):
                cleaned.append(url)
    cleaned = unique_keep_order(cleaned)
    cleaned.sort(key=lambda u: ("media.licdn.com/dms/image" not in u.lower(), len(u)))
    return cleaned


def extract_images(markdown: str) -> list[str]:
    images = []
    for image_url in IMAGE_PATTERN.findall(markdown):
        if image_url.startswith("http://") or image_url.startswith("https://"):
            if not is_noise_image_url(image_url):
                images.append(image_url)

    images = unique_keep_order(images)
    # Prefer real LinkedIn CDN media images first.
    images.sort(key=lambda u: ("media.licdn.com" not in u.lower(), len(u)))
    return images


def extract_caption(markdown: str) -> str:
    lines = markdown.splitlines()
    kept = []
    for raw_line in lines:
        line = clean_markdown_line(raw_line)
        if not line:
            continue
        lower = line.lower()
        if any(marker in lower for marker in NOISE_MARKERS):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            continue
        if len(line) < 25:
            continue
        kept.append(line)

    return "\n".join(kept).strip()


def extract_poster_name(markdown: str) -> str:
    lines = [clean_markdown_line(line) for line in markdown.splitlines()]
    for idx, line in enumerate(lines):
        lower = line.lower()
        if "followers" in lower and idx > 0:
            return lines[idx - 1]
        if "posted" in lower and idx > 0:
            return lines[idx - 1]
    return ""


def filter_linkedin_markdown(markdown: str, source_url: str) -> dict:
    images = load_scraper_image_candidates(source_url)
    if not images:
        images = extract_images(markdown)
    if not images:
        images = extract_meta_images_from_url(source_url)
    else:
        images = unique_keep_order(images)

    images.sort(key=lambda u: ("media.licdn.com" not in u.lower(), len(u)))

    return {
        "source_url": source_url,
        "poster_name": extract_poster_name(markdown),
        "post_text": extract_caption(markdown),
        "images": images,
    }
