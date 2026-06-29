from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository


CORE_TABLES = {"projects", "source_files", "emails", "errors"}
DERIVED_TABLES = {
    "clean_texts",
    "atlas_conversations",
    "atlas_conversation_messages",
    "atlas_semantic_documents",
    "atlas_candidate_categories",
}


class WorkspaceIntegrityError(RuntimeError):
    """A workspace cannot be used without risking inconsistent writes."""


def ensure_project(con: sqlite3.Connection, project: str) -> int:
    """Create the project when absent and prove that its id is usable."""
    if not project.strip():
        raise WorkspaceIntegrityError("Nome progetto non valido: non puo essere vuoto.")
    repo = Repository(con)
    try:
        project_id = repo.get_or_create_project(project)
        row = con.execute(
            "SELECT id FROM projects WHERE id=? AND name=?", (project_id, project)
        ).fetchone()
    except sqlite3.Error as exc:
        raise WorkspaceIntegrityError(
            "Il database del workspace e incompleto o danneggiato. "
            "Esegui doctor-workspace prima di riprovare."
        ) from exc
    if row is None:
        raise WorkspaceIntegrityError(
            "Il progetto non e stato registrato correttamente. Nessuna sorgente e stata importata."
        )
    return int(row["id"])


def doctor_workspace(db_path: Path, project: str = "studio") -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "database": str(db_path),
        "project": project,
        "project_id": None,
        "foreign_keys_enabled": False,
        "foreign_key_violations": [],
        "missing_core_tables": [],
        "missing_derived_tables": [],
        "counts": {},
        "errors": [],
        "warnings": [],
        "next_step": "",
    }
    if not db_path.is_file():
        result["errors"].append("Database del workspace non trovato.")
        result["next_step"] = "Esegui study per creare il workspace oppure repair-workspace."
        return result
    try:
        with connect(db_path) as con:
            result["foreign_keys_enabled"] = con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
            tables = {
                row["name"]
                for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            result["missing_core_tables"] = sorted(CORE_TABLES - tables)
            result["missing_derived_tables"] = sorted(DERIVED_TABLES - tables)
            if result["missing_core_tables"]:
                result["errors"].append("Mancano tabelle fondamentali del database.")
            if result["missing_derived_tables"]:
                result["warnings"].append("Mancano alcune tabelle derivate ricostruibili.")
            if "projects" in tables:
                row = con.execute("SELECT id FROM projects WHERE name=?", (project,)).fetchone()
                if row:
                    result["project_id"] = int(row["id"])
                else:
                    result["errors"].append(f"Progetto mancante: {project}.")
            violations = [dict(row) for row in con.execute("PRAGMA foreign_key_check")]
            result["foreign_key_violations"] = violations
            if violations:
                result["errors"].append(f"Rilevate {len(violations)} violazioni delle foreign key.")
            pid = result["project_id"]
            for table in ("source_files", "emails", "clean_texts", "atlas_conversations"):
                if table not in tables:
                    continue
                if table in {"source_files", "emails", "atlas_conversations"} and pid is not None:
                    count = con.execute(
                        f"SELECT count(*) FROM {table} WHERE project_id=?", (pid,)
                    ).fetchone()[0]
                elif table == "clean_texts" and pid is not None:
                    count = con.execute(
                        "SELECT count(*) FROM clean_texts c JOIN emails e ON e.id=c.email_id "
                        "WHERE e.project_id=?",
                        (pid,),
                    ).fetchone()[0]
                else:
                    count = 0
                result["counts"][table] = int(count)
    except sqlite3.Error as exc:
        result["errors"].append(f"Database SQLite non leggibile: {exc}")
    result["ok"] = not result["errors"] and result["foreign_keys_enabled"]
    if result["ok"]:
        result["next_step"] = "Workspace integro: puoi eseguire study."
    elif result["foreign_key_violations"]:
        result["next_step"] = (
            "Non scrivere in questo database. Conserva il workspace e creane uno nuovo, "
            "oppure ripristina un backup verificato."
        )
    else:
        result["next_step"] = "Esegui repair-workspace; verra creato prima un backup."
    return result


def repair_workspace(db_path: Path, project: str = "studio") -> dict[str, Any]:
    """Repair only schema/project omissions; never delete or rewrite orphaned rows."""
    backup: Path | None = None
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = db_path.with_suffix(db_path.suffix + f".backup-{timestamp}")
        try:
            with connect(db_path) as source, connect(backup) as target:
                source.backup(target)
        except sqlite3.Error as exc:
            raise WorkspaceIntegrityError(
                "Impossibile creare il backup: riparazione annullata senza modifiche."
            ) from exc
        before = doctor_workspace(db_path, project)
        if before["foreign_key_violations"]:
            raise WorkspaceIntegrityError(
                "Riparazione automatica rifiutata: esistono violazioni foreign key. "
                "Usa un workspace nuovo o ripristina un backup."
            )
    try:
        init_db(db_path, backup_before_migration=False)
        with connect(db_path) as con:
            ensure_project(con, project)
        after = doctor_workspace(db_path, project)
    except (sqlite3.Error, WorkspaceIntegrityError) as exc:
        raise WorkspaceIntegrityError(
            f"Riparazione non completata. Il backup resta disponibile in {backup or 'nessun backup'}."
        ) from exc
    if not after["ok"]:
        raise WorkspaceIntegrityError(f"Workspace ancora incoerente. {after['next_step']}")
    return {"ok": True, "backup": str(backup) if backup else None, "doctor": after}
