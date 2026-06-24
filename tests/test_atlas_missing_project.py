from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from email_cluster.atlas.reset import reset_atlas_derived_data, reset_project
from email_cluster.atlas.smoke import run_smoke_test
from email_cluster.storage.database import connect, init_db
from email_cluster.ui.app import create_app
from email_cluster.ui.atlas_data import AtlasUiData


def config_for(tmp_path: Path, db: Path) -> Path:
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"database": {"path": str(db)}}), encoding="utf-8")
    return config


def test_status_and_conversations_are_safe_for_missing_project(tmp_path: Path) -> None:
    db = tmp_path / "empty.sqlite"
    init_db(db)
    atlas = AtlasUiData(db, "archivio_storico", config_for(tmp_path, db))
    status = atlas.status()
    summary = atlas.conversation_summary()
    assert status["project_exists"] is False
    assert status["state"] == "missing_project"
    assert status["email_count"] == status["conversation_count"] == 0
    assert summary["conversations"] == summary["emails"] == 0
    assert "Nessun progetto attivo" in summary["warning"]
    assert atlas.conversations() == []
    assert atlas.candidates() == []
    assert atlas.approved() == []


def test_home_handles_empty_database_and_hides_impossible_workflow(tmp_path: Path) -> None:
    db = tmp_path / "new.sqlite"
    client = TestClient(create_app(db, "archivio_storico", config_for(tmp_path, db)))
    response = client.get("/")
    assert response.status_code == 200
    assert "Nessuno studio attivo" in response.text
    assert "Crea nuovo studio" in response.text
    assert "Importa archivio" in response.text
    header = response.text.split("</header>", 1)[0]
    assert "Esporta per Orange" not in header
    assert "Costruisci Atlante" not in header


def test_api_returns_structured_missing_project_error(tmp_path: Path) -> None:
    db = tmp_path / "missing.sqlite"
    client = TestClient(create_app(db, "archivio_storico", config_for(tmp_path, db)))
    response = client.post("/api/atlas/run/index", json={})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error_type"] == "missing_project"
    assert "Crea un nuovo studio" in detail["message"]
    assert "Project not found" in detail["technical_detail"]


def test_derived_reset_keeps_project_and_home_available(tmp_path: Path) -> None:
    run_smoke_test(tmp_path)
    db = tmp_path / "atlas.sqlite"
    reset_atlas_derived_data(db, "smoke")
    client = TestClient(create_app(db, "smoke", config_for(tmp_path, db)))
    response = client.get("/")
    assert response.status_code == 200
    assert "Nessuno studio attivo" not in response.text
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM projects WHERE name='smoke'").fetchone()[0] == 1


def test_project_reset_leads_to_missing_study_home_not_500(tmp_path: Path) -> None:
    run_smoke_test(tmp_path)
    db = tmp_path / "atlas.sqlite"
    reset_project(db, "smoke", confirm=True)
    client = TestClient(create_app(db, "smoke", config_for(tmp_path, db)))
    response = client.get("/")
    assert response.status_code == 200
    assert "Nessuno studio attivo" in response.text


def test_main_atlas_routes_do_not_500_without_project(tmp_path: Path) -> None:
    db = tmp_path / "routes.sqlite"
    client = TestClient(create_app(db, "missing", config_for(tmp_path, db)))
    for path in ("/", "/atlas/conversations", "/atlas/review", "/atlas/search"):
        assert client.get(path).status_code == 200
