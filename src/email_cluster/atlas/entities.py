from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, utcnow

from .reports import write_report


def extract_entities(
    db_path: Path,
    project: str,
    config_dir: Path = Path("config/entities"),
    reports: Path = Path("reports"),
) -> dict[str, Any]:
    init_db(db_path)
    dictionaries = {}
    for name in (
        "clients",
        "sites",
        "public_bodies",
        "suppliers",
        "technical_terms",
        "exclusion_terms",
    ):
        path = config_dir / f"{name}.yaml"
        dictionaries[name] = (
            yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else []
        )
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        con.execute(
            "DELETE FROM atlas_entity_mentions WHERE entity_id IN(SELECT id FROM atlas_entities WHERE project_id=?)",
            (pid,),
        )
        con.execute("DELETE FROM atlas_entities WHERE project_id=?", (pid,))
        rows = list(
            con.execute(
                "SELECT id,sender,subject,body_extracted_text FROM emails WHERE project_id=?",
                (pid,),
            )
        )
        found: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            sender = row["sender"] or ""
            match = re.search(r"@([\w.-]+)", sender)
            candidates = []
            if match:
                candidates.append(
                    ("domain", match.group(1).lower(), match.group(1).lower(), sender)
                )
            text = f"{row['subject'] or ''}\n{row['body_extracted_text'] or ''}"
            for kind, entries in dictionaries.items():
                for entry in entries or []:
                    value = entry if isinstance(entry, str) else entry.get("name", "")
                    aliases = [value] + ([] if isinstance(entry, str) else entry.get("aliases", []))
                    if value and any(
                        re.search(rf"\b{re.escape(a)}\b", text, re.I) for a in aliases
                    ):
                        candidates.append((kind.rstrip("s"), value.lower(), value, value))
            for kind, key, display, evidence in candidates:
                item = found.setdefault((kind, key), {"display": display, "mentions": []})
                item["mentions"].append((row["id"], evidence))
        for (kind, key), item in found.items():
            cur = con.execute(
                "INSERT INTO atlas_entities(project_id,entity_type,normalized_name,display_name,frequency,confidence,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,0.8,'{}',?,?)",
                (pid, kind, key, item["display"], len(item["mentions"]), utcnow(), utcnow()),
            )
            eid = int(cur.lastrowid)
            con.executemany(
                "INSERT OR IGNORE INTO atlas_entity_mentions(entity_id,email_id,evidence,created_at) VALUES(?,?,?,?)",
                [(eid, email, evidence, utcnow()) for email, evidence in item["mentions"]],
            )
    result = {"entities": len(found), "by_type": dict(Counter(k[0] for k in found))}
    write_report(reports / "entity_report.html", "Entità ricorrenti", result)
    return result
