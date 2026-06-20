from __future__ import annotations

import csv
import html
import json
import sqlite3
from pathlib import Path


def final_rows(con: sqlite3.Connection, session_id: int) -> list[dict[str, object]]:
    return [dict(row) for row in con.execute("""
        SELECT e.id, e.subject, e.sender, e.sent_at AS date,
            COALESCE(er.human_topic_label, cr.final_label, c.label_auto) final_label,
            er.human_topic_label human_label, cr.llm_label,
            er.original_cluster_id auto_cluster_id,
            COALESCE(er.human_cluster_id, er.original_cluster_id) final_cluster_id,
            er.review_status, er.auto_message_type message_type,
            NULL AS professional_relevance,
            sc.semantic_summary, er.human_notes notes
        FROM email_reviews er JOIN emails e ON e.id=er.email_id
        LEFT JOIN cluster_reviews cr ON cr.review_session_id=er.review_session_id
            AND cr.cluster_id=COALESCE(er.human_cluster_id, er.original_cluster_id)
        LEFT JOIN clusters c ON c.clustering_run_id=er.clustering_run_id AND c.cluster_id=er.original_cluster_id
        LEFT JOIN semantic_contexts sc ON sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=e.id)
        WHERE er.review_session_id=? ORDER BY e.id
    """, (session_id,))]


def export_dataset(con: sqlite3.Connection, session_id: int, output: Path, fmt: str) -> int:
    rows = final_rows(con, session_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "csv":
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["id"])
            writer.writeheader()
            writer.writerows(rows)
    elif fmt == "html":
        headers = list(rows[0]) if rows else ["id"]
        lines = ["<!doctype html><meta charset='utf-8'><table><thead><tr>"]
        lines.extend(f"<th>{html.escape(header)}</th>" for header in headers)
        lines.append("</tr></thead><tbody>")
        for row in rows:
            lines.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(header) or ''))}</td>" for header in headers) + "</tr>")
        lines.append("</tbody></table>")
        output.write_text("".join(lines), encoding="utf-8")
    else:
        raise ValueError("Formato supportato: csv, json o html")
    return len(rows)


def write_final_report(con: sqlite3.Connection, session_id: int, output: Path) -> None:
    session = con.execute("SELECT * FROM review_sessions WHERE id=?", (session_id,)).fetchone()
    statuses = list(con.execute("SELECT review_status, count(*) n FROM cluster_reviews WHERE review_session_id=? GROUP BY review_status", (session_id,)))
    labels = list(con.execute("SELECT final_label, count(*) n FROM cluster_reviews WHERE review_session_id=? GROUP BY final_label ORDER BY n DESC", (session_id,)))
    body = ["<h1>Classificazione finale</h1>", f"<p>Sessione: {html.escape(session['name'])}</p>", "<h2>Stato cluster</h2><ul>"]
    body += [f"<li>{html.escape(row['review_status'])}: {row['n']}</li>" for row in statuses]
    body += ["</ul><h2>Tassonomia consolidata</h2><ul>"]
    body += [f"<li>{html.escape(row['final_label'] or 'Senza label')}: {row['n']}</li>" for row in labels]
    body += ["</ul><p>Automatico, LLM e decisione umana sono conservati separatamente nel database.</p>"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("<!doctype html><meta charset='utf-8'><title>Report finale</title>" + "".join(body), encoding="utf-8")
