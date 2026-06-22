from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

from pathlib import Path
from typing import Any


from email_cluster.storage.database import init_db

from .conversations import build_conversations
from .discovery import discover
from .entities import extract_entities
from .parsing import parse_and_clean
from .reports import write_report
from .search import build_index
from .semantic_docs import build_semantic_docs


def update_archive(
    input_path: Path, db_path: Path, project: str, config_path: Path = Path("config/default.yaml")
) -> dict[str, Any]:
    from email_cluster.cli.app import import_emails

    init_db(db_path)
    import_emails(source=input_path, project=project, db=db_path, config=config_path)
    parsed = parse_and_clean(db_path, project, config_path)
    conversations = build_conversations(db_path, project)
    indexed = build_index(db_path, project)
    entities = extract_entities(db_path, project)
    docs = build_semantic_docs(db_path, project)
    discovery = discover(db_path, project)
    result = {
        "parse": parsed,
        "conversations": conversations,
        "index": indexed,
        "entities": entities,
        "semantic_docs": docs,
        "discovery": discovery,
    }
    write_report(Path("reports/update_report.html"), "Aggiornamento Atlante", result)
    return result
