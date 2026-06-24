from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository


@dataclass
class ResetResult:
    project: str
    mode: str
    backup_path: str | None
    deleted: dict[str, int]
    reviews_preserved: bool
    final_atlas_preserved: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_database_backup(db_path: Path) -> Path:
    """Create a consistent SQLite backup before a risky operation."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = db_path.with_suffix(db_path.suffix + f".backup-{timestamp}")
    with connect(db_path) as source, connect(backup) as target:
        source.backup(target)
    return backup


def _delete(con, table: str, where: str, params: tuple[Any, ...]) -> int:
    cursor = con.execute(f"DELETE FROM {table} WHERE {where}", params)
    return max(cursor.rowcount, 0)


def reset_atlas_derived_data(
    db_path: Path,
    project: str,
    *,
    include_reviews: bool = False,
    include_final_atlas: bool = False,
    create_backup: bool = True,
) -> ResetResult:
    """Delete rebuildable Atlas data in dependency order with FK enforcement enabled."""
    init_db(db_path)
    backup = create_database_backup(db_path) if create_backup else None
    deleted: dict[str, int] = {}
    with connect(db_path) as con:
        if con.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("Le foreign key SQLite non sono attive")
        pid = Repository(con).project_id(project)
        con.execute("BEGIN IMMEDIATE")
        try:
            if include_reviews:
                deleted["atlas_review_decisions"] = _delete(
                    con, "atlas_review_decisions", "project_id=?", (pid,)
                )
            if include_final_atlas:
                deleted["atlas_examples"] = _delete(
                    con,
                    "atlas_examples",
                    "category_id IN (SELECT id FROM atlas_categories WHERE project_id=?)",
                    (pid,),
                )
                deleted["atlas_categories"] = _delete(
                    con, "atlas_categories", "project_id=?", (pid,)
                )

            deleted["atlas_candidate_conversations"] = _delete(
                con,
                "atlas_candidate_conversations",
                "candidate_id IN (SELECT id FROM atlas_candidate_categories WHERE project_id=?) "
                "OR conversation_id IN (SELECT id FROM atlas_conversations WHERE project_id=?)",
                (pid, pid),
            )
            deleted["atlas_candidate_categories"] = _delete(
                con, "atlas_candidate_categories", "project_id=?", (pid,)
            )

            cache_exists = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='atlas_embedding_cache'"
            ).fetchone()
            if cache_exists:
                deleted["atlas_embedding_cache"] = _delete(
                    con,
                    "atlas_embedding_cache",
                    "semantic_document_id IN (SELECT id FROM atlas_semantic_documents WHERE project_id=?)",
                    (pid,),
                )
            deleted["atlas_semantic_documents"] = _delete(
                con, "atlas_semantic_documents", "project_id=?", (pid,)
            )
            deleted["atlas_entity_mentions"] = _delete(
                con,
                "atlas_entity_mentions",
                "entity_id IN (SELECT id FROM atlas_entities WHERE project_id=?) "
                "OR conversation_id IN (SELECT id FROM atlas_conversations WHERE project_id=?)",
                (pid, pid),
            )
            deleted["atlas_entities"] = _delete(con, "atlas_entities", "project_id=?", (pid,))
            deleted["atlas_conversation_messages"] = _delete(
                con,
                "atlas_conversation_messages",
                "conversation_id IN (SELECT id FROM atlas_conversations WHERE project_id=?)",
                (pid,),
            )
            deleted["atlas_conversations"] = _delete(
                con, "atlas_conversations", "project_id=?", (pid,)
            )
            con.commit()
        except Exception:
            con.rollback()
            raise
    return ResetResult(
        project=project,
        mode="rebuild-derived",
        backup_path=str(backup) if backup else None,
        deleted=deleted,
        reviews_preserved=not include_reviews,
        final_atlas_preserved=not include_final_atlas,
    )


def reset_project(db_path: Path, project: str, *, confirm: bool = False) -> ResetResult:
    """Reset the complete Atlas layer only after explicit destructive confirmation."""
    if not confirm:
        raise ValueError("Azzera progetto richiede conferma esplicita: usa --confirm")
    result = reset_atlas_derived_data(
        db_path,
        project,
        include_reviews=True,
        include_final_atlas=True,
        create_backup=True,
    )
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        con.execute("BEGIN IMMEDIATE")
        email_ids = "SELECT id FROM emails WHERE project_id=?"
        run_ids = "SELECT id FROM clustering_runs WHERE project_id=?"
        review_ids = "SELECT id FROM review_sessions WHERE project_id=?"
        context_ids = "SELECT id FROM operational_contexts WHERE project_id=?"
        llm_run_ids = "SELECT id FROM llm_runs WHERE project_id=?"
        deletions = [
            (
                "context_review_events",
                f"email_id IN ({email_ids}) OR operational_context_id IN ({context_ids})",
                (pid, pid),
            ),
            ("review_suggestions", f"review_session_id IN ({review_ids})", (pid,)),
            ("cluster_reviews", f"review_session_id IN ({review_ids})", (pid,)),
            (
                "email_reviews",
                f"review_session_id IN ({review_ids}) OR email_id IN ({email_ids})",
                (pid, pid),
            ),
            (
                "email_context_assignments",
                f"operational_context_id IN ({context_ids}) OR email_id IN ({email_ids})",
                (pid, pid),
            ),
            (
                "label_examples",
                f"email_id IN ({email_ids}) OR taxonomy_label_id IN (SELECT id FROM taxonomy_labels WHERE project_id=?)",
                (pid, pid),
            ),
            (
                "email_labels",
                f"email_id IN ({email_ids}) OR label_id IN (SELECT id FROM taxonomy_labels WHERE project_id=?)",
                (pid, pid),
            ),
            (
                "llm_email_suggestions",
                f"llm_run_id IN ({llm_run_ids}) OR email_id IN ({email_ids})",
                (pid, pid),
            ),
            ("llm_cluster_suggestions", f"llm_run_id IN ({llm_run_ids})", (pid,)),
            (
                "semantic_embeddings",
                f"email_id IN ({email_ids}) OR semantic_context_id IN (SELECT id FROM semantic_contexts WHERE email_id IN ({email_ids}))",
                (pid, pid),
            ),
            (
                "embeddings",
                f"email_id IN ({email_ids}) OR clean_text_id IN (SELECT id FROM clean_texts WHERE email_id IN ({email_ids}))",
                (pid, pid),
            ),
            ("semantic_contexts", f"email_id IN ({email_ids})", (pid,)),
            ("clean_texts", f"email_id IN ({email_ids})", (pid,)),
            ("attachments", f"email_id IN ({email_ids})", (pid,)),
            (
                "email_clusters",
                f"email_id IN ({email_ids}) OR clustering_run_id IN ({run_ids})",
                (pid, pid),
            ),
            ("clusters", f"clustering_run_id IN ({run_ids})", (pid,)),
            ("review_sessions", "project_id=?", (pid,)),
            ("operational_contexts", "project_id=?", (pid,)),
            ("label_rules", "project_id=?", (pid,)),
            ("classification_rules", "project_id=?", (pid,)),
            ("classification_classes", "project_id=?", (pid,)),
            ("classification_areas", "project_id=?", (pid,)),
            ("llm_runs", "project_id=?", (pid,)),
            ("clustering_runs", "project_id=?", (pid,)),
            ("processing_runs", "project_id=?", (pid,)),
            ("archive_operations", "project_id=?", (pid,)),
            ("atlas_jobs", "project_id=?", (pid,)),
            ("errors", "project_id=?", (pid,)),
            ("emails", "project_id=?", (pid,)),
            ("source_files", "project_id=?", (pid,)),
        ]
        try:
            for table, where, params in deletions:
                result.deleted[table] = _delete(con, table, where, params)
            con.execute(
                "UPDATE taxonomy_labels SET parent_label_id=NULL WHERE project_id=?", (pid,)
            )
            result.deleted["taxonomy_labels"] = _delete(
                con, "taxonomy_labels", "project_id=?", (pid,)
            )
            result.deleted["projects"] = _delete(con, "projects", "id=?", (pid,))
            con.commit()
        except Exception:
            con.rollback()
            raise
    result.mode = "reset-project"
    return result
