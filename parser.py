import re
from email.header import decode_header
from email.message import Message
from html import unescape

SUPPORTED_PREFIXES = {
    "facebook": "facebook - ",
    "linkedin": "linkedin - ",
}
URL_PATTERN = re.compile(r"https?://[^\s<>()\"']+")
SUBJECT_PATTERN = re.compile(r"^(facebook|linkedin)\s*-\s*(.+)$", flags=re.IGNORECASE)


class WorkflowEmailParseError(ValueError):
    pass


def decode_mime_header(value: str) -> str:
    if not value:
        return ""

    decoded_parts = []
    for part, charset in decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts).strip()


def strip_html_tags(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def extract_email_body(message: Message) -> str:
    plain_parts = []
    html_parts = []

    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition.lower():
                continue

            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            charset = part.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            if content_type == "text/plain":
                plain_parts.append(content)
            elif content_type == "text/html":
                html_parts.append(content)
    else:
        payload = message.get_payload(decode=True)
        if payload is None:
            return ""
        charset = message.get_content_charset() or "utf-8"
        content = payload.decode(charset, errors="replace")
        if message.get_content_type() == "text/html":
            html_parts.append(content)
        else:
            plain_parts.append(content)

    if plain_parts:
        return "\n".join(plain_parts).strip()
    if html_parts:
        return strip_html_tags("\n".join(html_parts))
    return ""


def parse_subject(subject: str) -> tuple[str, str]:
    decoded_subject = decode_mime_header(subject)
    match = SUBJECT_PATTERN.match(decoded_subject.strip())
    if not match:
        expected = " or ".join(f"'{p}<project_name>'" for p in SUPPORTED_PREFIXES.values())
        raise WorkflowEmailParseError(f"Invalid subject format. Expected: {expected}")

    matched_platform = match.group(1).lower()
    project_name = match.group(2).strip().strip('"').strip("'")
    if not project_name:
        raise WorkflowEmailParseError("Project name is missing in subject.")

    return matched_platform, project_name


def extract_platform_url(body: str, platform: str) -> str:
    matches = URL_PATTERN.findall(body)
    host_marker = "facebook.com" if platform == "facebook" else "linkedin.com"
    for url in matches:
        if host_marker in url.lower():
            return url

    raise WorkflowEmailParseError(f"No {platform} URL found in email body.")


def parse_email_message(message: Message) -> dict:
    platform, project_name = parse_subject(message.get("Subject", ""))
    body = extract_email_body(message)
    url = extract_platform_url(body, platform)

    return {
        "platform": platform,
        "project_name": project_name,
        "url": url,
        "subject": decode_mime_header(message.get("Subject", "")),
        "from": decode_mime_header(message.get("From", "")),
        "body": body,
    }
