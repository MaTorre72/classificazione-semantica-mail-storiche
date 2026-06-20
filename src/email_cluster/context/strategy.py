from __future__ import annotations

import re


def choose_strategy(
    message_type: str, current: str, thread: str, attachment_summary: str,
    excluded_types: list[str], min_chars: int,
) -> tuple[str, bool, str | None]:
    if message_type in excluded_types:
        return "exclude_from_main_clustering", True, f"tipo messaggio escluso: {message_type}"
    current_words = re.findall(r"\b\w{3,}\b", current)
    attachment_phrase = bool(re.search(r"\b(in|vedi|trovi|trasmetto).{0,25}allegat", current, re.I))
    if attachment_summary and (attachment_phrase or len(current_words) < 12):
        return "attachment_dominant", False, None
    if len(current.strip()) < min_chars and len(thread.strip()) >= min_chars:
        return "thread_dominant", False, None
    if len(current_words) < 5:
        return "exclude_from_main_clustering", True, "contenuto operativo insufficiente"
    return "current_plus_subject", False, None
