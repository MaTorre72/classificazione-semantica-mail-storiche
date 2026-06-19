import csv
import sqlite3

from email_cluster.export.writers import export_cluster_review, write_markdown_report
from email_cluster.storage.database import init_db
from email_cluster.storage.repository import Repository


def test_manual_label_is_used_in_report_and_review_csv(tmp_path) -> None:
    db = tmp_path / "test.sqlite"
    review = tmp_path / "review.csv"
    report = tmp_path / "report.md"
    init_db(db)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.execute("INSERT INTO projects (id, name, created_at) VALUES (1, 'studio', 'now')")
    con.execute(
        """
        INSERT INTO clustering_runs (
            id, project_id, embedding_model_id, umap_parameters_json,
            hdbscan_parameters_json, started_at, status
        )
        VALUES (7, 1, 1, '{}', '{}', 'now', 'completed')
        """
    )
    con.execute(
        """
        INSERT INTO clusters (
            clustering_run_id, cluster_id, label_auto, label_manual, keywords_json,
            representative_email_ids_json, size, created_at
        )
        VALUES (7, 2, 'auto label', NULL, '["alpha"]', '[]', 12, 'now')
        """
    )
    con.commit()

    Repository(con).set_cluster_manual_label(7, 2, "Etichetta umana")
    csv_count = export_cluster_review(con, review, 7)
    report_count = write_markdown_report(con, report, 7)

    assert csv_count == 1
    assert report_count == 1
    rows = list(csv.DictReader(review.open(encoding="utf-8")))
    assert rows[0]["label_manual"] == "Etichetta umana"
    assert "Cluster 2 - Etichetta umana" in report.read_text(encoding="utf-8")
