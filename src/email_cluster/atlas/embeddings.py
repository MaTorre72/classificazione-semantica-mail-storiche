from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

from pathlib import Path
from typing import Any


from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, utcnow


def embed_documents(
    db_path: Path, project: str, model_name: str, batch_size: int = 16, low_power: bool = False
) -> dict[str, Any]:
    from email_cluster.embeddings.engine import EmbeddingEngine
    from email_cluster.storage.repository import embedding_to_blob
    import time

    init_db(db_path)
    engine = EmbeddingEngine(model_name)
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        con.execute("""CREATE TABLE IF NOT EXISTS atlas_embedding_cache(id INTEGER PRIMARY KEY AUTOINCREMENT,semantic_document_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,content_hash TEXT NOT NULL,embedding BLOB NOT NULL,created_at TEXT NOT NULL,UNIQUE(semantic_document_id,model_name,content_hash))""")
        docs = list(
            con.execute(
                """SELECT d.* FROM atlas_semantic_documents d WHERE d.project_id=? AND d.document_level='conversation'
            AND NOT EXISTS(SELECT 1 FROM atlas_embedding_cache e WHERE e.semantic_document_id=d.id AND e.model_name=? AND e.content_hash=d.content_hash)""",
                (pid, model_name),
            )
        )
        done = 0
        for start in range(0, len(docs), batch_size):
            for doc in docs[start : start + batch_size]:
                vector = engine.embed_email(doc["content"], 2000, 200)
                con.execute(
                    "INSERT OR IGNORE INTO atlas_embedding_cache(semantic_document_id,model_name,content_hash,embedding,created_at) VALUES(?,?,?,?,?)",
                    (
                        doc["id"],
                        model_name,
                        doc["content_hash"],
                        embedding_to_blob(vector),
                        utcnow(),
                    ),
                )
                done += 1
            con.commit()
            if low_power:
                time.sleep(1)
    return {"embedded": done, "cached": max(len(docs) - done, 0), "model": model_name}
