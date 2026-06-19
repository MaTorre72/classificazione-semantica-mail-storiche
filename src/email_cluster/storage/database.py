from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

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
    imported_at TEXT NOT NULL,
    status TEXT NOT NULL,
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
    created_at TEXT NOT NULL,
    UNIQUE(email_id, cleaning_version),
    FOREIGN KEY(email_id) REFERENCES emails(id)
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
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db(db_path: Path) -> None:
    with connect(db_path) as con:
        con.executescript(SCHEMA_SQL)
        _migrate_clean_texts(con)
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
    }
    for name, declaration in additions.items():
        if name not in columns:
            con.execute(f"ALTER TABLE clean_texts ADD COLUMN {name} {declaration}")


def _migrate_table(con: sqlite3.Connection, table: str, additions: dict[str, str]) -> None:
    columns = {row["name"] for row in con.execute(f"PRAGMA table_info({table})")}
    for name, declaration in additions.items():
        if name not in columns:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")
