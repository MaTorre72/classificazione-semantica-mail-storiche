from __future__ import annotations

# ruff: noqa: E702

import csv
import html
import sqlite3
from pathlib import Path


def context_dataset(con: sqlite3.Connection, project_id: int) -> list[dict[str, object]]:
    return [dict(row) for row in con.execute("""
        SELECT e.id email_id,e.subject,e.sender,e.sent_at date,eca.macro_category,
            oc.name operational_context_name,oc.context_type,oc.client_or_entity,
            oc.technical_domain,oc.practice_or_topic,eca.review_status final_status,
            CASE WHEN eca.assignment_source='human' OR oc.source='human' THEN 1 ELSE 0 END human_reviewed,
            oc.llm_used,eca.confidence,eca.reason notes
        FROM email_context_assignments eca JOIN emails e ON e.id=eca.email_id
        JOIN operational_contexts oc ON oc.id=eca.operational_context_id
        WHERE oc.project_id=? AND eca.review_status!='moved'
          AND eca.id=(SELECT max(x.id) FROM email_context_assignments x WHERE x.email_id=eca.email_id AND x.review_status!='moved')
        ORDER BY e.id
    """, (project_id,))]


def export_context_report(con: sqlite3.Connection, project_id: int, output: Path, fmt: str = "html") -> int:
    rows = context_dataset(con, project_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv":
        with output.open("w",newline="",encoding="utf-8") as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]) if rows else ["email_id"]); writer.writeheader(); writer.writerows(rows)
        return len(rows)
    contexts = list(con.execute("""
        SELECT oc.*,count(eca.id) email_count,min(e.sent_at) first_date,max(e.sent_at) last_date
        FROM operational_contexts oc LEFT JOIN email_context_assignments eca ON eca.operational_context_id=oc.id AND eca.review_status NOT IN ('excluded','moved')
        LEFT JOIN emails e ON e.id=eca.email_id WHERE oc.project_id=? GROUP BY oc.id HAVING email_count>0 ORDER BY oc.review_status,oc.review_priority DESC
    """,(project_id,)))
    macro = list(con.execute("SELECT eca.macro_category,count(DISTINCT eca.email_id) n FROM email_context_assignments eca JOIN operational_contexts oc ON oc.id=eca.operational_context_id WHERE oc.project_id=? AND eca.review_status!='moved' GROUP BY eca.macro_category",(project_id,)))
    total = con.execute("SELECT count(*) FROM emails WHERE project_id=?",(project_id,)).fetchone()[0]
    parts=["<!doctype html><meta charset='utf-8'><title>Contesti operativi</title><style>body{font:15px Arial;max-width:1100px;margin:30px auto;color:#222}section{border-top:1px solid #ccc;padding:14px 0}.pending{border-left:4px solid #c47b00;padding-left:12px}.approved{border-left:4px solid #25824a;padding-left:12px}</style>","<h1>Classificazione per contesti operativi</h1>",f"<p>Email totali: <b>{total}</b> · Contesti: <b>{len(contexts)}</b></p>","<h2>Macro categorie</h2><ul>"]
    parts += [f"<li>{html.escape(row['macro_category'].replace('_',' '))}: {row['n']}</li>" for row in macro]
    parts.append("</ul><h2>Contesti</h2>")
    for row in contexts:
        senders = [item["sender"] for item in con.execute("""SELECT e.sender,count(*) n FROM email_context_assignments eca JOIN emails e ON e.id=eca.email_id WHERE eca.operational_context_id=? AND eca.review_status!='excluded' GROUP BY e.sender ORDER BY n DESC LIMIT 5""",(row["id"],))]
        attachments = [item["attachment_type"] or "altro" for item in con.execute("""SELECT a.attachment_type,count(*) n FROM email_context_assignments eca JOIN attachments a ON a.email_id=eca.email_id WHERE eca.operational_context_id=? AND eca.review_status!='excluded' GROUP BY a.attachment_type ORDER BY n DESC LIMIT 5""",(row["id"],))]
        examples = [item["subject"] or "" for item in con.execute("""SELECT e.subject FROM email_context_assignments eca JOIN emails e ON e.id=eca.email_id WHERE eca.operational_context_id=? AND eca.review_status!='excluded' ORDER BY eca.confidence DESC LIMIT 5""",(row["id"],))]
        parts.append(f"<section class='{html.escape(row['review_status'])}'><h3>{html.escape(row['name'])}</h3><p><b>{html.escape(row['context_type'])}</b> · {row['email_count']} email · {html.escape(row['first_date'] or '')} — {html.escape(row['last_date'] or '')}</p><p>{html.escape(row['description'] or '')}</p><p><b>Perché insieme:</b> {html.escape(row['why_grouped'] or '')}</p><p><b>Interlocutori:</b> {html.escape(', '.join(senders))}</p><p><b>Allegati:</b> {html.escape(', '.join(attachments))}</p><p><b>Email rappresentative:</b> {html.escape(' | '.join(examples))}</p><p><b>Stato:</b> {html.escape(row['review_status'])} · <b>Azione:</b> {html.escape(row['suggested_user_action'] or '')}</p></section>")
    output.write_text("".join(parts),encoding="utf-8")
    return len(rows)
