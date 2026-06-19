import sqlite3

from email_cluster.export.writers import export_emails
from email_cluster.storage.database import init_db


def test_export_uses_latest_clean_text_version(tmp_path) -> None:
    db = tmp_path / "test.sqlite"
    output = tmp_path / "emails.csv"
    init_db(db)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.execute(
        "INSERT INTO projects (id, name, created_at) VALUES (1, 'studio', 'now')"
    )
    con.execute(
        """
        INSERT INTO emails (
            id, project_id, message_hash, imported_at, body_extracted_text, parse_status
        )
        VALUES (1, 1, 'hash', 'now', 'raw', 'ok')
        """
    )
    con.execute(
        """
        INSERT INTO clean_texts (
            email_id, language, clean_text, cleaning_version, cleaning_flags_json, created_at
        )
        VALUES
            (1, 'it', 'vecchio', 'v0.1.0', '{}', 'now'),
            (1, 'it', 'nuovo', 'v0.2.0', '{}', 'later')
        """
    )
    con.commit()

    count = export_emails(con, output, "csv")

    assert count == 1
    text = output.read_text(encoding="utf-8")
    assert "nuovo" in text
    assert "vecchio" not in text
