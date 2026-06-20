from __future__ import annotations

import re
from collections import Counter


def summarize_thread(text: str, max_chars: int = 1500) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", compact)
    words = re.findall(r"\b[^\W\d_]{4,}\b", compact.lower())
    keywords = [word for word, _ in Counter(words).most_common(8)]
    summary = " ".join(sentences[:3])
    if keywords:
        summary += " Parole chiave thread: " + ", ".join(keywords) + "."
    return summary[:max_chars]
