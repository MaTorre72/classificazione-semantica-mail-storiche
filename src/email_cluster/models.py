from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AttachmentRecord:
    filename: str | None
    mime_type: str | None
    size_bytes: int | None
    sha256: str | None = None


@dataclass(slots=True)
class ParsedEmail:
    source_file: Path
    source_type: str
    message_id: str | None
    message_hash: str
    subject: str | None
    sender: str | None
    recipients: list[str]
    cc: list[str]
    bcc: list[str]
    sent_at: datetime | None
    body_plain: str | None
    body_html: str | None
    body_extracted_text: str
    attachments: list[AttachmentRecord] = field(default_factory=list)
    raw_headers: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CleanedText:
    email_id: int
    language: str | None
    clean_text: str
    cleaning_version: str
    cleaning_flags: dict[str, bool]
    subject_clean: str = ""
    body_current_message_clean: str = ""
    semantic_text: str = ""
    message_type: str = "operational_email"
    quality_score: float = 0.0
    excluded_from_main_clustering: bool = False
    exclusion_reason: str | None = None
