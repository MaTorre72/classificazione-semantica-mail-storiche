from __future__ import annotations

import hashlib
import mailbox
import re
from collections.abc import Iterable
from datetime import datetime
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from email_cluster.models import AttachmentRecord, ParsedEmail
from email_cluster.attachments.classifier import classify_attachment
from email_cluster.attachments.extractor import extract_attachment_text


def parse_eml(path: Path, *, extract_attachments: bool = True, max_attachment_size_mb: int = 20) -> ParsedEmail:
    msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    return parse_message(msg, source_file=path, source_type="eml", extract_attachments=extract_attachments, max_attachment_size_mb=max_attachment_size_mb)


def parse_mbox(path: Path, *, extract_attachments: bool = True, max_attachment_size_mb: int = 20) -> Iterable[ParsedEmail]:
    mbox = mailbox.mbox(path, factory=lambda f: BytesParser(policy=policy.default).parse(f))
    for msg in mbox:
        yield parse_message(msg, source_file=path, source_type="mbox", extract_attachments=extract_attachments, max_attachment_size_mb=max_attachment_size_mb)


def parse_message(
    msg: Message, source_file: Path, source_type: str, *,
    extract_attachments: bool = True, max_attachment_size_mb: int = 20,
) -> ParsedEmail:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[AttachmentRecord] = []

    for part in _walk_parts(msg):
        content_disposition = part.get_content_disposition()
        content_type = part.get_content_type()
        filename = part.get_filename()

        if content_disposition == "attachment" or filename:
            payload = _payload_bytes(part)
            attachment_type, keywords = classify_attachment(filename)
            if extract_attachments:
                extracted_text, status, error = extract_attachment_text(
                    payload or b"", filename, content_type, max_attachment_size_mb
                )
            else:
                extracted_text, status, error = None, "metadata_only", None
            attachments.append(
                AttachmentRecord(
                    filename=filename,
                    mime_type=content_type,
                    size_bytes=len(payload) if payload is not None else None,
                    sha256=hashlib.sha256(payload).hexdigest() if payload else None,
                    attachment_type=attachment_type,
                    attachment_keywords=keywords,
                    extracted_text=extracted_text,
                    text_excerpt=(extracted_text or "")[:2000] or None,
                    extraction_status=status,
                    extraction_error=error,
                )
            )
            continue

        if content_type == "text/plain":
            plain_parts.append(_decode_part(part))
        elif content_type == "text/html":
            html = _decode_part(part)
            html_parts.append(html)

    body_plain = "\n\n".join(p for p in plain_parts if p).strip() or None
    body_html = "\n\n".join(p for p in html_parts if p).strip() or None
    extracted = body_plain or html_to_text(body_html or "")
    message_hash = generate_message_hash(msg, extracted)

    return ParsedEmail(
        source_file=source_file,
        source_type=source_type,
        message_id=_header(msg, "Message-ID"),
        message_hash=message_hash,
        subject=_header(msg, "Subject"),
        sender=_header(msg, "From"),
        recipients=_addresses(msg, "To"),
        cc=_addresses(msg, "Cc"),
        bcc=_addresses(msg, "Bcc"),
        sent_at=_parse_date(_header(msg, "Date")),
        body_plain=body_plain,
        body_html=body_html,
        body_extracted_text=extracted,
        attachments=attachments,
        raw_headers={key: str(value) for key, value in msg.items()},
    )


def _walk_parts(msg: Message) -> Iterable[Message]:
    if msg.is_multipart():
        for part in msg.walk():
            if part.is_multipart():
                continue
            yield part
    else:
        yield msg


def _header(msg: Message, name: str) -> str | None:
    value = msg.get(name)
    return str(value).strip() if value is not None else None


def _addresses(msg: Message, name: str) -> list[str]:
    values = msg.get_all(name, [])
    return [addr for _, addr in getaddresses(values) if addr]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None


def _payload_bytes(part: Message) -> bytes | None:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8", errors="replace")
    return None


def _decode_part(part: Message) -> str:
    if isinstance(part, EmailMessage):
        try:
            content = part.get_content()
            return content if isinstance(content, str) else str(content)
        except (LookupError, UnicodeDecodeError, AttributeError):
            pass
    payload = _payload_bytes(part)
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset()
    if charset:
        try:
            return payload.decode(charset, errors="replace")
        except LookupError:
            pass
    try:
        from charset_normalizer import from_bytes
    except ImportError:
        return payload.decode("utf-8", errors="replace")
    match = from_bytes(payload).best()
    return str(match) if match is not None else payload.decode("utf-8", errors="replace")


def html_to_text(html: str) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        parser = _TextHTMLParser()
        parser.feed(html)
        return re.sub(r"\n{3,}", "\n\n", unescape(parser.text)).strip()

    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    return soup.get_text("\n", strip=True)


def generate_message_hash(msg: Message, extracted_text: str) -> str:
    pieces = [
        _header(msg, "Message-ID") or "",
        _header(msg, "Date") or "",
        _header(msg, "From") or "",
        _header(msg, "Subject") or "",
        extracted_text or "",
    ]
    return hashlib.sha256("\n".join(pieces).encode("utf-8", errors="replace")).hexdigest()


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())
            self.parts.append("\n")
