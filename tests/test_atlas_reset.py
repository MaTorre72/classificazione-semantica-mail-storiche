from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from email_cluster.atlas.cli import app as atlas_cli
from email_cluster.atlas.conversations import build_conversations
from email_cluster.atlas.reset import reset_atlas_derived_data, reset_project
from email_cluster.atlas.smoke import create_fixture, run_smoke_test
from email_cluster.atlas.study import build_study_dataset
from email_cluster.storage.database import connect
from email_cluster.storage.repository import embedding_to_blob
from email_cluster.ui.app import create_app


def populated(tmp_path: Path) -> Path:
    run_smoke_test(tmp_path)
    return tmp_path / "atlas.sqlite"


def test_build_conversations_is_safe_when_repeated(tmp_path: Path) -> None:
    db = populated(tmp_path)
    first = build_conversations(db, "smoke")
    second = build_conversations(db, "smoke")
    assert first["reused"] is True
    assert second["reused"] is True
    with connect(db) as con:
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_build_study_dataset_twice_with_unchanged_files(tmp_path: Path) -> None:
    mail = create_fixture(tmp_path)
    db = tmp_path / "study.sqlite"
    output = tmp_path / "study"
    first = build_study_dataset(mail, db, "study", output)
    second = build_study_dataset(mail, db, "study", output)
    assert first["conversation_build"]["reused"] is False
    assert second["conversation_build"]["reused"] is True
    assert second["conversation_build"]["new_unlinked_emails"] == 0


def test_rebuild_derived_preserves_human_data_and_creates_backup(tmp_path: Path) -> None:
    db = populated(tmp_path)
    with connect(db) as con:
        document = con.execute("SELECT id FROM atlas_semantic_documents LIMIT 1").fetchone()[0]
        con.execute(
            """CREATE TABLE IF NOT EXISTS atlas_embedding_cache(
               id INTEGER PRIMARY KEY,semantic_document_id INTEGER NOT NULL,model_name TEXT NOT NULL,
               content_hash TEXT NOT NULL,embedding BLOB NOT NULL,created_at TEXT NOT NULL,
               UNIQUE(semantic_document_id,model_name,content_hash))"""
        )
        con.execute(
            "INSERT INTO atlas_embedding_cache(semantic_document_id,model_name,content_hash,embedding,created_at) VALUES(?,?,?,?,datetime('now'))",
            (document, "test", "hash", embedding_to_blob(np.array([1.0, 2.0]))),
        )
        reviews_before = con.execute("SELECT count(*) FROM atlas_review_decisions").fetchone()[0]
        categories_before = con.execute("SELECT count(*) FROM atlas_categories").fetchone()[0]
    result = reset_atlas_derived_data(db, "smoke")
    assert result.backup_path and Path(result.backup_path).exists()
    assert result.deleted["atlas_embedding_cache"] == 1
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM atlas_conversations").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM atlas_semantic_documents").fetchone()[0] == 0
        assert con.execute("SELECT count(*) FROM atlas_candidate_categories").fetchone()[0] == 0
        assert (
            con.execute("SELECT count(*) FROM atlas_review_decisions").fetchone()[0]
            == reviews_before
        )
        assert (
            con.execute("SELECT count(*) FROM atlas_categories").fetchone()[0] == categories_before
        )
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_rebuild_then_conversations_succeeds_with_existing_candidates(tmp_path: Path) -> None:
    db = populated(tmp_path)
    result = build_conversations(db, "smoke", mode="rebuild-derived")
    assert result["reused"] is False
    assert result["reset"]["backup_path"]
    assert result["conversations"] > 0


def test_reset_project_requires_confirmation_and_removes_project(tmp_path: Path) -> None:
    db = populated(tmp_path)
    with pytest.raises(ValueError, match="conferma esplicita"):
        reset_project(db, "smoke")
    result = reset_project(db, "smoke", confirm=True)
    assert result.backup_path and Path(result.backup_path).exists()
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM projects WHERE name='smoke'").fetchone()[0] == 0
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_reset_project_cli_requires_confirm(tmp_path: Path) -> None:
    db = populated(tmp_path)
    result = CliRunner().invoke(atlas_cli, ["reset-project", "--db", str(db), "--project", "smoke"])
    assert result.exit_code != 0
    assert "conferma esplicita" in result.stdout


def test_gui_returns_readable_database_error(tmp_path: Path) -> None:
    db = populated(tmp_path)
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"database": {"path": str(db)}}), encoding="utf-8")
    client = TestClient(create_app(db, "smoke", config))

    def fail(*args, **kwargs):
        import sqlite3

        raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")

    client.app.state.atlas.run_phase = fail
    response = client.post("/api/atlas/run/build_study", json={})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert "evitare perdite" in detail["message"]
    assert detail["phase"] == "build_study"
    assert "Ricostruisci" in detail["next_step"] or "ricostruisci" in detail["next_step"]
    assert "IntegrityError" in detail["technical"]


def test_source_never_disables_foreign_keys() -> None:
    root = Path("src/email_cluster")
    forbidden = "foreign_keys = off"
    assert not any(
        forbidden in path.read_text(encoding="utf-8").lower() for path in root.rglob("*.py")
    )
