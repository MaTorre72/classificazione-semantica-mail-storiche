from __future__ import annotations

# ruff: noqa: E702

import json
import re
import sqlite3
from collections import Counter

from email_cluster.storage.repository import json_dumps, utcnow


def update_context(con: sqlite3.Connection, context_id: int, action: str, **changes: object) -> None:
    row = context_row(con, context_id)
    allowed = {"name", "review_status", "macro_category", "context_type", "suggested_user_action", "source"}
    values = {key: value for key, value in changes.items() if key in allowed}
    if values:
        assignments = ",".join(f"{key}=?" for key in values)
        con.execute(f"UPDATE operational_contexts SET {assignments},updated_at=? WHERE id=?", (*values.values(), utcnow(), context_id))
    con.execute("INSERT INTO context_review_events (operational_context_id,action,old_value_json,new_value_json,created_at) VALUES (?,?,?,?,?)", (context_id, action, json_dumps(dict(row)), json_dumps(values), utcnow()))


def exclude_email(con: sqlite3.Connection, context_id: int, email_id: int, reason: str) -> None:
    con.execute("UPDATE email_context_assignments SET review_status='excluded',reason=?,updated_at=? WHERE operational_context_id=? AND email_id=?", (reason, utcnow(), context_id, email_id))
    _event(con, context_id, email_id, "exclude_email", {"reason": reason})


def move_email(con: sqlite3.Connection, email_id: int, target_context_id: int) -> None:
    target = context_row(con, target_context_id)
    con.execute("UPDATE email_context_assignments SET review_status='moved',updated_at=? WHERE email_id=? AND review_status!='moved'", (utcnow(), email_id))
    con.execute("""
        INSERT INTO email_context_assignments (email_id,operational_context_id,macro_category,assignment_source,confidence,review_status,reason,is_suspicious,created_at,updated_at)
        VALUES (?,?,?,'human',1.0,'approved','spostamento umano',0,?,?)
        ON CONFLICT(email_id,operational_context_id) DO UPDATE SET assignment_source='human',confidence=1.0,review_status='approved',updated_at=excluded.updated_at
    """, (email_id, target_context_id, target["macro_category"], utcnow(), utcnow()))
    _event(con, target_context_id, email_id, "move_email", {"target_context_id": target_context_id})


def split_context(con: sqlite3.Connection, context_id: int) -> list[int]:
    original = context_row(con, context_id)
    rows = list(con.execute("""
        SELECT eca.email_id,e.subject FROM email_context_assignments eca JOIN emails e ON e.id=eca.email_id
        WHERE eca.operational_context_id=? AND eca.review_status!='excluded'
    """, (context_id,)))
    buckets: dict[str, list[int]] = {}
    words = Counter(word for row in rows for word in _subject_words(row["subject"] or ""))
    anchors = [word for word, _ in words.most_common(2)]
    if len(anchors) < 2:
        update_context(con, context_id, "split_requested", review_status="needs_split", suggested_user_action="rinomina_o_sposta_email")
        return []
    for row in rows:
        subject_words = set(_subject_words(row["subject"] or ""))
        anchor = next((item for item in anchors if item in subject_words), anchors[-1])
        buckets.setdefault(anchor, []).append(int(row["email_id"]))
    new_ids: list[int] = []
    for anchor, email_ids in buckets.items():
        cur = con.execute("""
            INSERT INTO operational_contexts (project_id,source_clustering_run_id,name,description,context_type,macro_category,client_or_entity,technical_domain,practice_or_topic,why_grouped,suggested_user_action,source,confidence,review_status,review_priority,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'mixed',0.6,'pending',60,?,?)
        """, (original["project_id"], original["source_clustering_run_id"], f"{original['client_or_entity'] or 'Contesto'} — {anchor}", f"Separazione proposta dal contesto {original['name']}", original["context_type"], original["macro_category"], original["client_or_entity"], original["technical_domain"], anchor, f"Le email condividono il tema ricorrente '{anchor}'.", "approva_o_rinomina", utcnow(), utcnow()))
        new_id = int(cur.lastrowid); new_ids.append(new_id)
        for email_id in email_ids:
            con.execute("INSERT INTO email_context_assignments (email_id,operational_context_id,macro_category,assignment_source,confidence,review_status,reason,is_suspicious,created_at,updated_at) VALUES (?,?,?,'mixed',0.6,'pending',?,0,?,?)", (email_id,new_id,original["macro_category"],f"split operativo: {anchor}",utcnow(),utcnow()))
    update_context(con, context_id, "split_created", review_status="needs_split", suggested_user_action="controlla_nuovi_contesti")
    return new_ids


def context_row(con: sqlite3.Connection, context_id: int) -> sqlite3.Row:
    row = con.execute("SELECT * FROM operational_contexts WHERE id=?", (context_id,)).fetchone()
    if not row:
        raise ValueError("Contesto operativo non trovato")
    return row


def _event(con: sqlite3.Connection, context_id: int, email_id: int, action: str, value: dict[str, object]) -> None:
    con.execute("INSERT INTO context_review_events (operational_context_id,email_id,action,new_value_json,created_at) VALUES (?,?,?,?,?)", (context_id,email_id,action,json.dumps(value,ensure_ascii=False),utcnow()))


def _subject_words(subject: str) -> list[str]:
    return [word.lower() for word in re.findall(r"[A-Za-zÀ-ÿ]{4,}", subject) if word.lower() not in {"della","delle","inoltro","risposta","allegato","tenax","mail"}]
