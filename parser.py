import re
from email.header import decode_header
from email.message import Message
from html import unescape

SUBJECT_PREFIX = "facebook - "
URL_PATTERN = re.compile(r"https?://[^\s<>()\"']+")


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


def parse_subject(subject: str) -> str:
    decoded_subject = decode_mime_header(subject)
    if not decoded_subject.lower().startswith(SUBJECT_PREFIX):
        raise WorkflowEmailParseError(
            f"Invalid subject format. Expected: '{SUBJECT_PREFIX}<project_name>'"
        )

    project_name = decoded_subject[len(SUBJECT_PREFIX) :].strip()
    if not project_name:
        raise WorkflowEmailParseError("Project name is missing in subject.")

    return project_name


def extract_facebook_url(body: str) -> str:
    matches = URL_PATTERN.findall(body)
    for url in matches:
        if "facebook.com" in url.lower():
            return url
    raise WorkflowEmailParseError("No Facebook URL found in email body.")


def parse_email_message(message: Message) -> dict:
    project_name = parse_subject(message.get("Subject", ""))
    body = extract_email_body(message)
    url = extract_facebook_url(body)

    return {
        "project_name": project_name,
        "url": url,
        "subject": decode_mime_header(message.get("Subject", "")),
        "from": decode_mime_header(message.get("From", "")),
        "body": body,
    }
