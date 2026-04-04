import asyncio
import json
import re
from pathlib import Path

from crawl4ai import AsyncWebCrawler


OUTPUT_MARKDOWN = Path(__file__).with_name("linkedin_post_output.md")
OUTPUT_CANDIDATES = Path(__file__).with_name("linkedin_image_candidates.json")


def _extract_image_urls_from_text(blob: str) -> list[str]:
    if not blob:
        return []

    patterns = [
        r"https://media\.licdn\.com/dms/image/[^\"'\s)]+",
        r"https://[^\"'\s)]+feedshare-[^\"'\s)]+",
        r"<meta[^>]+(?:property|name)=[\"'](?:og:image|twitter:image)[\"'][^>]+content=[\"']([^\"']+)[\"']",
        r"!\[[^\]]*\]\((https?://[^)]+)\)",
    ]

    urls: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, blob, flags=re.IGNORECASE):
            url = match if isinstance(match, str) else ""
            if not url:
                continue
            url = url.replace("&amp;", "&")
            if url.startswith("http://") or url.startswith("https://"):
                urls.append(url)

    # Prefer real post-media CDN paths over generic assets.
    unique = []
    for url in urls:
        if url not in unique:
            unique.append(url)

    unique.sort(key=lambda u: ("media.licdn.com/dms/image" not in u.lower(), len(u)))
    return unique


def build_image_candidates(result) -> list[str]:
    blobs = [
        str(getattr(result, "markdown", "") or ""),
        str(getattr(result, "cleaned_html", "") or ""),
        str(getattr(result, "html", "") or ""),
        str(getattr(result, "raw_html", "") or ""),
    ]

    candidates: list[str] = []
    for blob in blobs:
        candidates.extend(_extract_image_urls_from_text(blob))

    deduped: list[str] = []
    for url in candidates:
        if url not in deduped:
            deduped.append(url)
    return deduped


async def scrape_linkedin_post(url: str) -> None:
    print(f"Initializing LinkedIn crawler for: {url}")

    async with AsyncWebCrawler(verbose=True) as crawler:
        result = await crawler.arun(
            url=url,
            wait_for="main",
            magic=True,
            remove_overlay_elements=True,
            bypass_cache=True,
        )

        if result.success:
            print("LinkedIn extraction successful")
            OUTPUT_MARKDOWN.write_text(result.markdown, encoding="utf-8")

            candidates = build_image_candidates(result)
            OUTPUT_CANDIDATES.write_text(
                json.dumps(
                    {
                        "source_url": url,
                        "image_candidates": candidates,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            print("Saved LinkedIn markdown to linkedin_post_output.md")
            print(f"Saved {len(candidates)} LinkedIn image candidate(s) to linkedin_image_candidates.json")
        else:
            print(f"LinkedIn scrape failed: {result.error_message}")
            OUTPUT_MARKDOWN.write_text("", encoding="utf-8")
            OUTPUT_CANDIDATES.write_text(
                json.dumps({"source_url": url, "image_candidates": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


if __name__ == "__main__":
    target_url = "https://www.linkedin.com/posts/"
    asyncio.run(scrape_linkedin_post(target_url))
