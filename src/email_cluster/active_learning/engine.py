from __future__ import annotations

import re
import sqlite3

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from email_cluster.storage.repository import blob_to_embedding


def suggest_from_examples(con: sqlite3.Connection, project_id: int, threshold: float = 0.65) -> list[dict[str, object]]:
    rows = list(con.execute("""
        SELECT se.email_id, se.embedding FROM semantic_embeddings se
        JOIN emails e ON e.id=se.email_id
        WHERE e.project_id=? AND se.id=(SELECT max(se2.id) FROM semantic_embeddings se2 WHERE se2.email_id=se.email_id)
    """, (project_id,)))
    vectors = {int(row["email_id"]): blob_to_embedding(row["embedding"]) for row in rows}
    examples = con.execute("""
        SELECT tl.id label_id, tl.label, le.email_id, le.example_type
        FROM taxonomy_labels tl JOIN label_examples le ON le.taxonomy_label_id=tl.id
        WHERE tl.project_id=? AND tl.active=1
    """, (project_id,))
    by_label: dict[int, dict[str, object]] = {}
    for row in examples:
        item = by_label.setdefault(int(row["label_id"]), {"label": row["label"], "positive": [], "negative": []})
        if int(row["email_id"]) in vectors:
            item[str(row["example_type"])].append(vectors[int(row["email_id"])])
    suggestions: list[dict[str, object]] = []
    for email_id, vector in vectors.items():
        best: tuple[float, str] | None = None
        for item in by_label.values():
            positives = item["positive"]
            if not positives:
                continue
            positive = float(np.max(cosine_similarity([vector], positives)))
            negatives = item["negative"]
            negative = float(np.max(cosine_similarity([vector], negatives))) if negatives else 0.0
            score = positive - max(negative, 0.0)
            if score >= threshold and (best is None or score > best[0]):
                best = (score, str(item["label"]))
        if best:
            suggestions.append({"email_id": email_id, "label": best[1], "score": round(best[0], 3)})
    return suggestions


def apply_rules(con: sqlite3.Connection, project_id: int) -> list[dict[str, object]]:
    rules = list(con.execute("""
        SELECT lr.*, tl.label FROM label_rules lr JOIN taxonomy_labels tl ON tl.id=lr.label_id
        WHERE lr.project_id=? AND lr.active=1 ORDER BY lr.priority DESC
    """, (project_id,)))
    emails = con.execute("""
        SELECT e.id, e.sender, e.subject, sc.message_type, sc.semantic_text_for_embedding,
               group_concat(a.attachment_type) attachment_types
        FROM emails e
        LEFT JOIN semantic_contexts sc ON sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=e.id)
        LEFT JOIN attachments a ON a.email_id=e.id WHERE e.project_id=? GROUP BY e.id
    """, (project_id,))
    matches: list[dict[str, object]] = []
    field_map = {
        "sender_domain": "sender", "sender_email": "sender", "subject_contains": "subject",
        "body_contains": "semantic_text_for_embedding", "attachment_type": "attachment_types",
        "message_type": "message_type", "regex": "semantic_text_for_embedding",
    }
    for email in emails:
        for rule in rules:
            value = str(email[field_map.get(rule["rule_type"], rule["target_field"] or "subject")] or "")
            pattern = str(rule["pattern"])
            matched = bool(re.search(pattern, value, re.I)) if rule["rule_type"] == "regex" else pattern.lower() in value.lower()
            if matched:
                matches.append({"email_id": int(email["id"]), "label": rule["label"], "rule_id": int(rule["id"])})
                break
    return matches
