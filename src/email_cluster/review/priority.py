from __future__ import annotations

import json
import sqlite3


GENERIC = {"cluster", "tenax", "analisi", "email", "mail", "altro", "rumore"}


def cluster_priority(row: sqlite3.Row) -> float:
    label = (row["label_auto"] or "").lower()
    score = (1.0 - float(row["coherence_score"] or 0.5)) * 35
    score += (1.0 - float(row["mean_probability"] or 0.5)) * 30
    if any(word in GENERIC for word in label.replace(",", " ").split()):
        score += 20
    if int(row["cluster_id"]) == -1:
        score += 25
    if int(row["size"] or 0) > 25:
        score += 10
    senders = json.loads(row["recurring_senders_json"] or "[]")
    score += min(len(senders) * 2, 10)
    return round(score, 2)


def email_priority(probability: float | None, is_noise: bool, strategy: str | None, excluded: bool) -> float:
    score = (1.0 - float(probability or 0.0)) * 45
    if is_noise:
        score += 30
    if strategy in {"attachment_dominant", "thread_dominant"}:
        score += 15
    if excluded:
        score += 10
    return round(score, 2)
