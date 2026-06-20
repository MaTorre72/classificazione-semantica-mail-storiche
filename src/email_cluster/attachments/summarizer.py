from __future__ import annotations

import re


def summarize_attachment(filename: str | None, attachment_type: str, keywords: list[str], text: str | None, limit: int = 1500) -> str:
    parts = [f"Allegato {attachment_type}: {filename or 'senza nome'}." ]
    if keywords:
        parts.append(", ".join(keywords) + ".")
    if text:
        compact = re.sub(r"\s+", " ", text).strip()
        parts.append(compact[:limit])
    return " ".join(parts)[:limit]
