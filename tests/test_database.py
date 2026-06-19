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
