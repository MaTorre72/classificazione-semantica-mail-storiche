from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from email_cluster.atlas.smoke import run_smoke_test
from email_cluster.storage.database import connect
from email_cluster.ui.app import create_app


def smoke_client(tmp_path: Path) -> tuple[TestClient, Path]:
    run_smoke_test(tmp_path)
    db = tmp_path / "atlas.sqlite"
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"database": {"path": str(db)}}), encoding="utf-8")
    app = create_app(db, "smoke", config)
    app.state.atlas.reports_dir = tmp_path / "reports"
    return TestClient(app), db


def test_conversation_page_uses_real_fields_and_quality(tmp_path: Path) -> None:
    client, _ = smoke_client(tmp_path)
    response = client.get("/atlas/conversations")
    assert response.status_code == 200
    assert "Registri rifiuti sede TPM" in response.text
    assert "Header di risposta" in response.text
    assert "Conversazioni isolate" in response.text
    assert "Bassa affidabilita" in response.text


def test_conversation_detail_shows_linked_messages_and_reason(tmp_path: Path) -> None:
    client, db = smoke_client(tmp_path)
    with connect(db) as con:
        conversation_id = con.execute(
            "SELECT id FROM atlas_conversations WHERE message_count>1 LIMIT 1"
        ).fetchone()[0]
    response = client.get(f"/atlas/conversations/{conversation_id}")
    assert response.status_code == 200
    assert response.text.count("Oggetto normalizzato:") >= 2
    assert "Perche sono collegati" in response.text
    assert "Correzioni manuali - non ancora disponibile" in response.text


def test_fragile_state_and_entity_state_are_independent(tmp_path: Path) -> None:
    client, db = smoke_client(tmp_path)
    with connect(db) as con:
        con.execute("DELETE FROM atlas_entity_mentions")
        con.execute("DELETE FROM atlas_entities")
    status = client.app.state.atlas.status()
    conversation_phase = next(p for p in status["phases"] if p["key"] == "conversations")
    entity_phase = next(p for p in status["phases"] if p["key"] == "entities")
    assert conversation_phase["state"] == "fragile"
    assert status["semantic_docs"] > 0
    assert entity_phase["state"] != "completed"


def test_home_result_panel_is_before_pipeline_and_review_empty_is_clear(tmp_path: Path) -> None:
    client, db = smoke_client(tmp_path)
    home = client.get("/").text
    assert home.index("runStatus") < home.index('id="prepare"')
    with connect(db) as con:
        con.execute("DELETE FROM atlas_candidate_conversations")
        con.execute("DELETE FROM atlas_candidate_categories")
    review = client.get("/atlas/review")
    assert "Non ci sono categorie candidate da revisionare" in review.text
    assert "Esegui Categorie candidate" in review.text


def test_discovery_is_blocked_without_prerequisites(tmp_path: Path) -> None:
    client, db = smoke_client(tmp_path)
    with connect(db) as con:
        con.execute("DELETE FROM atlas_semantic_documents")
    response = client.post("/api/atlas/run/discover", json={})
    assert response.status_code == 409
    assert "Documenti conversazione" in response.json()["detail"]
