from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient

from email_cluster.atlas.smoke import create_fixture, run_smoke_test
from email_cluster.atlas.study import (
    build_study_dataset,
    export_orange,
    export_study_pack,
    import_classification,
    _conversation_rows,
    _semantic_points,
)
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, embedding_to_blob, utcnow
from email_cluster.ui.app import create_app


REQUIRED_STUDY = {
    "conversations.csv",
    "conversation_messages.csv",
    "conversation_features.csv",
    "semantic_points.csv",
    "similarity_edges.csv",
    "entities.csv",
    "subjects.csv",
    "terms.csv",
    "attachments.csv",
    "candidate_clusters.csv",
    "candidate_categories.csv",
    "atlas_draft.csv",
    "classification_workspace.csv",
    "orange_readme.md",
    "orange_workflow_suggestions.md",
    "study_report.html",
    "nodes.csv",
    "edges.csv",
}
ORANGE_COLUMNS = {
    "conversation_id",
    "subject_normalized",
    "date_start",
    "date_end",
    "year",
    "month",
    "message_count",
    "incoming_count",
    "outgoing_count",
    "participants_count",
    "sender_domains",
    "main_domain",
    "main_subject",
    "main_entity",
    "probable_scope",
    "probable_subject",
    "probable_context",
    "technical_terms",
    "attachment_count",
    "attachment_types",
    "clean_summary",
    "semantic_text_short",
    "cluster_id",
    "cluster_label",
    "x",
    "y",
    "confidence",
    "warnings",
    "review_status",
}


def prepared(tmp_path: Path) -> tuple[Path, Path]:
    run_smoke_test(tmp_path)
    return tmp_path / "atlas.sqlite", tmp_path / "study"


def test_build_study_dataset_runs_the_complete_local_pipeline(tmp_path: Path) -> None:
    mail = create_fixture(tmp_path)
    result = build_study_dataset(
        mail, tmp_path / "builder.sqlite", "builder", tmp_path / "built-study"
    )
    assert REQUIRED_STUDY <= set(result["files"])
    assert result["conversations"] > 0


def test_study_pack_produces_documented_standard_csvs(tmp_path: Path) -> None:
    db, output = prepared(tmp_path)
    result = export_study_pack(db, "smoke", output)
    assert REQUIRED_STUDY <= set(result["files"])
    for name in REQUIRED_STUDY:
        assert (output / name).exists()
    for path in output.glob("*.csv"):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            assert csv.reader(handle).__next__()
    assert result["embeddings_used"] is False
    assert "TF-IDF" in result["warnings"][0]


def test_semantic_map_network_and_report_are_explorable(tmp_path: Path) -> None:
    db, output = prepared(tmp_path)
    export_study_pack(db, "smoke", output)
    with (output / "semantic_points.csv").open(encoding="utf-8-sig") as handle:
        points = list(csv.DictReader(handle))
    assert points and all(row["x"] and row["y"] for row in points)
    with (output / "nodes.csv").open(encoding="utf-8-sig") as handle:
        nodes = list(csv.DictReader(handle))
    with (output / "edges.csv").open(encoding="utf-8-sig") as handle:
        edges = list(csv.DictReader(handle))
    assert nodes and edges
    report = (output / "study_report.html").read_text(encoding="utf-8")
    assert "Distribuzioni temporali" in report
    assert "Mappa semantica 2D" in report
    assert "Cluster e categorie provvisorie" in report
    assert "Rete relazionale" in report


def test_semantic_points_stream_cached_embeddings_without_extra_list(tmp_path: Path) -> None:
    db = tmp_path / "study.sqlite"
    init_db(db)
    rows = [
        {
            "id": 101,
            "subject_normalized": "Primo tema",
            "semantic_text": "alpha beta",
            "analysis_text": "",
            "probable_scope": "Ambito A",
            "message_count": 1,
        },
        {
            "id": 102,
            "subject_normalized": "Secondo tema",
            "semantic_text": "gamma delta",
            "analysis_text": "",
            "probable_scope": "Ambito B",
            "message_count": 2,
        },
    ]
    with connect(db) as con:
        pid = Repository(con).get_or_create_project("study")
        con.execute(
            """CREATE TABLE IF NOT EXISTS atlas_embedding_cache(
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               semantic_document_id INTEGER NOT NULL,
               model_name TEXT NOT NULL,
               content_hash TEXT NOT NULL,
               embedding BLOB NOT NULL,
               created_at TEXT NOT NULL,
               UNIQUE(semantic_document_id, model_name, content_hash)
            )"""
        )
        for index, row in enumerate(rows, start=1):
            document_id = con.execute(
                """INSERT INTO atlas_semantic_documents(
                       project_id, document_level, source_id, version, content_hash, content,
                       metadata_json, created_at
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    pid,
                    "conversation",
                    row["id"],
                    "stream-test",
                    f"hash-{index}",
                    row["subject_normalized"],
                    "{}",
                    utcnow(),
                ),
            ).lastrowid
            con.execute(
                """INSERT INTO atlas_embedding_cache(
                       semantic_document_id, model_name, content_hash, embedding, created_at
                   ) VALUES(?,?,?,?,?)""",
                (
                    document_id,
                    "mock-embeddings",
                    f"hash-{index}",
                    embedding_to_blob(np.array([float(index), float(3 - index)])),
                    utcnow(),
                ),
            )

        points, method = _semantic_points(con, rows)

    assert method == "embeddings_pca"
    assert [point["conversation_id"] for point in points] == [101, 102]
    assert [point["group"] for point in points] == ["Ambito A", "Ambito B"]
    assert all(point["label"] for point in points)


def test_conversation_rows_keep_entities_and_attachments_aggregated(tmp_path: Path) -> None:
    db, _ = prepared(tmp_path)
    with connect(db) as con:
        pid = Repository(con).project_id("smoke")
        conversation = con.execute(
            "SELECT id FROM atlas_conversations WHERE project_id=? AND message_count>1 ORDER BY id LIMIT 1",
            (pid,),
        ).fetchone()
        assert conversation is not None
        conversation_id = int(conversation["id"])
        email_ids = [
            int(row["email_id"])
            for row in con.execute(
                "SELECT email_id FROM atlas_conversation_messages WHERE conversation_id=? ORDER BY position LIMIT 2",
                (conversation_id,),
            )
        ]
        assert len(email_ids) == 2
        now = utcnow()
        entity_ids = []
        for display_name in ("ACME Spa", "Studio Tecnico"):
            cur = con.execute(
                """
                INSERT INTO atlas_entities (
                    project_id,entity_type,normalized_name,display_name,
                    frequency,source,confidence,metadata_json,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    pid,
                    "organization",
                    display_name.lower().replace(" ", "_"),
                    display_name,
                    1,
                    "test",
                    0.9,
                    "{}",
                    now,
                    now,
                ),
            )
            entity_ids.append(int(cur.lastrowid))
        con.executemany(
            """
            INSERT INTO atlas_entity_mentions (
                entity_id,email_id,conversation_id,evidence,created_at
            ) VALUES (?,?,?,?,?)
            """,
            [
                (entity_ids[0], email_ids[0], conversation_id, "subject", now),
                (entity_ids[1], email_ids[1], conversation_id, "body", now),
            ],
        )
        con.executemany(
            """
            INSERT INTO attachments (
                email_id,filename,mime_type,size_bytes,sha256,extracted_text,
                extraction_status,attachment_type,attachment_keywords_json,
                text_excerpt,extraction_error,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    email_ids[0],
                    "alfa.pdf",
                    "application/pdf",
                    123,
                    "sha1",
                    None,
                    "ok",
                    "document",
                    "[]",
                    "alfa",
                    None,
                    now,
                ),
                (
                    email_ids[1],
                    "beta.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    456,
                    "sha2",
                    None,
                    "ok",
                    "document",
                    "[]",
                    "beta",
                    None,
                    now,
                ),
            ],
        )
    with connect(db) as con:
        rows = _conversation_rows(con, pid)
    row = next(item for item in rows if int(item["id"]) == conversation_id)
    assert set(row["entities"]) >= {"ACME Spa", "Studio Tecnico"}
    assert set(row["attachments"]) >= {"alfa.pdf", "beta.docx"}


def test_orange_pack_has_required_columns_and_workflows(tmp_path: Path) -> None:
    db, _ = prepared(tmp_path)
    output = tmp_path / "orange"
    export_orange(db, "smoke", output)
    with (output / "orange_conversations.csv").open(encoding="utf-8-sig") as handle:
        assert ORANGE_COLUMNS <= set(csv.DictReader(handle).fieldnames or [])
    assert (output / "orange_nodes.csv").stat().st_size > 0
    assert (output / "orange_edges.csv").stat().st_size > 0
    workflows = (output / "orange_workflow_suggestions.md").read_text(encoding="utf-8")
    assert all(f"## {letter}" in workflows for letter in "ABCD")


def test_classification_workspace_import_generates_final_atlas(tmp_path: Path) -> None:
    db, output = prepared(tmp_path)
    export_study_pack(db, "smoke", output)
    workspace = output / "classification_workspace.csv"
    with workspace.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    rows[0]["human_decision"] = "approve"
    rows[0]["final_name"] = "Pratiche ambientali"
    with workspace.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    final = tmp_path / "final"
    result = import_classification(db, "smoke", workspace, final)
    assert result["imported"] == 1
    assert {"atlas_final.csv", "atlas_final.yaml", "atlas_final.json", "atlas_final.html"} <= set(
        result["files"]
    )
    assert (
        json.loads((final / "atlas_final.json").read_text(encoding="utf-8"))[0]["name"]
        == "Pratiche ambientali"
    )
    assert yaml.safe_load((final / "atlas_final.yaml").read_text(encoding="utf-8"))
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM atlas_review_decisions").fetchone()[0] >= 2


def test_classification_import_rejects_unknown_approved_candidate(tmp_path: Path) -> None:
    db, output = prepared(tmp_path)
    export_study_pack(db, "smoke", output)
    workspace = output / "classification_workspace.csv"
    with workspace.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    rows[0]["candidate_id"] = "999999"
    rows[0]["human_decision"] = "approve"
    with workspace.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="Categorie candidate non trovate: 999999"):
        import_classification(db, "smoke", workspace, tmp_path / "final")
    assert not (tmp_path / "final").exists()


def test_gui_is_a_four_section_study_workbench(tmp_path: Path) -> None:
    db, _ = prepared(tmp_path)
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"database": {"path": str(db)}}), encoding="utf-8")
    page = TestClient(create_app(db, "smoke", config)).get("/").text
    assert all(
        label in page
        for label in (
            "Prepara Studio",
            "Esplora Risultati",
            "Esporta per Orange",
            "Costruisci Atlante",
        )
    )
    header = page.split("</header>", 1)[0]
    assert "Ricerca" not in header
    assert "Assistente locale" not in header
    assert "Funzioni precedenti" not in header
