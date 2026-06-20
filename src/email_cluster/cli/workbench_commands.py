from __future__ import annotations

# ruff: noqa: E701, E702

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from email_cluster.config import load_config
from email_cluster.llm.prompts import operational_context_prompt
from email_cluster.llm.review_assistant import validated_suggestion
from email_cluster.llm.schemas import OperationalContextSuggestion
from email_cluster.operational.builder import build_operational_contexts
from email_cluster.operational.export import export_context_report
from email_cluster.operational.service import context_row, exclude_email, move_email, split_context, update_context
from email_cluster.review.repository import ReviewRepository
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository

console = Console()


def register_workbench_commands(app: typer.Typer) -> None:
    @app.command("workbench")
    def workbench(project: Annotated[str,typer.Option("--project")], db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite"), config: Annotated[Path,typer.Option("--config")]=Path("config/default.yaml")) -> None:
        init_db(db)
        with connect(db) as con:
            pid=Repository(con).project_id(project); run_id=ReviewRepository(con).resolve_run(pid,"latest")
            result=build_operational_contexts(con,pid,run_id)
            stats=_archive_stats(con,pid)
            next_context=con.execute("SELECT id,name,review_priority FROM operational_contexts WHERE project_id=? AND review_status='pending' ORDER BY review_priority DESC LIMIT 1",(pid,)).fetchone()
        console.rule("STATO ARCHIVIO")
        for label,value in stats: console.print(f"{label}: [bold]{value}[/bold]")
        console.print(f"Contesti aggiornati: {result['contexts']} | assegnazioni: {result['assignments']} | email sospette: {result['suspicious']}")
        cfg=load_config(config)
        if not cfg.local_llm.enabled: console.print("[yellow]LLM locale disabilitato: nomi e spiegazioni sono euristici e possono richiedere rinomina.[/yellow]")
        console.rule("PROSSIMA AZIONE CONSIGLIATA")
        if next_context: console.print(f"Rivedi il contesto {next_context['id']}: {next_context['name']}\nComando: email-cluster review --context {next_context['id']} --db {db}")
        else: console.print(f"Esporta la classificazione finale.\nComando: email-cluster export-final --project {project} --db {db}")

    @app.command("review")
    def review(context: Annotated[int|None,typer.Option("--context")]=None, next_item: Annotated[bool,typer.Option("--next")]=False, project: Annotated[str,typer.Option("--project")]="archivio_storico", db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            if context is None or next_item:
                pid=Repository(con).project_id(project); row=con.execute("SELECT id FROM operational_contexts WHERE project_id=? AND review_status='pending' ORDER BY review_priority DESC LIMIT 1",(pid,)).fetchone()
                if not row: console.print("Nessun contesto pending."); return
                context=int(row["id"])
        _show_context(db,context)

    @app.command("review-context")
    def review_context(context: Annotated[int|None,typer.Option("--context")]=None, next_item: Annotated[bool,typer.Option("--next")]=False, project: Annotated[str,typer.Option("--project")]="archivio_storico", db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        review(context,next_item,project,db)

    @app.command("macro-review")
    def macro_review(project: Annotated[str,typer.Option("--project")]="archivio_storico", db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            pid=Repository(con).project_id(project); rows=list(con.execute("""SELECT eca.macro_category,count(DISTINCT eca.email_id) n,group_concat(DISTINCT substr(e.subject,1,60)) examples FROM email_context_assignments eca JOIN operational_contexts oc ON oc.id=eca.operational_context_id JOIN emails e ON e.id=eca.email_id WHERE oc.project_id=? AND eca.review_status!='moved' GROUP BY eca.macro_category ORDER BY n DESC""",(pid,)))
        table=Table(title="Macro categorie prima dei contesti professionali"); table.add_column("categoria"); table.add_column("email"); table.add_column("esempi")
        for row in rows: table.add_row(row["macro_category"].replace("_"," "),str(row["n"]),(row["examples"] or "")[:160])
        console.print(table)

    _register_context_actions(app)

    @app.command("ask-context-llm")
    def ask_llm(context: Annotated[int,typer.Option("--context")], db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite"), config: Annotated[Path,typer.Option("--config")]=Path("config/default.yaml")) -> None:
        cfg=load_config(config).local_llm
        with connect(db) as con:
            row=context_row(con,context); cards=[dict(item) for item in con.execute("""SELECT e.id,e.subject,e.sender,e.sent_at,substr(c.current_message_text,1,500) current_message,substr(sc.thread_context_summary,1,300) thread_summary,substr(sc.attachment_summary,1,300) attachment_summary,eca.is_suspicious FROM email_context_assignments eca JOIN emails e ON e.id=eca.email_id LEFT JOIN clean_texts c ON c.id=(SELECT max(c2.id) FROM clean_texts c2 WHERE c2.email_id=e.id) LEFT JOIN semantic_contexts sc ON sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=e.id) WHERE eca.operational_context_id=? LIMIT 20""",(context,))]
            prompt=operational_context_prompt(json.dumps({"current_context":dict(row),"email_cards":cards},ensure_ascii=False)[:cfg.max_input_chars])
            try:
                suggestion=validated_suggestion(con,prompt,OperationalContextSuggestion,cfg)
            except RuntimeError as exc:
                console.print(f"LLM non disponibile: {exc}"); return
            con.execute("""UPDATE operational_contexts SET name=?,description=?,context_type=?,client_or_entity=?,technical_domain=?,practice_or_topic=?,why_grouped=?,suggested_user_action=?,source='llm',confidence=?,llm_used=1,updated_at=datetime('now') WHERE id=?""",(suggestion.context_name,suggestion.summary,suggestion.context_type,suggestion.client_or_entity,suggestion.technical_domain,suggestion.practice_or_topic,suggestion.why_grouped,suggestion.suggested_user_action,suggestion.confidence,context))
            for email_id in suggestion.emails_that_do_not_fit: con.execute("UPDATE email_context_assignments SET is_suspicious=1,reason='LLM segnala fuori contesto' WHERE operational_context_id=? AND email_id=?",(context,email_id))
        console.print(f"Proposta LLM salvata per il contesto {context}; richiede conferma umana.")

    @app.command("export-context-report")
    def export_report(project: Annotated[str,typer.Option("--project")]="archivio_storico", output: Annotated[Path,typer.Option("--output")]=Path("data/output/context_report.html"), fmt: Annotated[str,typer.Option("--format")]="html", db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: count=export_context_report(con,Repository(con).project_id(project),output,fmt)
        console.print(f"Report contesti: {output} ({count} email)")

    @app.command("export-final")
    def export_final(project: Annotated[str,typer.Option("--project")], output: Annotated[Path,typer.Option("--output")]=Path("data/output/context_report.html"), db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: count=export_context_report(con,Repository(con).project_id(project),output,"html")
        console.print(f"Classificazione finale esportata: {output} ({count} email)")


def _register_context_actions(app: typer.Typer) -> None:
    @app.command("approve-context")
    def approve(context: Annotated[int,typer.Option("--context")], db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: update_context(con,context,"approve",review_status="approved",source="human",suggested_user_action="completato")
        console.print(f"Contesto {context} approvato.")

    @app.command("rename-context")
    def rename(context: Annotated[int,typer.Option("--context")], name: Annotated[str,typer.Option("--name")], db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: update_context(con,context,"rename",name=name,source="human",review_status="approved")

    @app.command("exclude-from-context")
    def exclude(context: Annotated[int,typer.Option("--context")], email_id: Annotated[int,typer.Option("--email-id")], reason: Annotated[str,typer.Option("--reason")]="fuori contesto", db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: exclude_email(con,context,email_id,reason)

    @app.command("move-to-context")
    def move(email_id: Annotated[int,typer.Option("--email-id")], context: Annotated[int,typer.Option("--context")], db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: move_email(con,email_id,context)

    @app.command("split-context")
    def split(context: Annotated[int,typer.Option("--context")], db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: ids=split_context(con,context)
        console.print(f"Contesti proposti: {ids}" if ids else "Split non affidabile: usa rinomina/sposta email.")

    @app.command("mark-context-nonprofessional")
    def nonprofessional(context: Annotated[int,typer.Option("--context")], db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: update_context(con,context,"mark_nonprofessional",macro_category="personale",context_type="personale",source="human",review_status="approved")


def _show_context(db: Path, context_id: int) -> None:
    with connect(db) as con:
        row=context_row(con,context_id); emails=list(con.execute("""SELECT e.id,e.subject,e.sender,eca.confidence,eca.reason,eca.is_suspicious FROM email_context_assignments eca JOIN emails e ON e.id=eca.email_id WHERE eca.operational_context_id=? AND eca.review_status!='excluded' ORDER BY eca.is_suspicious DESC,eca.confidence LIMIT 50""",(context_id,)))
    console.rule("CONTESTO PROPOSTO")
    console.print(f"Nome: [bold]{row['name']}[/bold]\nTipo: {row['context_type']}\nMacro: {row['macro_category'].replace('_',' ')}\nCliente/ente: {row['client_or_entity'] or '-'}\nDominio: {row['technical_domain'] or '-'}\nSintesi: {row['description']}\nPerché insieme: {row['why_grouped']}\nConfidenza: {row['confidence']:.1%}\nAzione consigliata: [bold]{row['suggested_user_action']}[/bold]")
    table=Table(title="Email incluse e sospette"); table.add_column("id"); table.add_column("stato"); table.add_column("subject"); table.add_column("motivo")
    for email in emails: table.add_row(str(email["id"]),"SOSPETTA" if email["is_suspicious"] else "inclusa",_safe(email["subject"]),_safe(email["reason"]))
    console.print(table)
    console.print(f"Azioni: approve-context | rename-context | exclude-from-context | move-to-context | split-context | mark-context-nonprofessional\nLLM: ask-context-llm --context {context_id}")


def _archive_stats(con, project_id: int) -> list[tuple[str,int]]:
    total=con.execute("SELECT count(*) FROM emails WHERE project_id=?",(project_id,)).fetchone()[0]
    macro=dict(con.execute("""SELECT eca.macro_category,count(DISTINCT eca.email_id) FROM email_context_assignments eca JOIN operational_contexts oc ON oc.id=eca.operational_context_id WHERE oc.project_id=? AND eca.review_status!='moved' GROUP BY eca.macro_category""",(project_id,)).fetchall())
    attachments=con.execute("SELECT count(DISTINCT e.id) FROM emails e JOIN attachments a ON a.email_id=e.id WHERE e.project_id=?",(project_id,)).fetchone()[0]
    threads=con.execute("SELECT count(DISTINCT e.id) FROM emails e JOIN semantic_contexts sc ON sc.email_id=e.id WHERE e.project_id=? AND sc.context_strategy='thread_dominant'",(project_id,)).fetchone()[0]
    insufficient=macro.get("rumore_non_classificabile",0)
    professional=macro.get("professionale_operativo",0)+macro.get("professionale_amministrativo",0)
    nonprofessional=total-professional
    return [("Email totali",total),("Email professionali candidate",professional),("Automatiche/personali/newsletter",nonprofessional),("Email con allegati",attachments),("Email con thread utile",threads),("Email senza contesto sufficiente",insufficient)]


def _safe(value: object) -> str:
    return str(value or "").encode("cp1252", errors="replace").decode("cp1252")
