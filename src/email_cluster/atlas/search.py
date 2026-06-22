from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

from pathlib import Path
from typing import Any


from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository


def build_index(db_path: Path, project: str) -> dict[str, Any]:
    init_db(db_path)
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        con.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS atlas_search USING fts5(document_type UNINDEXED,source_id UNINDEXED,project_id UNINDEXED,subject,content,participants,attachments,entities,tokenize='unicode61 remove_diacritics 2')"
        )
        con.execute("DELETE FROM atlas_search WHERE project_id=?", (pid,))
        conversations = list(
            con.execute(
                """SELECT ac.*,group_concat(a.filename,' ') attachment_names FROM atlas_conversations ac
            LEFT JOIN atlas_conversation_messages cm ON cm.conversation_id=ac.id LEFT JOIN attachments a ON a.email_id=cm.email_id
            WHERE ac.project_id=? GROUP BY ac.id""",
                (pid,),
            )
        )
        con.executemany(
            "INSERT INTO atlas_search(document_type,source_id,project_id,subject,content,participants,attachments,entities) VALUES('conversation',?,?,?,?,?,?,?)",
            [
                (
                    r["id"],
                    pid,
                    r["subject_normalized"],
                    r["analysis_text"],
                    r["participants_json"],
                    r["attachment_names"] or "",
                    "",
                )
                for r in conversations
            ],
        )
    return {"indexed_conversations": len(conversations)}


def search(
    db_path: Path, query: str, project: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    with connect(db_path) as con:
        pid = Repository(con).project_id(project) if project else None
        clauses = "atlas_search MATCH ?" + (" AND project_id=?" if pid else "")
        params = [query] + ([pid] if pid else []) + [limit]
        rows = con.execute(
            f"""SELECT document_type,source_id,subject,snippet(atlas_search,4,'[',']',' … ',18) evidence,bm25(atlas_search) score
            FROM atlas_search WHERE {clauses} ORDER BY score LIMIT ?""",
            params,
        )
        return [dict(r) for r in rows]
