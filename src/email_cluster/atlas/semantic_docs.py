from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

import hashlib
import json
from pathlib import Path
from typing import Any


from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, utcnow

from .common import ATLAS_VERSION


def build_semantic_docs(db_path: Path, project: str) -> dict[str, Any]:
    init_db(db_path)
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        rows = list(con.execute("SELECT * FROM atlas_conversations WHERE project_id=?", (pid,)))
        created = 0
        for row in rows:
            entities = [
                x[0]
                for x in con.execute(
                    """SELECT DISTINCT ae.display_name FROM atlas_entities ae JOIN atlas_entity_mentions em ON em.entity_id=ae.id
                JOIN atlas_conversation_messages cm ON cm.email_id=em.email_id WHERE cm.conversation_id=? ORDER BY ae.frequency DESC LIMIT 20""",
                    (row["id"],),
                )
            ]
            attachments = [
                x[0]
                for x in con.execute(
                    """SELECT DISTINCT a.filename FROM attachments a JOIN atlas_conversation_messages cm ON cm.email_id=a.email_id WHERE cm.conversation_id=? AND a.filename IS NOT NULL LIMIT 20""",
                    (row["id"],),
                )
            ]
            content = (
                f"Oggetto: {row['subject_normalized']}\nPartecipanti: {', '.join(json.loads(row['participants_json'] or '[]'))}\nEntità: {', '.join(entities)}\nAllegati: {', '.join(attachments)}\n\n{row['analysis_text'] or ''}"
            )[:60000]
            digest = hashlib.sha256(content.encode()).hexdigest()
            con.execute(
                """INSERT INTO atlas_semantic_documents(project_id,document_level,source_id,version,content_hash,content,metadata_json,created_at)
                VALUES(?,'conversation',?,?,?,?,?,?) ON CONFLICT(document_level,source_id,version) DO UPDATE SET content_hash=excluded.content_hash,content=excluded.content,metadata_json=excluded.metadata_json,created_at=excluded.created_at""",
                (
                    pid,
                    row["id"],
                    ATLAS_VERSION,
                    digest,
                    content,
                    json.dumps(
                        {"entities": entities, "attachments": attachments}, ensure_ascii=False
                    ),
                    utcnow(),
                ),
            )
            created += 1
    return {"conversation_documents": created, "version": ATLAS_VERSION}
