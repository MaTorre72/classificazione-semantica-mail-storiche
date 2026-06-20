from __future__ import annotations

import html
import re

from email_cluster.config import CleaningConfig
from email_cluster.models import CleanedText

from .classifier import classify_message
from .quality import semantic_quality
from .segmentation import segment_body


def build_clean_text(
    email_id: int,
    text: str = "",
    version: str = "v1.0.0",
    *,
    subject: str | None = None,
    body: str | None = None,
    has_attachments: bool = False,
    config: CleaningConfig | None = None,
) -> CleanedText:
    cfg = config or CleaningConfig(version=version)
    if subject is None and body is None:
        subject, _, body = (text or "").partition("\n\n")
        if not body:
            body, subject = subject, ""
    subject_clean = clean_subject(subject or "")
    normalized_body = normalize_whitespace(remove_html_artifacts(body or ""))
    segments = segment_body(normalized_body, cfg.quote_patterns)
    current = clean_current_message("\n".join(segments.current_message))
    semantic = "\n\n".join(part for part in (subject_clean, current) if part).strip()
    semantic = semantic[: cfg.max_semantic_chars].strip()
    classification_body = current
    if segments.newsletter_footer:
        classification_body += "\n" + "\n".join(segments.newsletter_footer)
    message_type = classify_message(subject_clean, classification_body, has_attachments)
    score, quality_reason = semantic_quality(semantic, cfg.min_semantic_chars, cfg.min_unique_words)
    reason = quality_reason
    if message_type in cfg.exclude_message_types:
        reason = f"tipo messaggio escluso: {message_type}"
    flags = {
        "signature_removed": bool(segments.signature),
        "disclaimer_removed": bool(segments.disclaimer),
        "quoted_reply_removed": bool(segments.quoted_reply),
        "forwarded_block_removed": bool(segments.forwarded_message),
        "newsletter_footer_removed": bool(segments.newsletter_footer),
        "technical_headers_removed": bool(segments.technical_headers),
        "html_converted": False,
    }
    return CleanedText(
        email_id=email_id,
        language=detect_language(semantic),
        clean_text=current,
        cleaning_version=cfg.version,
        cleaning_flags=flags,
        subject_clean=subject_clean,
        body_current_message_clean=current,
        semantic_text=semantic,
        message_type=message_type,
        quality_score=score,
        excluded_from_main_clustering=reason is not None,
        exclusion_reason=reason,
        quoted_thread_text=normalize_whitespace("\n".join(segments.quoted_reply)),
        forwarded_text=normalize_whitespace("\n".join(segments.forwarded_message)),
        signature_text=normalize_whitespace("\n".join(segments.signature)),
        disclaimer_text=normalize_whitespace("\n".join(segments.disclaimer)),
        automatic_footer_text=normalize_whitespace(
            "\n".join(segments.automatic_footer + segments.newsletter_footer)
        ),
    )


def clean_subject(subject: str) -> str:
    value = remove_html_artifacts(subject)
    value = re.sub(r"^(?:(?:re|fw|fwd|rif|inoltro)\s*:\s*)+", "", value, flags=re.I)
    value = re.sub(r"\[(?:spam|external|esterno)\]\s*", "", value, flags=re.I)
    return normalize_whitespace(value)


def clean_current_message(text: str) -> str:
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = normalize_whitespace(normalize_inline_links(raw_line))
        if line and not _is_low_signal_line(line):
            kept.append(line)
    return normalize_whitespace("\n".join(kept))


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_html_artifacts(text: str) -> str:
    return html.unescape(text.replace("\u00a0", " "))


def normalize_inline_links(text: str) -> str:
    text = re.sub(r"\[?cid:[^\] >]+\]?", "", text, flags=re.I)
    text = re.sub(r"<https?://[^>]+>", "", text, flags=re.I)
    return text


def _is_low_signal_line(line: str) -> bool:
    lowered = line.lower()
    if re.fullmatch(r"[>_\-=* .]{2,}", line):
        return True
    if re.fullmatch(r"(?:https?://|www\.)\S+", lowered):
        return True
    if re.fullmatch(r"[\w.+-]+@[\w.-]+\.\w+", lowered):
        return True
    if re.fullmatch(r"(?:tel|fax|cell|mobile|pec|e-mail)[: .+\d()/\-]+", lowered):
        return True
    if re.search(r"\b(?:p\.?\s*iva|partita iva|codice fiscale|c\.?f\.?)\b", lowered):
        return True
    if re.search(r"\b(?:via|viale|piazza|corso)\b.+\b\d{5}\b", lowered):
        return True
    if lowered.startswith(("[immagine", "image:", "mailto:", "curriculum vitae")):
        return True
    return False


def detect_language(text: str) -> str | None:
    lowered = f" {text[:3000].lower()} "
    italian = sum(token in lowered for token in (" il ", " la ", " che ", " per ", " della ", " con "))
    english = sum(token in lowered for token in (" the ", " and ", " for ", " with ", " this ", " from "))
    if italian == english == 0:
        return None
    return "it" if italian >= english else "en"
