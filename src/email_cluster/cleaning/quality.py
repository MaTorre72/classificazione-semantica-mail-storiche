from __future__ import annotations

import re


def semantic_quality(text: str, min_chars: int, min_unique_words: int) -> tuple[float, str | None]:
    words = re.findall(r"\b[^\W\d_]{2,}\b", text.lower(), re.UNICODE)
    unique = set(words)
    char_score = min(len(text) / max(min_chars * 3, 1), 1.0)
    word_score = min(len(unique) / max(min_unique_words * 2, 1), 1.0)
    diversity = min(len(unique) / max(len(words), 1), 1.0)
    score = round(0.4 * char_score + 0.4 * word_score + 0.2 * diversity, 3)
    if len(text.strip()) < min_chars:
        return score, f"semantic_text sotto {min_chars} caratteri"
    if len(unique) < min_unique_words:
        return score, f"meno di {min_unique_words} parole uniche"
    return score, None
