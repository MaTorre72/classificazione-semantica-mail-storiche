from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from email_cluster.operational.builder import build_operational_contexts
from email_cluster.storage.database import connect
from email_cluster.ui.app import create_app
from tests.test_review_v3 import make_review_db


def make_client(tmp_path: Path) -> tuple[TestClient, Path]:
    db = tmp_path / "ui.sqlite"
    make_review_db(db)
    with connect(db) as con:
        build_operational_contexts(con, 1, 1)
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "database": {"path": str(db)},
                "local_llm": {
                    "enabled": False,
                    "backend": "ollama",
                    "ollama_url": "http://127.0.0.1:11434",
                    "mode": "suggestions_only",
                },
            }
        ),
        encoding="utf-8",
    )
    return TestClient(create_app(db, "studio", config)), db


def test_main_console_pages_render(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    for path in ("/", "/wizard", "/llm", "/macro", "/contexts", "/taxonomy", "/export"):
        response = client.get(path)
        assert response.status_code == 200
        assert "Archivio storico" in response.text


def test_context_and_email_drill_down(tmp_path: Path) -> None:
    client, db = make_client(tmp_path)
    with connect(db) as con:
        context_id = con.execute(
            "SELECT id FROM operational_contexts ORDER BY id LIMIT 1"
        ).fetchone()[0]
        email_id = con.execute("SELECT email_id FROM email_context_assignments LIMIT 1").fetchone()[
            0
        ]
    assert client.get(f"/contexts/{context_id}").status_code == 200
    assert client.get(f"/emails/{email_id}").status_code == 200
    assert client.get("/contexts/999999").status_code == 404


def test_human_approval_is_persisted(tmp_path: Path) -> None:
    client, db = make_client(tmp_path)
    with connect(db) as con:
        context_id = con.execute(
            "SELECT id FROM operational_contexts ORDER BY id LIMIT 1"
        ).fetchone()[0]
    response = client.post(f"/api/contexts/{context_id}/approve", json={})
    assert response.status_code == 200
    with connect(db) as con:
        status = con.execute(
            "SELECT review_status FROM operational_contexts WHERE id=?", (context_id,)
        ).fetchone()[0]
        events = con.execute(
            "SELECT count(*) FROM context_review_events WHERE operational_context_id=?",
            (context_id,),
        ).fetchone()[0]
    assert status == "approved"
    assert events >= 1


def test_llm_settings_stay_local(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    response = client.post(
        "/api/llm/config",
        json={
            "enabled": True,
            "backend": "ollama",
            "ollama_url": "http://127.0.0.1:11434",
            "model": "qwen-local",
        },
    )
    assert response.status_code == 200
    page = client.get("/llm")
    assert "qwen-local" in page.text
    assert "non scarica modelli" in page.text
