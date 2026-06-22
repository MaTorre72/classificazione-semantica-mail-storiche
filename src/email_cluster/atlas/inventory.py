from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

from collections import Counter
from pathlib import Path
from typing import Any


from email_cluster.ingestion.scanner import scan_local_folder
from email_cluster.parsing.email_parser import parse_eml, parse_mbox
from email_cluster.storage.database import init_db

from .reports import write_report


def inventory(
    input_path: Path, db_path: Path, project: str, reports: Path = Path("reports")
) -> dict[str, Any]:
    if not input_path.exists():
        raise ValueError(f"Percorso non valido: {input_path}")
    init_db(db_path)
    candidates = scan_local_folder(input_path)
    hashes: Counter[str] = Counter()
    years: list[int] = []
    detected = parseable = attachments = errors = incoming = outgoing = 0
    source_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        found = ok = bad = files_attachments = 0
        try:
            messages = (
                [parse_eml(candidate.path, extract_attachments=False)]
                if candidate.file_type == "eml"
                else parse_mbox(candidate.path, extract_attachments=False)
            )
            for message in messages:
                found += 1
                detected += 1
                ok += 1
                parseable += 1
                hashes[message.message_hash] += 1
                attachments += len(message.attachments)
                files_attachments += len(message.attachments)
                if message.sent_at:
                    years.append(message.sent_at.year)
                if message.sender and "sent" in str(candidate.path).lower():
                    outgoing += 1
                else:
                    incoming += 1
        except Exception as exc:  # noqa: BLE001
            bad += 1
            errors += 1
            source_rows.append(
                {"path": str(candidate.path), "type": candidate.file_type, "error": str(exc)}
            )
        else:
            source_rows.append(
                {
                    "path": str(candidate.path),
                    "type": candidate.file_type,
                    "messages": found,
                    "parseable": ok,
                    "errors": bad,
                    "attachments": files_attachments,
                }
            )
    result = {
        "project": project,
        "input": str(input_path),
        "sources": len(candidates),
        "files": len(candidates),
        "emails_detected": detected,
        "emails_parseable": parseable,
        "probable_duplicates": sum(n - 1 for n in hashes.values() if n > 1),
        "year_start": min(years) if years else None,
        "year_end": max(years) if years else None,
        "incoming_estimate": incoming,
        "outgoing_estimate": outgoing,
        "attachments": attachments,
        "errors": errors,
        "warnings": (
            ["La direzione ricevuta/inviata è stimata dal percorso della sorgente."]
            if candidates
            else ["Nessuna sorgente email trovata."]
        ),
        "source_details": source_rows,
    }
    write_report(reports / "inventory_report.json", "Inventario archivio", result)
    write_report(reports / "inventory_report.html", "Inventario archivio", result)
    return result
