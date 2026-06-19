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

