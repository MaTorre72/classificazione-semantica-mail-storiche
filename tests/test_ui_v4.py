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
    for path in (
        "/",
        "/wizard",
        "/llm",
        "/macro",
        "/contexts",
        "/classification",
        "/taxonomy",
        "/export",
    ):
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


def test_simple_terminology_is_visible(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    page = client.get("/classification")
    assert "Area → Classe → Insieme → Email" in page.text
    assert "Classificazione" in page.text
    detail = client.get("/contexts")
    assert "Insiemi" in detail.text
    assert "Contesti operativi" not in detail.text


def test_manage_areas_labels_and_rules(tmp_path: Path) -> None:
    client, db = make_client(tmp_path)
    assert (
        client.post(
            "/api/classification/areas", json={"display_name": "Progetti speciali"}
        ).status_code
        == 200
    )
    with connect(db) as con:
        area = con.execute(
            "SELECT * FROM classification_areas WHERE display_name='Progetti speciali'"
        ).fetchone()
    assert (
        client.post(
            f"/api/classification/areas/{area['id']}",
            json={"display_name": "Progetti", "active": False},
        ).status_code
        == 200
    )
    assert client.post("/api/classification/labels", json={"label": "MUD"}).status_code == 200
    with connect(db) as con:
        label = con.execute("SELECT * FROM taxonomy_labels WHERE label='MUD'").fetchone()
    assert (
        client.post(
            f"/api/classification/labels/{label['id']}", json={"label": "MUD annuale"}
        ).status_code
        == 200
    )
    rule = client.post(
        "/api/classification/rules",
        json={
            "name": "Tenax",
            "condition_type": "sender_contains",
            "pattern": "tenax.it",
            "action_type": "label",
            "action_value": "Cliente Tenax",
            "priority": 100,
        },
    ).json()
    preview = client.post(f"/api/classification/rules/{rule['id']}/preview").json()
    assert preview["count"] >= 1
    applied = client.post(f"/api/classification/rules/{rule['id']}/apply").json()
    assert applied["count"] == preview["count"]


def test_model_pull_requires_confirmation(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    response = client.post("/api/llm/pull", json={"model": "qwen2.5:1.5b", "confirmed": False})
    assert response.status_code == 409
    assert "conferma esplicita" in response.json()["detail"]


def test_classes_tree_and_archive_page(tmp_path: Path) -> None:
    client, db = make_client(tmp_path)
    page = client.get("/classification/classes")
    assert page.status_code == 200
    assert "Gestione rifiuti" in page.text
    with connect(db) as con:
        area_id = con.execute("SELECT id FROM classification_areas ORDER BY id LIMIT 1").fetchone()[
            0
        ]
    created = client.post(
        "/api/classification/classes", json={"area_id": area_id, "name": "Classe prova"}
    )
    assert created.status_code == 200
    tree = client.get("/classification")
    assert "Classe prova" in tree.text
    archive = client.get("/database")
    assert archive.status_code == 200
    assert "Archivio email" in archive.text


def test_archive_scan_and_restore_require_confirmation(tmp_path: Path) -> None:
    client, db = make_client(tmp_path)
    mail_dir = tmp_path / "mail"
    mail_dir.mkdir()
    (mail_dir / "sample.eml").write_text("Subject: Test\n\nMessaggio", encoding="utf-8")
    scan = client.post("/api/archive/scan", json={"input_path": str(mail_dir)})
    assert scan.status_code == 200
    assert scan.json()["files"] == 1
    backup = client.post("/api/archive/backup", json={}).json()["backup"]
    denied = client.post(f"/api/archive/restore/{Path(backup).name}", json={"confirmed": False})
    assert denied.status_code == 409
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM archive_operations").fetchone()[0] >= 1
