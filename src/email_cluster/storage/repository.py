from __future__ import annotations

import io
import json
import sqlite3
import traceback as tb
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import numpy as np

from email_cluster.models import CleanedText, ParsedEmail


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def embedding_to_blob(vector: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, vector.astype("float32"), allow_pickle=False)
    return buffer.getvalue()


def blob_to_embedding(blob: bytes) -> np.ndarray:
    return np.load(io.BytesIO(blob), allow_pickle=False)


class Repository:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def get_or_create_project(self, name: str, description: str | None = None) -> int:
        row = self.con.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
        if row:
            return int(row["id"])
        cur = self.con.execute(
            "INSERT INTO projects (name, description, created_at) VALUES (?, ?, ?)",
            (name, description, utcnow()),
        )
        return int(cur.lastrowid)

    def project_id(self, name: str) -> int:
        row = self.con.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
        if not row:
            raise ValueError(f"Project not found: {name}")
        return int(row["id"])

    def upsert_source_file(
        self, project_id: int, path: str, file_type: str, file_hash: str | None, status: str
    ) -> int:
        self.con.execute(
            """
            INSERT INTO source_files (project_id, path, file_type, file_hash, imported_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, path) DO UPDATE SET
                file_hash = excluded.file_hash,
                imported_at = excluded.imported_at,
                status = excluded.status
            """,
            (project_id, path, file_type, file_hash, utcnow(), status),
        )
        row = self.con.execute(
            "SELECT id FROM source_files WHERE project_id = ? AND path = ?", (project_id, path)
        ).fetchone()
        return int(row["id"])

    def insert_email(self, project_id: int, source_file_id: int, parsed: ParsedEmail) -> int | None:
        try:
            cur = self.con.execute(
                """
                INSERT INTO emails (
                    project_id, source_file_id, original_message_id, message_hash, subject,
                    sender, recipients, cc, bcc, sent_at, imported_at, raw_headers_json,
                    body_plain, body_html, body_extracted_text, has_attachments, parse_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    source_file_id,
                    parsed.message_id,
                    parsed.message_hash,
                    parsed.subject,
                    parsed.sender,
                    json_dumps(parsed.recipients),
                    json_dumps(parsed.cc),
                    json_dumps(parsed.bcc),
                    parsed.sent_at.isoformat() if parsed.sent_at else None,
                    utcnow(),
                    json_dumps(parsed.raw_headers),
                    parsed.body_plain,
                    parsed.body_html,
                    parsed.body_extracted_text,
                    1 if parsed.attachments else 0,
                    "ok",
                ),
            )
        except sqlite3.IntegrityError:
            return None
        email_id = int(cur.lastrowid)
        for attachment in parsed.attachments:
            self.con.execute(
                """
                INSERT INTO attachments
                    (email_id, filename, mime_type, size_bytes, sha256, extraction_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    email_id,
                    attachment.filename,
                    attachment.mime_type,
                    attachment.size_bytes,
                    attachment.sha256,
                    "metadata_only",
                ),
            )
        return email_id

    def record_error(
        self,
        module: str,
        exc: BaseException,
        project_id: int | None = None,
        source_file_id: int | None = None,
        email_id: int | None = None,
    ) -> None:
        self.con.execute(
            """
            INSERT INTO errors (
                project_id, source_file_id, email_id, module, error_type,
                error_message, traceback, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                source_file_id,
                email_id,
                module,
                type(exc).__name__,
                str(exc),
                "".join(tb.format_exception(exc)),
                utcnow(),
            ),
        )

    def emails_needing_cleaning(self, project_id: int, cleaning_version: str) -> Iterable[sqlite3.Row]:
        return self.con.execute(
            """
            SELECT e.* FROM emails e
            LEFT JOIN clean_texts c
                ON c.email_id = e.id AND c.cleaning_version = ?
            WHERE e.project_id = ? AND c.id IS NULL
            ORDER BY e.id
            """,
            (cleaning_version, project_id),
        )

    def insert_clean_text(self, cleaned: CleanedText) -> int:
        cur = self.con.execute(
            """
            INSERT OR IGNORE INTO clean_texts (
                email_id, language, clean_text, cleaning_version, cleaning_flags_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cleaned.email_id,
                cleaned.language,
                cleaned.clean_text,
                cleaned.cleaning_version,
                json_dumps(cleaned.cleaning_flags),
                utcnow(),
            ),
        )
        if cur.lastrowid:
            return int(cur.lastrowid)
        row = self.con.execute(
            "SELECT id FROM clean_texts WHERE email_id = ? AND cleaning_version = ?",
            (cleaned.email_id, cleaned.cleaning_version),
        ).fetchone()
        return int(row["id"])

    def get_or_create_embedding_model(
        self, model_name: str, model_version: str | None, dimension: int, parameters: dict[str, Any]
    ) -> int:
        params = json_dumps(parameters)
        self.con.execute(
            """
            INSERT OR IGNORE INTO embedding_models (
                model_name, model_version, embedding_dimension, parameters_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (model_name, model_version, dimension, params, utcnow()),
        )
        row = self.con.execute(
            """
            SELECT id FROM embedding_models
            WHERE model_name = ? AND model_version IS ? AND embedding_dimension = ?
                AND parameters_json = ?
            """,
            (model_name, model_version, dimension, params),
        ).fetchone()
        return int(row["id"])

    def clean_texts_without_embedding(
        self, project_id: int, model_id: int, limit: int | None = None
    ) -> list[sqlite3.Row]:
        sql = """
            SELECT c.*, e.project_id FROM clean_texts c
            JOIN emails e ON e.id = c.email_id
            LEFT JOIN embeddings emb
                ON emb.clean_text_id = c.id AND emb.model_id = ?
            WHERE e.project_id = ? AND emb.id IS NULL AND length(c.clean_text) > 0
            ORDER BY c.id
        """
        params: tuple[Any, ...]
        if limit:
            sql += " LIMIT ?"
            params = (model_id, project_id, limit)
        else:
            params = (model_id, project_id)
        return list(self.con.execute(sql, params))

    def insert_embedding(
        self,
        email_id: int,
        clean_text_id: int,
        model_id: int,
        vector: np.ndarray,
        chunking_strategy: str,
        pooling_strategy: str,
    ) -> None:
        self.con.execute(
            """
            INSERT OR IGNORE INTO embeddings (
                email_id, clean_text_id, model_id, embedding, chunking_strategy,
                pooling_strategy, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email_id,
                clean_text_id,
                model_id,
                embedding_to_blob(vector),
                chunking_strategy,
                pooling_strategy,
                utcnow(),
            ),
        )

    def embeddings_for_project(self, project_id: int) -> list[sqlite3.Row]:
        return list(
            self.con.execute(
                """
                SELECT emb.*, c.clean_text, e.subject, e.sender
                FROM embeddings emb
                JOIN emails e ON e.id = emb.email_id
                JOIN clean_texts c ON c.id = emb.clean_text_id
                WHERE e.project_id = ?
                ORDER BY emb.id
                """,
                (project_id,),
            )
        )

    def create_clustering_run(
        self, project_id: int, model_id: int, umap_params: dict[str, Any], hdbscan_params: dict[str, Any]
    ) -> int:
        cur = self.con.execute(
            """
            INSERT INTO clustering_runs (
                project_id, embedding_model_id, umap_parameters_json,
                hdbscan_parameters_json, started_at, status
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (project_id, model_id, json_dumps(umap_params), json_dumps(hdbscan_params), utcnow(), "running"),
        )
        return int(cur.lastrowid)

    def complete_clustering_run(self, run_id: int, status: str = "completed") -> None:
        self.con.execute(
            "UPDATE clustering_runs SET completed_at = ?, status = ? WHERE id = ?",
            (utcnow(), status, run_id),
        )

    def insert_email_cluster(
        self, run_id: int, email_id: int, cluster_id: int, probability: float | None
    ) -> None:
        self.con.execute(
            """
            INSERT OR REPLACE INTO email_clusters (
                clustering_run_id, email_id, cluster_id, probability, is_noise
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_id, email_id, cluster_id, probability, 1 if cluster_id == -1 else 0),
        )

    def insert_cluster_summary(
        self,
        run_id: int,
        cluster_id: int,
        label_auto: str,
        keywords: list[str],
        representative_email_ids: list[int],
        size: int,
        coherence_score: float | None = None,
        density_score: float | None = None,
    ) -> None:
        self.con.execute(
            """
            INSERT OR REPLACE INTO clusters (
                clustering_run_id, cluster_id, label_auto, keywords_json,
                representative_email_ids_json, size, coherence_score, density_score, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                cluster_id,
                label_auto,
                json_dumps(keywords),
                json_dumps(representative_email_ids),
                size,
                coherence_score,
                density_score,
                utcnow(),
            ),
        )

