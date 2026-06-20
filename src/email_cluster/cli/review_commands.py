from __future__ import annotations

# ruff: noqa: E701, E702

import json
import sqlite3
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from email_cluster.active_learning.engine import apply_rules, suggest_from_examples
from email_cluster.config import load_config
from email_cluster.llm.client import LocalLlmClient
from email_cluster.llm.prompts import cluster_prompt, email_prompt
from email_cluster.llm.review_assistant import validated_suggestion
from email_cluster.llm.schemas import ClusterReviewSuggestion, EmailReviewSuggestion
from email_cluster.review.analysis import suggest_cluster_merges, suggest_cluster_splits
from email_cluster.review.export import export_dataset, write_final_report
from email_cluster.review.repository import ReviewRepository
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, json_dumps, utcnow

console = Console()


def register_review_commands(app: typer.Typer) -> None:
    @app.command("review-start")
    def review_start(
        project: Annotated[str, typer.Option("--project")], run: Annotated[str, typer.Option("--run")] = "latest",
        db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite"),
        name: Annotated[str | None, typer.Option("--name")] = None,
    ) -> None:
        init_db(db)
        with connect(db) as con:
            project_id = Repository(con).project_id(project)
            reviews = ReviewRepository(con)
            run_id = reviews.resolve_run(project_id, run)
            session_id = reviews.start_session(project_id, run_id, name)
        console.print(f"Review session creata: {session_id} | run {run_id}")

    @app.command("review-dashboard")
    def review_dashboard(session: Annotated[int, typer.Option("--session")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            session_row = _session(con, session)
            cluster_stats = list(con.execute("SELECT review_status, count(*) n FROM cluster_reviews WHERE review_session_id=? GROUP BY review_status", (session,)))
            email_stats = list(con.execute("SELECT review_status, count(*) n FROM email_reviews WHERE review_session_id=? GROUP BY review_status", (session,)))
            excluded = con.execute("SELECT count(*) FROM email_reviews WHERE review_session_id=? AND original_cluster_id IS NULL", (session,)).fetchone()[0]
            noise = con.execute("SELECT count(*) FROM email_reviews WHERE review_session_id=? AND original_cluster_id=-1", (session,)).fetchone()[0]
            low_quality = con.execute("SELECT count(*) FROM cluster_reviews cr JOIN clusters c ON c.clustering_run_id=cr.clustering_run_id AND c.cluster_id=cr.cluster_id WHERE cr.review_session_id=? AND (c.coherence_score<0.55 OR c.mean_probability<0.6)", (session,)).fetchone()[0]
        console.print(f"Sessione {session}: {session_row['name']} | stato {session_row['status']} | cluster critici {low_quality} | rumore {noise} | escluse a monte {excluded}")
        console.print("Cluster: " + ", ".join(f"{r['review_status']}={r['n']}" for r in cluster_stats))
        console.print("Email: " + ", ".join(f"{r['review_status']}={r['n']}" for r in email_stats))

    @app.command("review-cluster")
    def review_cluster(session: Annotated[int, typer.Option("--session")], cluster: Annotated[int, typer.Option("--cluster")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            review = con.execute("""SELECT cr.*, c.* FROM cluster_reviews cr JOIN clusters c ON c.clustering_run_id=cr.clustering_run_id AND c.cluster_id=cr.cluster_id WHERE cr.review_session_id=? AND cr.cluster_id=?""", (session, cluster)).fetchone()
            if not review:
                raise typer.BadParameter("Cluster review non trovata")
            emails = list(con.execute("""SELECT e.id,e.subject,e.sender,ec.probability FROM email_clusters ec JOIN emails e ON e.id=ec.email_id WHERE ec.clustering_run_id=? AND ec.cluster_id=? ORDER BY ec.probability LIMIT 10""", (review["clustering_run_id"], cluster)))
        console.print(f"Cluster {cluster} | stato {review['review_status']} | priorita {review['review_priority']:.1f}")
        console.print(f"Auto: {review['auto_label']} | LLM: {review['llm_label'] or '-'} | Umano: {review['human_label'] or '-'} | Finale: {review['final_label']}")
        console.print(f"Size {review['size']} | probabilita {review['mean_probability'] or 0:.3f} | coerenza {review['coherence_score'] or 0:.3f}")
        console.print("Keyword: " + ", ".join(json.loads(review["keywords_json"] or "[]")))
        console.print("Sender: " + ", ".join(json.loads(review["recurring_senders_json"] or "[]")))
        if review["llm_summary"]:
            console.print("Sintesi LLM: " + review["llm_summary"])
        table = Table(title="Email borderline")
        table.add_column("id")
        table.add_column("prob.")
        table.add_column("subject")
        for row in emails:
            table.add_row(str(row["id"]), f"{row['probability'] or 0:.3f}", row["subject"] or "")
        console.print(table)

    _register_cluster_actions(app)
    _register_email_actions(app)
    _register_taxonomy_commands(app)
    _register_llm_commands(app)
    _register_analysis_commands(app)
    _register_export_commands(app)

    @app.command("review-next")
    def review_next(session: Annotated[int, typer.Option("--session")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            cluster = con.execute("SELECT cluster_id, review_priority, auto_label FROM cluster_reviews WHERE review_session_id=? AND review_status='pending' ORDER BY review_priority DESC LIMIT 1", (session,)).fetchone()
            email = con.execute("SELECT email_id, review_priority FROM email_reviews WHERE review_session_id=? AND review_status='pending' ORDER BY review_priority DESC LIMIT 1", (session,)).fetchone()
        if cluster and (not email or cluster["review_priority"] >= email["review_priority"]):
            console.print(f"Prossimo cluster: {cluster['cluster_id']} | priorita {cluster['review_priority']:.1f} | {cluster['auto_label']}")
        elif email:
            console.print(f"Prossima email: {email['email_id']} | priorita {email['review_priority']:.1f}")
        else:
            console.print("Nessun elemento pending.")


def _register_cluster_actions(app: typer.Typer) -> None:
    def update(session: int, cluster: int, status: str, db: Path, label: str | None = None, notes: str | None = None, action: str | None = None) -> None:
        with connect(db) as con:
            ReviewRepository(con).update_cluster(session, cluster, status, label=label, notes=notes, action=action)
        console.print(f"Cluster {cluster}: {status}")

    @app.command("approve-cluster")
    def approve(session: Annotated[int, typer.Option("--session")], cluster: Annotated[int, typer.Option("--cluster")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        update(session, cluster, "approved", db, action="approve")

    @app.command("rename-cluster")
    def rename(session: Annotated[int, typer.Option("--session")], cluster: Annotated[int, typer.Option("--cluster")], label: Annotated[str, typer.Option("--label")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        update(session, cluster, "renamed", db, label=label, action="rename")

    @app.command("reject-cluster")
    def reject(session: Annotated[int, typer.Option("--session")], cluster: Annotated[int, typer.Option("--cluster")], reason: Annotated[str, typer.Option("--reason")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        update(session, cluster, "rejected", db, notes=reason, action="exclude")

    for command, status, action in (("mark-cluster-mixed", "mixed", "inspect_emails"), ("mark-cluster-split", "needs_split", "split")):
        def handler(session: Annotated[int, typer.Option("--session")], cluster: Annotated[int, typer.Option("--cluster")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite"), _status=status, _action=action) -> None:
            update(session, cluster, _status, db, action=_action)
        app.command(command)(handler)

    @app.command("merge-clusters")
    def merge(session: Annotated[int, typer.Option("--session")], clusters: Annotated[str, typer.Option("--clusters")], label: Annotated[str, typer.Option("--label")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        ids = [int(value.strip()) for value in clusters.split(",")]
        with connect(db) as con:
            reviews = ReviewRepository(con)
            for cluster_id in ids:
                reviews.update_cluster(session, cluster_id, "needs_merge", label=label, action="merge")
        console.print(f"Merge proposto per {ids}: {label}")


def _register_email_actions(app: typer.Typer) -> None:
    @app.command("move-email")
    def move(session: Annotated[int, typer.Option("--session")], email_id: Annotated[int, typer.Option("--email-id")], to_cluster: Annotated[int, typer.Option("--to-cluster")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: ReviewRepository(con).update_email(session, email_id, "moved", cluster_id=to_cluster)
        console.print(f"Email {email_id} spostata nella revisione al cluster {to_cluster}")

    @app.command("exclude-email")
    def exclude(session: Annotated[int, typer.Option("--session")], email_id: Annotated[int, typer.Option("--email-id")], reason: Annotated[str, typer.Option("--reason")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: ReviewRepository(con).update_email(session, email_id, "excluded", notes=reason)

    @app.command("set-email-label")
    def set_label(session: Annotated[int, typer.Option("--session")], email_id: Annotated[int, typer.Option("--email-id")], label: Annotated[str, typer.Option("--label")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: ReviewRepository(con).update_email(session, email_id, "approved", label=label)


def _register_taxonomy_commands(app: typer.Typer) -> None:
    @app.command("add-taxonomy-label")
    def add_label(project: Annotated[str, typer.Option("--project")], label: Annotated[str, typer.Option("--label")], label_type: Annotated[str, typer.Option("--type")] = "altro", description: Annotated[str, typer.Option("--description")] = "", db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            pid = Repository(con).project_id(project); label_id = ReviewRepository(con).add_taxonomy_label(pid, label, label_type, description)
        console.print(f"Label creata: {label_id} {label}")

    @app.command("add-label-example")
    def add_example(label: Annotated[str, typer.Option("--label")], email_id: Annotated[int, typer.Option("--email-id")], example_type: Annotated[str, typer.Option("--type")] = "positive", db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            row = con.execute("SELECT id FROM taxonomy_labels WHERE label=? AND active=1 ORDER BY id DESC LIMIT 1", (label,)).fetchone()
            if not row: raise typer.BadParameter("Label non trovata")
            ReviewRepository(con).add_example(int(row["id"]), email_id, example_type)

    @app.command("add-label-rule")
    def add_rule(label: Annotated[str, typer.Option("--label")], rule_type: Annotated[str, typer.Option("--type")], pattern: Annotated[str, typer.Option("--pattern")], project: Annotated[str, typer.Option("--project")] = "archivio_storico", db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            pid = Repository(con).project_id(project); row = con.execute("SELECT id FROM taxonomy_labels WHERE project_id=? AND label=?", (pid, label)).fetchone()
            if not row: raise typer.BadParameter("Label non trovata")
            rule_id = ReviewRepository(con).add_rule(pid, int(row["id"]), rule_type, pattern)
        console.print(f"Regola creata: {rule_id}")

    @app.command("suggest-from-examples")
    def suggest_examples(project: Annotated[str, typer.Option("--project")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: suggestions = suggest_from_examples(con, Repository(con).project_id(project))
        console.print_json(data=suggestions[:100])

    @app.command("apply-label-rules")
    def rules(project: Annotated[str, typer.Option("--project")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: matches = apply_rules(con, Repository(con).project_id(project))
        console.print_json(data=matches[:200])


def _register_llm_commands(app: typer.Typer) -> None:
    @app.command("llm-check")
    def llm_check(db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite"), config: Annotated[Path, typer.Option("--config")] = Path("config/default.yaml")) -> None:
        cfg = load_config(config).local_llm; client = LocalLlmClient(cfg)
        console.print(f"enabled={cfg.enabled} backend={cfg.backend} model={client.model_name}")
        if not cfg.enabled: console.print("LLM disabilitato: la revisione resta completamente funzionale."); return
        try: parsed, _, elapsed = client.generate_json('Restituisci {"ok": true}'); console.print(f"OK {elapsed} ms: {parsed}")
        except Exception as exc: console.print(f"ERRORE: {exc}")

    @app.command("llm-label-clusters")
    def label_clusters(project: Annotated[str, typer.Option("--project")], run: Annotated[str, typer.Option("--run")] = "latest", db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite"), config: Annotated[Path, typer.Option("--config")] = Path("config/default.yaml")) -> None:
        cfg = load_config(config).local_llm
        with connect(db) as con:
            pid = Repository(con).project_id(project); reviews = ReviewRepository(con); run_id = reviews.resolve_run(pid, run)
            llm_run = con.execute("INSERT INTO llm_runs (project_id,run_type,backend,model,prompt_version,started_at,status,parameters_json) VALUES (?,?,?,?,?,?,?,?)", (pid,"cluster_labeling",cfg.backend,cfg.model or cfg.model_path,"review-v1",utcnow(),"running","{}")); llm_run_id=int(llm_run.lastrowid)
            success=errors=0
            for cluster in con.execute("SELECT * FROM clusters WHERE clustering_run_id=?", (run_id,)):
                context = json_dumps({"cluster_id":cluster["cluster_id"],"label":cluster["label_auto"],"keywords":json.loads(cluster["keywords_json"] or "[]"),"subjects":json.loads(cluster["recurring_subjects_json"] or "[]"),"representatives":json.loads(cluster["representative_email_ids_json"] or "[]")})
                try:
                    suggestion=validated_suggestion(con,cluster_prompt(context),ClusterReviewSuggestion,cfg)
                    con.execute("INSERT INTO llm_cluster_suggestions (clustering_run_id,cluster_id,llm_run_id,suggestion_json,confidence,created_at) VALUES (?,?,?,?,?,?)",(run_id,cluster["cluster_id"],llm_run_id,json_dumps(suggestion.model_dump()),suggestion.confidence,utcnow()))
                    con.execute("UPDATE cluster_reviews SET llm_label=?,llm_summary=?,llm_confidence=?,suggested_action=?,updated_at=? WHERE clustering_run_id=? AND cluster_id=? AND review_status='pending'",(suggestion.cluster_label,suggestion.cluster_summary,suggestion.confidence,"split" if suggestion.is_mixed_cluster else "approve",utcnow(),run_id,cluster["cluster_id"])); success+=1
                except RuntimeError: errors+=1
            con.execute("UPDATE llm_runs SET status=?,completed_at=? WHERE id=?",("completed" if not errors else "partial",utcnow(),llm_run_id))
        console.print(f"Suggerimenti LLM: {success} | errori/fallback: {errors}")

    @app.command("llm-triage-emails")
    def triage(project: Annotated[str, typer.Option("--project")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite"), config: Annotated[Path, typer.Option("--config")] = Path("config/default.yaml"), only_uncertain: Annotated[bool, typer.Option("--only-uncertain")] = True) -> None:
        cfg=load_config(config).local_llm
        with connect(db) as con:
            pid=Repository(con).project_id(project); llm_run_id=int(con.execute("INSERT INTO llm_runs (project_id,run_type,backend,model,prompt_version,started_at,status) VALUES (?,?,?,?,?,?,'running')",(pid,"email_triage",cfg.backend,cfg.model or cfg.model_path,"review-v1",utcnow())).lastrowid)
            sql="""SELECT e.id,sc.semantic_text_for_embedding FROM emails e JOIN semantic_contexts sc ON sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=e.id) LEFT JOIN email_clusters ec ON ec.email_id=e.id WHERE e.project_id=?""" + (" AND (ec.is_noise=1 OR ec.probability<0.5 OR sc.context_strategy IN ('attachment_dominant','thread_dominant'))" if only_uncertain else "") + " GROUP BY e.id LIMIT 200"
            success=0
            for row in con.execute(sql,(pid,)):
                try:
                    suggestion=validated_suggestion(con,email_prompt(row["semantic_text_for_embedding"]),EmailReviewSuggestion,cfg); con.execute("INSERT INTO llm_email_suggestions (email_id,llm_run_id,suggestion_json,confidence,created_at) VALUES (?,?,?,?,?)",(row["id"],llm_run_id,json_dumps(suggestion.model_dump()),suggestion.confidence,utcnow())); success+=1
                except RuntimeError: pass
            con.execute("UPDATE llm_runs SET status='completed',completed_at=? WHERE id=?",(utcnow(),llm_run_id))
        console.print(f"Email triage completate: {success}")

    @app.command("llm-review-report")
    def llm_report(session: Annotated[int, typer.Option("--session")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            row=con.execute("SELECT count(*) total,sum(llm_label IS NOT NULL) proposed,avg(llm_confidence) confidence FROM cluster_reviews WHERE review_session_id=?",(session,)).fetchone()
        console.print(f"Cluster: {row['total']} | proposte LLM: {row['proposed'] or 0} | confidenza media: {row['confidence'] or 0:.3f}")

    @app.command("llm-suggest-taxonomy")
    def suggest_taxonomy(project: Annotated[str, typer.Option("--project")], db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            pid = Repository(con).project_id(project)
            labels = [dict(row) for row in con.execute("""
                SELECT label_auto label, keywords_json keywords, size FROM clusters
                WHERE clustering_run_id=(SELECT max(id) FROM clustering_runs WHERE project_id=?)
                  AND cluster_id!=-1 ORDER BY size DESC
            """, (pid,))]
        proposal = [{"label": row["label"], "description": "Derivata dai cluster revisionabili", "label_type": "tema_tecnico", "source": "auto"} for row in labels]
        console.print_json(data={"labels": proposal})

    @app.command("review-ui")
    def review_ui(db: Annotated[Path, typer.Option("--db")] = Path("data/email_cluster.sqlite"), project: Annotated[str, typer.Option("--project")] = "archivio_storico") -> None:
        import os
        from email_cluster.gui.app import main

        console.print(f"Apertura review UI locale | progetto {project} | database {db}")
        os.environ["EMAIL_CLUSTER_PROJECT"] = project
        os.environ["EMAIL_CLUSTER_DB"] = str(db)
        main()


def _register_analysis_commands(app: typer.Typer) -> None:
    @app.command("suggest-splits")
    def splits(run: Annotated[str, typer.Option("--run")]="latest", project: Annotated[str, typer.Option("--project")]="archivio_storico", session: Annotated[int|None,typer.Option("--session")]=None, db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            pid=Repository(con).project_id(project); reviews=ReviewRepository(con); run_id=reviews.resolve_run(pid,run); items=suggest_cluster_splits(con,run_id)
            for item in items: reviews.save_suggestion(session,run_id,int(item["cluster_id"]),"split",item)
        console.print_json(data=items)

    @app.command("suggest-merges")
    def merges(run: Annotated[str, typer.Option("--run")]="latest", project: Annotated[str, typer.Option("--project")]="archivio_storico", session: Annotated[int|None,typer.Option("--session")]=None, db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            pid=Repository(con).project_id(project); reviews=ReviewRepository(con); run_id=reviews.resolve_run(pid,run); items=suggest_cluster_merges(con,run_id)
            for item in items: reviews.save_suggestion(session,run_id,None,"merge",item)
        console.print_json(data=items)

    @app.command("apply-split")
    def apply_split(session: Annotated[int,typer.Option("--session")], cluster: Annotated[int,typer.Option("--cluster")], db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con:
            con.execute("UPDATE review_suggestions SET status='accepted' WHERE review_session_id=? AND cluster_id=? AND suggestion_type='split' AND id=(SELECT max(id) FROM review_suggestions WHERE review_session_id=? AND cluster_id=? AND suggestion_type='split')",(session,cluster,session,cluster)); ReviewRepository(con).update_cluster(session,cluster,"needs_split",action="split")
        console.print("Split accettato come decisione di revisione; la run originale non e stata modificata.")


def _register_export_commands(app: typer.Typer) -> None:
    @app.command("export-review")
    def export_review(session: Annotated[int,typer.Option("--session")], output: Annotated[Path,typer.Option("--output")], fmt: Annotated[str,typer.Option("--format")]="csv", db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: count=export_dataset(con,session,output,fmt)
        console.print(f"Esportate {count} email")

    @app.command("export-final-dataset")
    def export_final(session: Annotated[int,typer.Option("--session")], output: Annotated[Path,typer.Option("--output")], fmt: Annotated[str,typer.Option("--format")]="csv", db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: count=export_dataset(con,session,output,fmt)
        console.print(f"Dataset finale: {output} ({count})")

    @app.command("final-classification-report")
    def final_report(session: Annotated[int,typer.Option("--session")], output: Annotated[Path,typer.Option("--output")]=Path("data/output/final_report.html"), db: Annotated[Path,typer.Option("--db")]=Path("data/email_cluster.sqlite")) -> None:
        with connect(db) as con: write_final_report(con,session,output)
        console.print(f"Report finale: {output}")


def _session(con: sqlite3.Connection, session_id: int) -> sqlite3.Row:
    row=con.execute("SELECT * FROM review_sessions WHERE id=?",(session_id,)).fetchone()
    if not row: raise typer.BadParameter("Sessione non trovata")
    return row
