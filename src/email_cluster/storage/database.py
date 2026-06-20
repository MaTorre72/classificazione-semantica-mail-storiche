from __future__ import annotations

import sqlite3
import shutil
from datetime import datetime
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_hash TEXT,
    file_size INTEGER,
    modified_at TEXT,
    imported_at TEXT NOT NULL,
    status TEXT NOT NULL,
    emails_found INTEGER DEFAULT 0,
    emails_imported INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,
    UNIQUE(project_id, path),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    source_file_id INTEGER,
    original_message_id TEXT,
    message_hash TEXT NOT NULL UNIQUE,
    subject TEXT,
    sender TEXT,
    recipients TEXT,
    cc TEXT,
    bcc TEXT,
    sent_at TEXT,
    imported_at TEXT NOT NULL,
    raw_headers_json TEXT,
    body_plain TEXT,
    body_html TEXT,
    body_extracted_text TEXT,
    has_attachments INTEGER DEFAULT 0,
    parse_status TEXT NOT NULL,
    import_run_id INTEGER,
    thread_key TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(source_file_id) REFERENCES source_files(id)
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    filename TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    sha256 TEXT,
    extracted_text TEXT,
    extraction_status TEXT,
    attachment_type TEXT,
    attachment_keywords_json TEXT,
    text_excerpt TEXT,
    extraction_error TEXT,
    created_at TEXT,
    FOREIGN KEY(email_id) REFERENCES emails(id)
);

CREATE TABLE IF NOT EXISTS clean_texts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    language TEXT,
    clean_text TEXT NOT NULL,
    cleaning_version TEXT NOT NULL,
    cleaning_flags_json TEXT,
    semantic_text TEXT NOT NULL DEFAULT '',
    subject_clean TEXT NOT NULL DEFAULT '',
    body_current_message_clean TEXT NOT NULL DEFAULT '',
    message_type TEXT NOT NULL DEFAULT 'operational_email',
    quality_score REAL NOT NULL DEFAULT 0,
    excluded_from_main_clustering INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT,
    current_message_text TEXT,
    quoted_thread_text TEXT,
    forwarded_text TEXT,
    signature_text TEXT,
    disclaimer_text TEXT,
    automatic_footer_text TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(email_id, cleaning_version),
    FOREIGN KEY(email_id) REFERENCES emails(id)
);

CREATE TABLE IF NOT EXISTS semantic_contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    context_version TEXT NOT NULL,
    message_type TEXT NOT NULL,
    message_type_confidence REAL NOT NULL DEFAULT 0,
    context_strategy TEXT NOT NULL,
    thread_context_summary TEXT,
    attachment_summary TEXT,
    semantic_summary TEXT,
    action_required TEXT,
    topic_label TEXT,
    candidate_tags_json TEXT,
    semantic_text_for_embedding TEXT NOT NULL,
    quality_score REAL NOT NULL DEFAULT 0,
    excluded_from_main_clustering INTEGER NOT NULL DEFAULT 0,
    exclusion_reason TEXT,
    llm_used INTEGER NOT NULL DEFAULT 0,
    llm_model TEXT,
    llm_parameters_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(email_id, context_version),
    FOREIGN KEY(email_id) REFERENCES emails(id)
);

CREATE TABLE IF NOT EXISTS semantic_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    semantic_context_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(semantic_context_id, model_id),
    FOREIGN KEY(email_id) REFERENCES emails(id),
    FOREIGN KEY(semantic_context_id) REFERENCES semantic_contexts(id),
    FOREIGN KEY(model_id) REFERENCES embedding_models(id)
);

CREATE TABLE IF NOT EXISTS embedding_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    model_version TEXT,
    embedding_dimension INTEGER NOT NULL,
    parameters_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(model_name, model_version, embedding_dimension, parameters_json)
);

CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    clean_text_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    chunking_strategy TEXT,
    pooling_strategy TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(clean_text_id, model_id),
    FOREIGN KEY(email_id) REFERENCES emails(id),
    FOREIGN KEY(clean_text_id) REFERENCES clean_texts(id),
    FOREIGN KEY(model_id) REFERENCES embedding_models(id)
);

CREATE TABLE IF NOT EXISTS processing_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    parameters_json TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    notes TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS clustering_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    embedding_model_id INTEGER NOT NULL,
    umap_parameters_json TEXT NOT NULL,
    hdbscan_parameters_json TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    profile_name TEXT,
    total_emails_considered INTEGER,
    excluded_before_clustering INTEGER,
    total_clusters INTEGER,
    total_noise INTEGER,
    noise_ratio REAL,
    largest_cluster_size INTEGER,
    largest_cluster_ratio REAL,
    median_cluster_size REAL,
    mean_cluster_size REAL,
    min_cluster_size INTEGER,
    max_cluster_size INTEGER,
    number_of_small_clusters INTEGER,
    number_of_large_clusters INTEGER,
    silhouette_score REAL,
    davies_bouldin_score REAL,
    calinski_harabasz_score REAL,
    mean_cluster_probability REAL,
    low_confidence_assignments INTEGER,
    random_state INTEGER,
    warnings_json TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(embedding_model_id) REFERENCES embedding_models(id)
);

CREATE TABLE IF NOT EXISTS email_clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clustering_run_id INTEGER NOT NULL,
    email_id INTEGER NOT NULL,
    cluster_id INTEGER NOT NULL,
    probability REAL,
    is_noise INTEGER DEFAULT 0,
    UNIQUE(clustering_run_id, email_id),
    FOREIGN KEY(clustering_run_id) REFERENCES clustering_runs(id),
    FOREIGN KEY(email_id) REFERENCES emails(id)
);

CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clustering_run_id INTEGER NOT NULL,
    cluster_id INTEGER NOT NULL,
    label_auto TEXT,
    label_manual TEXT,
    keywords_json TEXT,
    representative_email_ids_json TEXT,
    size INTEGER,
    coherence_score REAL,
    density_score REAL,
    recurring_subjects_json TEXT,
    recurring_senders_json TEXT,
    mean_probability REAL,
    confidence_label REAL,
    created_at TEXT NOT NULL,
    UNIQUE(clustering_run_id, cluster_id),
    FOREIGN KEY(clustering_run_id) REFERENCES clustering_runs(id)
);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    source_file_id INTEGER,
    email_id INTEGER,
    module TEXT NOT NULL,
    error_type TEXT,
    error_message TEXT,
    traceback TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,
    clustering_run_id INTEGER NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL, completed_at TEXT, notes TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(clustering_run_id) REFERENCES clustering_runs(id)
);

CREATE TABLE IF NOT EXISTS cluster_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, review_session_id INTEGER NOT NULL,
    clustering_run_id INTEGER NOT NULL, cluster_id INTEGER NOT NULL, auto_label TEXT,
    llm_label TEXT, human_label TEXT, final_label TEXT, review_status TEXT NOT NULL DEFAULT 'pending',
    human_notes TEXT, llm_summary TEXT, llm_confidence REAL, suggested_action TEXT,
    review_priority REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(review_session_id, cluster_id),
    FOREIGN KEY(review_session_id) REFERENCES review_sessions(id)
);

CREATE TABLE IF NOT EXISTS email_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, review_session_id INTEGER NOT NULL, email_id INTEGER NOT NULL,
    clustering_run_id INTEGER NOT NULL, original_cluster_id INTEGER, suggested_cluster_id INTEGER,
    human_cluster_id INTEGER, auto_message_type TEXT, llm_message_type TEXT, human_message_type TEXT,
    human_topic_label TEXT, human_notes TEXT, review_status TEXT NOT NULL DEFAULT 'pending',
    review_priority REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(review_session_id, email_id), FOREIGN KEY(review_session_id) REFERENCES review_sessions(id),
    FOREIGN KEY(email_id) REFERENCES emails(id)
);

CREATE TABLE IF NOT EXISTS taxonomy_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, label TEXT NOT NULL,
    description TEXT, parent_label_id INTEGER, label_type TEXT NOT NULL DEFAULT 'altro',
    source TEXT NOT NULL DEFAULT 'human', active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(project_id, label),
    FOREIGN KEY(project_id) REFERENCES projects(id), FOREIGN KEY(parent_label_id) REFERENCES taxonomy_labels(id)
);

CREATE TABLE IF NOT EXISTS label_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT, taxonomy_label_id INTEGER NOT NULL, email_id INTEGER NOT NULL,
    example_type TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(taxonomy_label_id, email_id, example_type),
    FOREIGN KEY(taxonomy_label_id) REFERENCES taxonomy_labels(id), FOREIGN KEY(email_id) REFERENCES emails(id)
);

CREATE TABLE IF NOT EXISTS label_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, label_id INTEGER NOT NULL,
    rule_type TEXT NOT NULL, pattern TEXT NOT NULL, target_field TEXT, priority INTEGER DEFAULT 100,
    active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id), FOREIGN KEY(label_id) REFERENCES taxonomy_labels(id)
);

CREATE TABLE IF NOT EXISTS llm_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, run_type TEXT NOT NULL, backend TEXT,
    model TEXT, prompt_version TEXT, started_at TEXT NOT NULL, completed_at TEXT, status TEXT NOT NULL,
    parameters_json TEXT, FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS llm_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT, input_hash TEXT NOT NULL, model TEXT NOT NULL,
    prompt_version TEXT NOT NULL, input_excerpt TEXT, raw_output TEXT, parsed_output_json TEXT,
    status TEXT NOT NULL, error TEXT, elapsed_ms INTEGER, created_at TEXT NOT NULL,
    UNIQUE(input_hash, model, prompt_version)
);

CREATE TABLE IF NOT EXISTS llm_email_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, email_id INTEGER NOT NULL, llm_run_id INTEGER NOT NULL,
    suggestion_json TEXT NOT NULL, confidence REAL, created_at TEXT NOT NULL,
    FOREIGN KEY(email_id) REFERENCES emails(id), FOREIGN KEY(llm_run_id) REFERENCES llm_runs(id)
);

CREATE TABLE IF NOT EXISTS llm_cluster_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, clustering_run_id INTEGER NOT NULL, cluster_id INTEGER NOT NULL,
    llm_run_id INTEGER NOT NULL, suggestion_json TEXT NOT NULL, confidence REAL, created_at TEXT NOT NULL,
    FOREIGN KEY(llm_run_id) REFERENCES llm_runs(id)
);

CREATE TABLE IF NOT EXISTS review_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, review_session_id INTEGER, clustering_run_id INTEGER NOT NULL,
    cluster_id INTEGER, suggestion_type TEXT NOT NULL, suggestion_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL,
    FOREIGN KEY(review_session_id) REFERENCES review_sessions(id)
);

CREATE TABLE IF NOT EXISTS operational_contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL,
    source_clustering_run_id INTEGER, source_cluster_id INTEGER,
    name TEXT NOT NULL, description TEXT, context_type TEXT NOT NULL,
    macro_category TEXT NOT NULL, client_or_entity TEXT, technical_domain TEXT,
    practice_or_topic TEXT, why_grouped TEXT, suggested_user_action TEXT,
    source TEXT NOT NULL DEFAULT 'auto', confidence REAL NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'pending', review_priority REAL NOT NULL DEFAULT 0,
    llm_used INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(project_id, source_clustering_run_id, source_cluster_id, macro_category),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS email_context_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT, email_id INTEGER NOT NULL,
    operational_context_id INTEGER NOT NULL, macro_category TEXT NOT NULL,
    assignment_source TEXT NOT NULL DEFAULT 'auto', confidence REAL NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'pending', reason TEXT,
    is_suspicious INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    UNIQUE(email_id, operational_context_id), FOREIGN KEY(email_id) REFERENCES emails(id),
    FOREIGN KEY(operational_context_id) REFERENCES operational_contexts(id)
);

CREATE TABLE IF NOT EXISTS context_review_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, operational_context_id INTEGER NOT NULL,
    email_id INTEGER, action TEXT NOT NULL, old_value_json TEXT, new_value_json TEXT,
    notes TEXT, created_at TEXT NOT NULL,
    FOREIGN KEY(operational_context_id) REFERENCES operational_contexts(id),
    FOREIGN KEY(email_id) REFERENCES emails(id)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(db_path: Path, backup_before_migration: bool = True) -> None:
    if db_path.exists() and backup_before_migration and _needs_migration(db_path, 4):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(db_path, db_path.with_suffix(db_path.suffix + f".backup-{timestamp}"))
    with connect(db_path) as con:
        con.executescript(SCHEMA_SQL)
        _migrate_clean_texts(con)
        _migrate_table(con, "source_files", {
            "file_size": "INTEGER", "modified_at": "TEXT", "emails_found": "INTEGER DEFAULT 0",
            "emails_imported": "INTEGER DEFAULT 0", "errors_count": "INTEGER DEFAULT 0",
        })
        _migrate_table(con, "emails", {"import_run_id": "INTEGER", "thread_key": "TEXT"})
        _migrate_table(con, "attachments", {
            "attachment_type": "TEXT", "attachment_keywords_json": "TEXT", "text_excerpt": "TEXT",
            "extraction_error": "TEXT", "created_at": "TEXT",
        })
        _migrate_table(con, "clustering_runs", {
            "profile_name": "TEXT", "total_emails_considered": "INTEGER", "excluded_before_clustering": "INTEGER",
            "total_clusters": "INTEGER", "total_noise": "INTEGER", "noise_ratio": "REAL",
            "largest_cluster_size": "INTEGER", "largest_cluster_ratio": "REAL", "median_cluster_size": "REAL",
            "mean_cluster_size": "REAL", "min_cluster_size": "INTEGER", "max_cluster_size": "INTEGER",
            "number_of_small_clusters": "INTEGER", "number_of_large_clusters": "INTEGER",
            "silhouette_score": "REAL", "davies_bouldin_score": "REAL", "calinski_harabasz_score": "REAL",
            "mean_cluster_probability": "REAL", "low_confidence_assignments": "INTEGER",
            "random_state": "INTEGER", "warnings_json": "TEXT",
        })
        _migrate_table(con, "clusters", {
            "recurring_subjects_json": "TEXT", "recurring_senders_json": "TEXT",
            "mean_probability": "REAL", "confidence_label": "REAL",
        })
        con.execute("INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('schema_version', '4')")


def _migrate_clean_texts(con: sqlite3.Connection) -> None:
    columns = {row["name"] for row in con.execute("PRAGMA table_info(clean_texts)")}
    additions = {
        "semantic_text": "TEXT NOT NULL DEFAULT ''",
        "subject_clean": "TEXT NOT NULL DEFAULT ''",
        "body_current_message_clean": "TEXT NOT NULL DEFAULT ''",
        "message_type": "TEXT NOT NULL DEFAULT 'operational_email'",
        "quality_score": "REAL NOT NULL DEFAULT 0",
        "excluded_from_main_clustering": "INTEGER NOT NULL DEFAULT 0",
        "exclusion_reason": "TEXT",
        "current_message_text": "TEXT",
        "quoted_thread_text": "TEXT",
        "forwarded_text": "TEXT",
        "signature_text": "TEXT",
        "disclaimer_text": "TEXT",
        "automatic_footer_text": "TEXT",
    }
    for name, declaration in additions.items():
        if name not in columns:
            con.execute(f"ALTER TABLE clean_texts ADD COLUMN {name} {declaration}")


def _migrate_table(con: sqlite3.Connection, table: str, additions: dict[str, str]) -> None:
    columns = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
    for name, declaration in additions.items():
        if name not in columns:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def _needs_migration(db_path: Path, target: int) -> bool:
    try:
        with sqlite3.connect(db_path) as con:
            row = con.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            return row is None or int(row[0]) < target
    except sqlite3.Error:
        return True
