from __future__ import annotations

import io
import json
import re
import sqlite3
import traceback as tb
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

import numpy as np

from email_cluster.models import CleanedText, ParsedEmail
from email_cluster.context.builder import SemanticContext


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


def _thread_key(subject: str | None, headers: dict[str, Any]) -> str:
    references = str(headers.get("References") or headers.get("In-Reply-To") or "").strip()
    if references:
        return references.split()[0].strip("<>")[:250]
    value = re.sub(r"^(?:(?:re|fw|fwd|r|i)\s*:\s*)+", "", subject or "", flags=re.I)
    return re.sub(r"\s+", " ", value).strip().lower()[:250]


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
        self, project_id: int, path: str, file_type: str, file_hash: str | None, status: str,
        *, file_size: int | None = None, modified_at: str | None = None,
        emails_found: int = 0, emails_imported: int = 0, errors_count: int = 0,
    ) -> int:
        self.con.execute(
            """
            INSERT INTO source_files (
                project_id, path, file_type, file_hash, imported_at, status, file_size, modified_at,
                emails_found, emails_imported, errors_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, path) DO UPDATE SET
                file_hash = excluded.file_hash,
                imported_at = excluded.imported_at,
                status = excluded.status
                , file_size = excluded.file_size, modified_at = excluded.modified_at,
                emails_found = excluded.emails_found, emails_imported = excluded.emails_imported,
                errors_count = excluded.errors_count
            """,
            (project_id, path, file_type, file_hash, utcnow(), status, file_size, modified_at,
             emails_found, emails_imported, errors_count),
        )
        row = self.con.execute(
            "SELECT id FROM source_files WHERE project_id = ? AND path = ?", (project_id, path)
        ).fetchone()
        return int(row["id"])

    def source_file_is_current(self, project_id: int, path: str, file_hash: str) -> bool:
        row = self.con.execute(
            "SELECT file_hash, status FROM source_files WHERE project_id = ? AND path = ?",
            (project_id, path),
        ).fetchone()
        return bool(row and row["file_hash"] == file_hash and row["status"] == "ok")

    def insert_email(self, project_id: int, source_file_id: int, parsed: ParsedEmail) -> int | None:
        try:
            cur = self.con.execute(
                """
                INSERT INTO emails (
                    project_id, source_file_id, original_message_id, message_hash, subject,
                    sender, recipients, cc, bcc, sent_at, imported_at, raw_headers_json,
                    body_plain, body_html, body_extracted_text, has_attachments, parse_status,
                    thread_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    _thread_key(parsed.subject, parsed.raw_headers),
                ),
            )
        except sqlite3.IntegrityError:
            return None
        email_id = int(cur.lastrowid)
        for attachment in parsed.attachments:
            self.con.execute(
                """
                INSERT INTO attachments
                    (email_id, filename, mime_type, size_bytes, sha256, extraction_status,
                     attachment_type, attachment_keywords_json, extracted_text, text_excerpt,
                     extraction_error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email_id,
                    attachment.filename,
                    attachment.mime_type,
                    attachment.size_bytes,
                    attachment.sha256,
                    attachment.extraction_status,
                    attachment.attachment_type,
                    json_dumps(attachment.attachment_keywords),
                    attachment.extracted_text,
                    attachment.text_excerpt,
                    attachment.extraction_error,
                    utcnow(),
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
                email_id, language, clean_text, cleaning_version, cleaning_flags_json, created_at,
                semantic_text, subject_clean, body_current_message_clean, message_type,
                quality_score, excluded_from_main_clustering, exclusion_reason,
                current_message_text, quoted_thread_text, forwarded_text, signature_text,
                disclaimer_text, automatic_footer_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cleaned.email_id,
                cleaned.language,
                cleaned.clean_text,
                cleaned.cleaning_version,
                json_dumps(cleaned.cleaning_flags),
                utcnow(),
                cleaned.semantic_text,
                cleaned.subject_clean,
                cleaned.body_current_message_clean,
                cleaned.message_type,
                cleaned.quality_score,
                1 if cleaned.excluded_from_main_clustering else 0,
                cleaned.exclusion_reason,
                cleaned.body_current_message_clean,
                cleaned.quoted_thread_text,
                cleaned.forwarded_text,
                cleaned.signature_text,
                cleaned.disclaimer_text,
                cleaned.automatic_footer_text,
            ),
        )
        if cur.lastrowid:
            return int(cur.lastrowid)
        row = self.con.execute(
            "SELECT id FROM clean_texts WHERE email_id = ? AND cleaning_version = ?",
            (cleaned.email_id, cleaned.cleaning_version),
        ).fetchone()
        return int(row["id"])

    def emails_needing_context(self, project_id: int, context_version: str) -> list[sqlite3.Row]:
        return list(self.con.execute("""
            SELECT e.*, c.subject_clean, c.current_message_text, c.body_current_message_clean,
                   c.quoted_thread_text, c.message_type, c.quality_score
            FROM emails e
            JOIN clean_texts c ON c.id = (
                SELECT MAX(c2.id) FROM clean_texts c2 WHERE c2.email_id = e.id
            )
            LEFT JOIN semantic_contexts sc
                ON sc.email_id = e.id AND sc.context_version = ?
            WHERE e.project_id = ? AND sc.id IS NULL
            ORDER BY e.id
        """, (context_version, project_id)))

    def attachment_rows(self, email_id: int) -> list[sqlite3.Row]:
        return list(self.con.execute("SELECT * FROM attachments WHERE email_id = ?", (email_id,)))

    def insert_semantic_context(self, context: SemanticContext) -> int:
        self.con.execute("""
            INSERT OR IGNORE INTO semantic_contexts (
                email_id, context_version, message_type, message_type_confidence, context_strategy,
                thread_context_summary, attachment_summary, semantic_summary, action_required,
                topic_label, candidate_tags_json, semantic_text_for_embedding, quality_score,
                excluded_from_main_clustering, exclusion_reason, llm_used, llm_model,
                llm_parameters_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            context.email_id, context.context_version, context.message_type,
            context.message_type_confidence, context.context_strategy,
            context.thread_context_summary, context.attachment_summary, context.semantic_summary,
            context.action_required, context.topic_label, json_dumps(context.candidate_tags or []),
            context.semantic_text_for_embedding, context.quality_score,
            int(context.excluded_from_main_clustering), context.exclusion_reason,
            int(context.llm_used), context.llm_model, json_dumps(context.llm_parameters or {}), utcnow(),
        ))
        row = self.con.execute(
            "SELECT id FROM semantic_contexts WHERE email_id = ? AND context_version = ?",
            (context.email_id, context.context_version),
        ).fetchone()
        return int(row["id"])

    def semantic_contexts_without_embedding(
        self, project_id: int, model_id: int, limit: int | None = None,
    ) -> list[sqlite3.Row]:
        sql = """
            SELECT sc.* FROM semantic_contexts sc
            JOIN emails e ON e.id = sc.email_id
            LEFT JOIN semantic_embeddings se
                ON se.semantic_context_id = sc.id AND se.model_id = ?
            WHERE e.project_id = ? AND se.id IS NULL
              AND sc.excluded_from_main_clustering = 0
              AND length(sc.semantic_text_for_embedding) > 0
              AND sc.id = (SELECT MAX(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=sc.email_id)
            ORDER BY sc.id
        """
        params: list[Any] = [model_id, project_id]
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        return list(self.con.execute(sql, params))

    def insert_semantic_embedding(self, email_id: int, context_id: int, model_id: int, vector: np.ndarray) -> None:
        self.con.execute("""
            INSERT OR IGNORE INTO semantic_embeddings
                (email_id, semantic_context_id, model_id, embedding, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (email_id, context_id, model_id, embedding_to_blob(vector), utcnow()))

    def semantic_embeddings_for_project(self, project_id: int) -> list[sqlite3.Row]:
        return list(self.con.execute("""
            SELECT se.*, sc.semantic_text_for_embedding AS semantic_text,
                   e.subject, e.sender
            FROM semantic_embeddings se
            JOIN semantic_contexts sc ON sc.id = se.semantic_context_id
            JOIN emails e ON e.id = se.email_id
            WHERE e.project_id = ? AND sc.excluded_from_main_clustering = 0
              AND sc.id = (SELECT MAX(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=sc.email_id)
            ORDER BY se.id
        """, (project_id,)))

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
            WHERE e.project_id = ? AND emb.id IS NULL
                AND c.excluded_from_main_clustering = 0 AND length(c.semantic_text) > 0
                AND c.id = (SELECT MAX(c3.id) FROM clean_texts c3 WHERE c3.email_id = c.email_id)
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

    def embeddings_for_project(
        self, project_id: int, *, min_chars: int = 1,
        message_types: list[str] | None = None, model_id: int | None = None,
    ) -> list[sqlite3.Row]:
        allowed = message_types or ["operational_email"]
        placeholders = ",".join("?" for _ in allowed)
        model_clause = "AND emb.model_id = ?" if model_id is not None else ""
        params: list[Any] = [project_id, min_chars, *allowed]
        if model_id is not None:
            params.append(model_id)
        return list(
            self.con.execute(
                f"""
                SELECT emb.*, c.clean_text, c.semantic_text, e.subject, e.sender
                FROM embeddings emb
                JOIN emails e ON e.id = emb.email_id
                JOIN clean_texts c ON c.id = emb.clean_text_id
                JOIN (
                    SELECT emb2.email_id, MAX(emb2.id) AS embedding_id
                    FROM embeddings emb2
                    JOIN clean_texts c2 ON c2.id = emb2.clean_text_id
                    WHERE c2.excluded_from_main_clustering = 0 AND length(c2.semantic_text) > 0
                    GROUP BY emb2.email_id
                ) latest ON latest.embedding_id = emb.id
                WHERE e.project_id = ?
                    AND c.excluded_from_main_clustering = 0
                    AND length(c.semantic_text) > 0
                    AND length(c.semantic_text) >= ?
                    AND c.message_type IN ({placeholders})
                    {model_clause}
                    AND c.id = (
                        SELECT MAX(c3.id) FROM clean_texts c3 WHERE c3.email_id = c.email_id
                    )
                ORDER BY emb.id
                """,
                params,
            )
        )

    def create_clustering_run(
        self, project_id: int, model_id: int, umap_params: dict[str, Any], hdbscan_params: dict[str, Any],
        profile_name: str | None = None,
    ) -> int:
        cur = self.con.execute(
            """
            INSERT INTO clustering_runs (
                project_id, embedding_model_id, umap_parameters_json,
                hdbscan_parameters_json, started_at, status, profile_name, random_state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, model_id, json_dumps(umap_params), json_dumps(hdbscan_params), utcnow(), "running", profile_name, umap_params.get("random_state")),
        )
        return int(cur.lastrowid)

    def complete_clustering_run(self, run_id: int, status: str = "completed") -> None:
        self.con.execute(
            "UPDATE clustering_runs SET completed_at = ?, status = ? WHERE id = ?",
            (utcnow(), status, run_id),
        )

    def save_clustering_metrics(self, run_id: int, metrics: dict[str, Any], warnings: list[str]) -> None:
        fields = list(metrics) + ["warnings_json"]
        values = [metrics[name] for name in metrics] + [json_dumps(warnings)]
        assignments = ", ".join(f"{name} = ?" for name in fields)
        self.con.execute(f"UPDATE clustering_runs SET {assignments} WHERE id = ?", (*values, run_id))

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
        recurring_subjects: list[str] | None = None,
        recurring_senders: list[str] | None = None,
        mean_probability: float | None = None,
        confidence_label: float | None = None,
    ) -> None:
        self.con.execute(
            """
            INSERT OR REPLACE INTO clusters (
                clustering_run_id, cluster_id, label_auto, keywords_json,
                representative_email_ids_json, size, coherence_score, density_score, created_at,
                recurring_subjects_json, recurring_senders_json, mean_probability, confidence_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json_dumps(recurring_subjects or []),
                json_dumps(recurring_senders or []),
                mean_probability,
                confidence_label,
            ),
        )

    def set_cluster_manual_label(self, run_id: int, cluster_id: int, label: str | None) -> None:
        cur = self.con.execute(
            """
            UPDATE clusters
            SET label_manual = ?
            WHERE clustering_run_id = ? AND cluster_id = ?
            """,
            (label, run_id, cluster_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Cluster {cluster_id} not found in run {run_id}")
