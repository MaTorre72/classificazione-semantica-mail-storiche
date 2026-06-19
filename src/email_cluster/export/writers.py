from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path


def export_emails(con: sqlite3.Connection, output: Path, fmt: str, cluster: int | None = None) -> int:
    rows = _email_rows(con, cluster)
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        output.write_text(json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "csv":
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["id"])
            writer.writeheader()
            writer.writerows(dict(row) for row in rows)
    else:
        raise ValueError("format deve essere csv oppure json")
    return len(rows)


def write_markdown_report(con: sqlite3.Connection, output: Path, run_id: int | None = None) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    if run_id is None:
        row = con.execute("SELECT id FROM clustering_runs ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            run_id = int(row["id"])
    lines = ["# Report cluster", ""]
    if run_id is None:
        lines.append("Nessun clustering run presente.")
        output.write_text("\n".join(lines), encoding="utf-8")
        return 0
    total = con.execute(
        "SELECT count(*) FROM email_clusters WHERE clustering_run_id = ?", (run_id,)
    ).fetchone()[0]
    noise = con.execute(
        "SELECT count(*) FROM email_clusters WHERE clustering_run_id = ? AND is_noise = 1", (run_id,)
    ).fetchone()[0]
    rows = list(
        con.execute(
            """
            SELECT cluster_id, label_auto, keywords_json, representative_email_ids_json,
                   size, coherence_score
            FROM clusters
            WHERE clustering_run_id = ?
            ORDER BY cluster_id
            """,
            (run_id,),
        )
    )
    lines.append(f"Run: `{run_id}`")
    lines.append(f"Email clusterizzate: `{total}`")
    lines.append(f"Rumore: `{noise}` ({_percentage(noise, total)})")
    lines.append("")
    for row in rows:
        representative_rows = _representative_rows(
            con, json.loads(row["representative_email_ids_json"] or "[]")
        )
        lines.extend(
            [
                f"## Cluster {row['cluster_id']} - {row['label_auto']}",
                "",
                f"- Dimensione: {row['size']} ({_percentage(row['size'], total)})",
                f"- Coerenza: {_format_score(row['coherence_score'])}",
                f"- Keyword: {', '.join(json.loads(row['keywords_json'] or '[]'))}",
                "",
                "| ID | Mittente | Oggetto |",
                "| --- | --- | --- |",
            ]
        )
        for representative in representative_rows:
            lines.append(
                f"| {representative['id']} | {_escape_cell(representative['sender'])} | "
                f"{_escape_cell(representative['subject'])} |"
            )
        lines.append("")
    output.write_text("\n".join(lines), encoding="utf-8")
    return len(rows)


def _representative_rows(con: sqlite3.Connection, email_ids: list[int]) -> list[sqlite3.Row]:
    if not email_ids:
        return []
    placeholders = ",".join("?" for _ in email_ids)
    rows = list(
        con.execute(
            f"SELECT id, sender, subject FROM emails WHERE id IN ({placeholders})",
            email_ids,
        )
    )
    by_id = {int(row["id"]): row for row in rows}
    return [by_id[email_id] for email_id in email_ids if email_id in by_id]


def _percentage(value: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{value / total:.1%}"


def _format_score(value: float | None) -> str:
    return "n/d" if value is None else f"{value:.3f}"


def _escape_cell(value: str | None) -> str:
    return (value or "").replace("|", "\\|").replace("\n", " ")


def _email_rows(con: sqlite3.Connection, cluster: int | None) -> list[sqlite3.Row]:
    if cluster is None:
        return list(
            con.execute(
                """
                SELECT e.id, e.subject, e.sender, e.sent_at, c.language, c.clean_text
                FROM emails e
                LEFT JOIN clean_texts c ON c.id = (
                    SELECT c2.id FROM clean_texts c2
                    WHERE c2.email_id = e.id
                    ORDER BY c2.id DESC
                    LIMIT 1
                )
                ORDER BY e.id
                """
            )
        )
    return list(
        con.execute(
            """
            SELECT e.id, e.subject, e.sender, e.sent_at, c.language, c.clean_text,
                   ec.cluster_id, ec.probability
            FROM email_clusters ec
            JOIN emails e ON e.id = ec.email_id
            LEFT JOIN clean_texts c ON c.id = (
                SELECT c2.id FROM clean_texts c2
                WHERE c2.email_id = e.id
                ORDER BY c2.id DESC
                LIMIT 1
            )
            WHERE ec.cluster_id = ?
            ORDER BY e.id
            """,
            (cluster,),
        )
    )
