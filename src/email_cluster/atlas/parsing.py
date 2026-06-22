from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

from pathlib import Path
from typing import Any


from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository

from .common import ATLAS_VERSION
from .reports import write_report


def parse_and_clean(
    db_path: Path,
    project: str,
    config_path: Path = Path("config/default.yaml"),
    reports: Path = Path("reports"),
    force: bool = False,
) -> dict[str, Any]:
    from email_cluster.cli.app import clean, prepare_context

    init_db(db_path)
    if force:
        raise ValueError(
            "La rigenerazione invasiva richiede il comando update con conferma e backup."
        )
    clean(project=project, db=db_path, config=config_path)
    prepare_context(project=project, db=db_path, config=config_path)
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        total = con.execute("SELECT count(*) FROM emails WHERE project_id=?", (pid,)).fetchone()[0]
        cleaned = con.execute(
            "SELECT count(DISTINCT c.email_id) FROM clean_texts c JOIN emails e ON e.id=c.email_id WHERE e.project_id=?",
            (pid,),
        ).fetchone()[0]
        segmented = con.execute(
            "SELECT count(DISTINCT c.email_id) FROM clean_texts c JOIN emails e ON e.id=c.email_id WHERE e.project_id=? AND (c.quoted_thread_text!='' OR c.forwarded_text!='' OR c.signature_text!='' OR c.disclaimer_text!='')",
            (pid,),
        ).fetchone()[0]
        poor = con.execute(
            "SELECT count(DISTINCT c.email_id) FROM clean_texts c JOIN emails e ON e.id=c.email_id WHERE e.project_id=? AND c.quality_score<0.4",
            (pid,),
        ).fetchone()[0]
    result = {
        "project": project,
        "emails": total,
        "cleaned": cleaned,
        "segmented": segmented,
        "low_quality": poor,
        "version": ATLAS_VERSION,
    }
    write_report(reports / "parsing_report.html", "Parsing archivio", result)
    write_report(reports / "cleaning_report.html", "Pulizia testi", result)
    return result
