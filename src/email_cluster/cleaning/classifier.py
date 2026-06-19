from __future__ import annotations

import re

from .patterns import AUTOMATIC_MARKERS, CALENDAR_MARKERS, DELIVERY_MARKERS, NEWSLETTER_MARKERS, PEC_MARKERS


def classify_message(subject: str, body: str, has_attachments: bool = False) -> str:
    text = f"{subject}\n{body}".lower()
    if any(marker in text for marker in PEC_MARKERS):
        return "pec_receipt"
    if any(marker in text for marker in DELIVERY_MARKERS):
        return "delivery_notification"
    if any(marker in text for marker in CALENDAR_MARKERS):
        return "calendar_message"
    if any(marker in text for marker in NEWSLETTER_MARKERS):
        return "newsletter"
    if any(marker in text for marker in AUTOMATIC_MARKERS):
        return "auto_generated"
    words = re.findall(r"\b[^\W\d_]{2,}\b", body, re.UNICODE)
    if not words and has_attachments:
        return "attachment_only"
    if not words and re.search(r"inoltrat|forward", subject, re.I):
        return "forward_only"
    compact = " ".join(words).lower()
    if len(words) <= 5 and re.fullmatch(r"(?:ok|okay|grazie|thanks|ricevuto|perfetto|va bene|bene|ciao|saluti)[ .,!]*(?:grazie|thanks)?", compact):
        return "short_ack"
    if len(set(word.lower() for word in words)) < 4:
        return "low_information"
    return "operational_email"
