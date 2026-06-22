from pathlib import Path

import json
import yaml
from typer.testing import CliRunner

from email_cluster.atlas.cli import app
from email_cluster.atlas.export import export_atlas
from email_cluster.atlas.review import review_action
from email_cluster.atlas.search import search
from email_cluster.atlas.smoke import create_fixture, run_smoke_test
from email_cluster.storage.database import connect, init_db


def test_inventory_cli_handles_fixture_and_duplicates(tmp_path: Path) -> None:
    mail = create_fixture(tmp_path)
    db = tmp_path / "inventory.sqlite"
    result = CliRunner().invoke(
        app,
        [
            "inventory",
            "--input",
            str(mail),
            "--db",
            str(db),
            "--project",
            "test",
            "--reports",
            str(tmp_path / "reports"),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["emails_detected"] == 7
    assert data["probable_duplicates"] == 1


def test_inventory_invalid_path_is_clear(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "inventory",
            "--input",
            str(tmp_path / "missing"),
            "--db",
            str(tmp_path / "x.sqlite"),
            "--project",
            "test",
        ],
    )
    assert result.exit_code != 0
    assert "Percorso non valido" in str(result.exception)


def test_conversation_search_and_smoke(tmp_path: Path) -> None:
    result = run_smoke_test(tmp_path)
    assert result["conversations"]["conversations"] < result["conversations"]["emails"]
    assert result["export"]["categories"] >= 1
    assert (tmp_path / "atlas-output" / "atlas.yaml").exists()
    assert yaml.safe_load((tmp_path / "atlas-output" / "atlas.yaml").read_text(encoding="utf-8"))
    rows = search(tmp_path / "atlas.sqlite", "rifiuti", "smoke")
    assert rows and "[rifiuti]" in rows[0]["evidence"].lower()


def test_schema_contains_conversation_and_atlas_tables(tmp_path: Path) -> None:
    db = tmp_path / "schema.sqlite"
    init_db(db)
    with connect(db) as con:
        tables = {
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")
        }
        version = con.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
    assert {
        "atlas_conversations",
        "atlas_conversation_messages",
        "atlas_candidate_categories",
        "atlas_categories",
    } <= tables
    assert version == "7"


def test_review_is_traced_and_public_export_redacts_identity(tmp_path: Path) -> None:
    run_smoke_test(tmp_path)
    db = tmp_path / "atlas.sqlite"
    with connect(db) as con:
        candidate = con.execute(
            "SELECT id FROM atlas_candidate_categories WHERE status='candidate' LIMIT 1"
        ).fetchone()
    review_action(db, "smoke", int(candidate[0]), "approve", name="Categoria sicura")
    output = tmp_path / "public"
    result = export_atlas(db, "smoke", output, public_safe=True)
    payload = json.loads((output / "atlas.json").read_text(encoding="utf-8"))
    assert result["categories"] >= 1
    assert all(item["soggetto_nome"] is None for item in payload)
    assert all(not item["domini_ricorrenti"] for item in payload)
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM atlas_review_decisions").fetchone()[0] >= 2
