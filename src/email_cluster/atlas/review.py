from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

import json
from pathlib import Path
from typing import Any


from email_cluster.storage.database import connect
from email_cluster.storage.repository import Repository, utcnow


def review_action(
    db_path: Path,
    project: str,
    candidate_id: int,
    action: str,
    name: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    allowed = {"approve", "rename", "exclude", "deprecate", "ambiguous", "merge"}
    if action not in allowed:
        raise ValueError("Azione di revisione non supportata")
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        row = con.execute(
            "SELECT * FROM atlas_candidate_categories WHERE id=? AND project_id=?",
            (candidate_id, pid),
        ).fetchone()
        if not row:
            raise ValueError("Categoria candidata non trovata")
        before = dict(row)
        status = {
            "approve": "approved",
            "rename": "candidate",
            "exclude": "excluded",
            "deprecate": "deprecated",
            "ambiguous": "ambiguous",
            "merge": "to_merge",
        }[action]
        con.execute(
            "UPDATE atlas_candidate_categories SET name=coalesce(?,name),status=?,updated_at=? WHERE id=?",
            (name, status, utcnow(), candidate_id),
        )
        if action == "approve":
            con.execute(
                """INSERT INTO atlas_categories(project_id,candidate_id,scope,operational_theme,description,lexical_signals_json,
                recurring_domains_json,assignment_criterion,status,confidence,source,last_reviewed_at,notes,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,'human',?,?,?,?)""",
                (
                    pid,
                    candidate_id,
                    row["scope"],
                    name or row["name"],
                    row["description"],
                    row["lexical_signals_json"],
                    row["recurring_domains_json"],
                    row["rationale"],
                    "approved",
                    row["confidence"],
                    utcnow(),
                    notes,
                    utcnow(),
                    utcnow(),
                ),
            )
        after = dict(
            con.execute(
                "SELECT * FROM atlas_candidate_categories WHERE id=?", (candidate_id,)
            ).fetchone()
        )
        con.execute(
            "INSERT INTO atlas_review_decisions(project_id,target_type,target_id,action,before_json,after_json,notes,created_at) VALUES(?,'candidate',?,?,?,?,?,?)",
            (
                pid,
                candidate_id,
                action,
                json.dumps(before, default=str),
                json.dumps(after, default=str),
                notes,
                utcnow(),
            ),
        )
    return after
