from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from email_cluster.atlas.cli import app as atlas_cli
from email_cluster.atlas.reset import reset_atlas_derived_data
from email_cluster.atlas.workspace_study import run_study
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository
from email_cluster.storage.workspace_health import (
    WorkspaceIntegrityError,
    doctor_workspace,
    repair_workspace,
)
from email_cluster.ui.app import create_app
from tests.test_thunderbird_workspace import make_snapshot


def corrupt_with_orphan_source(db: Path) -> None:
    init_db(db)
    with sqlite3.connect(db) as con:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute(
            """INSERT INTO source_files
               (project_id,path,file_type,imported_at,status)
               VALUES (999,'orphan.mbox','mbox','now','error')"""
        )
        con.commit()


def test_doctor_and_repair_empty_workspace(tmp_path: Path) -> None:
    db = tmp_path / "empty" / "email_atlas.sqlite"
    before = doctor_workspace(db)
    assert before["ok"] is False
    repaired = repair_workspace(db)
    assert repaired["ok"] is True
    assert repaired["backup"] is None
    assert doctor_workspace(db)["ok"] is True


def test_missing_project_is_created_before_source_file(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"
    init_db(workspace / "email_atlas.sqlite")
    result = run_study(snapshot, workspace, attachments_text=False)
    assert result["conversations"] > 0
    with connect(workspace / "email_atlas.sqlite") as con:
        pid = Repository(con).project_id("studio")
        assert (
            con.execute("SELECT count(*) FROM source_files WHERE project_id=?", (pid,)).fetchone()[
                0
            ]
            > 0
        )


def test_study_after_derived_reset_and_second_rerun(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"
    run_study(snapshot, workspace, attachments_text=False)
    reset_atlas_derived_data(workspace / "email_atlas.sqlite", "studio")
    assert run_study(snapshot, workspace, attachments_text=False)["conversations"] > 0
    assert run_study(snapshot, workspace, attachments_text=False)["conversations"] > 0
    assert doctor_workspace(workspace / "email_atlas.sqlite")["ok"] is True


def test_partial_database_is_completed_without_deleting_data(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "partial"
    workspace.mkdir()
    db = workspace / "email_atlas.sqlite"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE retained_note (value TEXT)")
        con.execute("INSERT INTO retained_note VALUES ('keep')")
    run_study(snapshot, workspace, attachments_text=False)
    with connect(db) as con:
        assert con.execute("SELECT value FROM retained_note").fetchone()[0] == "keep"
    assert list(workspace.glob("email_atlas.sqlite.backup-*"))


def test_foreign_key_violation_blocks_study_and_repair(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "broken"
    workspace.mkdir()
    db = workspace / "email_atlas.sqlite"
    corrupt_with_orphan_source(db)
    health = doctor_workspace(db)
    assert health["ok"] is False
    assert health["foreign_key_violations"]
    try:
        run_study(snapshot, workspace, attachments_text=False)
    except WorkspaceIntegrityError as exc:
        assert "Non scrivere" in str(exc) or "workspace" in str(exc).lower()
    else:
        raise AssertionError("study accepted a workspace with FK violations")
    try:
        repair_workspace(db)
    except WorkspaceIntegrityError as exc:
        assert "rifiutata" in str(exc).lower()
    else:
        raise AssertionError("repair rewrote a workspace with FK violations")
    assert list(workspace.glob("email_atlas.sqlite.backup-*"))


def test_cli_and_gui_return_readable_integrity_errors(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "broken"
    workspace.mkdir()
    corrupt_with_orphan_source(workspace / "email_atlas.sqlite")
    runner = CliRunner()
    cli = runner.invoke(
        atlas_cli,
        ["study", "--input", str(snapshot), "--workspace", str(workspace)],
    )
    assert cli.exit_code == 2
    assert "Traceback" not in cli.stdout
    assert "Workspace incoerente" in cli.stdout

    app = create_app(tmp_path / "ui.sqlite", "missing")
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/atlas/run/workspace_study",
        json={"input_path": str(snapshot), "workspace": str(workspace)},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error_type"] == "workspace_integrity"
    assert "Traceback" not in detail["technical"]


def test_record_error_drops_invalid_links(tmp_path: Path) -> None:
    db = tmp_path / "errors.sqlite"
    init_db(db)
    with connect(db) as con:
        Repository(con).record_error("ingestion", ValueError("bad"), 999, 888, 777)
        row = con.execute("SELECT project_id,source_file_id,email_id FROM errors").fetchone()
        assert tuple(row) == (None, None, None)
