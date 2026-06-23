from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from email_cluster.atlas.smoke import create_fixture, run_smoke_test
from email_cluster.atlas.study import (
    build_study_dataset,
    export_orange,
    export_study_pack,
    import_classification,
)
from email_cluster.storage.database import connect
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
