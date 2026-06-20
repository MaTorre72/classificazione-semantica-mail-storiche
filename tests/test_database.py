from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository


def test_init_db_and_project_insert(tmp_path) -> None:
    db = tmp_path / "test.sqlite"
    init_db(db)

    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.get_or_create_project("studio")
        same_id = repo.get_or_create_project("studio")

    assert project_id == same_id


def test_init_db_migrates_existing_clean_texts_table(tmp_path) -> None:
    db = tmp_path / "old.sqlite"
    with connect(db) as con:
        con.execute("CREATE TABLE clean_texts (id INTEGER PRIMARY KEY, clean_text TEXT)")
    init_db(db)
    with connect(db) as con:
        columns = {row["name"] for row in con.execute("PRAGMA table_info(clean_texts)")}
    assert {"semantic_text", "message_type", "quality_score", "exclusion_reason"} <= columns


def test_clustering_diagnostic_columns_exist(tmp_path) -> None:
    db = tmp_path / "metrics.sqlite"
    init_db(db)
    with connect(db) as con:
        run_columns = {row["name"] for row in con.execute("PRAGMA table_info(clustering_runs)")}
        cluster_columns = {row["name"] for row in con.execute("PRAGMA table_info(clusters)")}
    assert {"profile_name", "noise_ratio", "warnings_json", "excluded_before_clustering"} <= run_columns
    assert {"recurring_subjects_json", "mean_probability", "confidence_label"} <= cluster_columns


def test_v2_schema_and_incremental_source_state(tmp_path) -> None:
    db = tmp_path / "v2.sqlite"
    init_db(db)
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.get_or_create_project("mail")
        repo.upsert_source_file(project_id, "inbox.mbox", "mbox", "abc", "ok", file_size=10)
        assert repo.source_file_is_current(project_id, "inbox.mbox", "abc")
        assert not repo.source_file_is_current(project_id, "inbox.mbox", "changed")
        version = con.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
        context_columns = {row["name"] for row in con.execute("PRAGMA table_info(semantic_contexts)")}
    assert version == "4"
    assert {"context_strategy", "semantic_text_for_embedding", "llm_used"} <= context_columns


def test_v3_review_tables_exist(tmp_path) -> None:
    db = tmp_path / "v3.sqlite"
    init_db(db)
    with connect(db) as con:
        tables = {row["name"] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"review_sessions", "cluster_reviews", "email_reviews", "taxonomy_labels", "label_examples", "label_rules", "llm_cache"} <= tables
    assert {"operational_contexts", "email_context_assignments", "context_review_events"} <= tables
