from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

from pathlib import Path
from typing import Any


from email_cluster.storage.database import connect
from email_cluster.storage.repository import Repository

from .reports import write_report


def evaluate(db_path: Path, project: str, reports: Path = Path("reports")) -> dict[str, Any]:
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        emails = con.execute("SELECT count(*) FROM emails WHERE project_id=?", (pid,)).fetchone()[0]
        conversations = con.execute(
            "SELECT count(*) FROM atlas_conversations WHERE project_id=?", (pid,)
        ).fetchone()[0]
        candidates = con.execute(
            "SELECT count(*) FROM atlas_candidate_categories WHERE project_id=?", (pid,)
        ).fetchone()[0]
        approved = con.execute(
            "SELECT count(*) FROM atlas_categories WHERE project_id=? AND status='approved'", (pid,)
        ).fetchone()[0]
        small = con.execute(
            "SELECT count(*) FROM atlas_candidate_categories WHERE project_id=? AND is_fragmented=1",
            (pid,),
        ).fetchone()[0]
        ambiguous = con.execute(
            "SELECT count(*) FROM atlas_candidate_categories WHERE project_id=? AND status='ambiguous'",
            (pid,),
        ).fetchone()[0]
    ratio = candidates / max(conversations, 1)
    judgement = (
        "fragile"
        if not conversations or not candidates
        else "troppo frammentato"
        if ratio > 0.25
        else "accettabile"
        if not approved
        else "buono"
    )
    result = {
        "emails": emails,
        "conversations": conversations,
        "email_to_conversation_reduction": round(1 - conversations / max(emails, 1), 3),
        "candidate_categories": candidates,
        "approved_categories": approved,
        "categories_per_conversation": round(ratio, 3),
        "small_categories": small,
        "ambiguous": ambiguous,
        "judgement": judgement,
    }
    write_report(reports / "evaluation_report.html", "Valutazione Atlante", result)
    return result
