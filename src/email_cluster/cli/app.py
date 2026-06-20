from __future__ import annotations

from pathlib import Path
import json
import importlib.util
import platform
from itertools import islice, product
from typing import Annotated

import numpy as np
import typer
from rich.console import Console
from rich.table import Table

from email_cluster.cleaning.normalizer import build_clean_text
from email_cluster.attachments.summarizer import summarize_attachment
from email_cluster.attachments.classifier import classify_attachment
from email_cluster.context.builder import build_context
from email_cluster.llm.local import enrich_locally
from email_cluster.clustering.engine import run_clustering, summarize_clusters
from email_cluster.clustering.diagnostics import calculate_metrics, diagnostic_warnings
from email_cluster.config import load_config
from email_cluster.embeddings.engine import EmbeddingEngine
from email_cluster.export.writers import export_cluster_review, export_emails, write_markdown_report
from email_cluster.ingestion.scanner import file_sha256, scan_local_folder
from email_cluster.parsing.email_parser import parse_eml, parse_mbox
from email_cluster.storage.database import connect, init_db as create_schema
from email_cluster.storage.repository import Repository, blob_to_embedding
from email_cluster.cli.review_commands import register_review_commands
from email_cluster.cli.workbench_commands import register_workbench_commands


app = typer.Typer(help="Pipeline locale per classificazione semantica di archivi email.")
console = Console()


DbOpt = Annotated[Path, typer.Option("--db", help="Percorso database SQLite.")]
ConfigOpt = Annotated[Path | None, typer.Option("--config", help="File YAML di configurazione.")]


def _db_path(db: Path | None, config_path: Path | None) -> Path:
    config = load_config(config_path)
    return db or config.database.path


def _terminal_safe(value: object) -> str:
    text = "" if value is None else str(value)
    return text.encode("cp1252", errors="replace").decode("cp1252")


@app.command("init-db")
def init_db(db: DbOpt = Path("data/email_cluster.sqlite")) -> None:
    create_schema(db)
    console.print(f"Database pronto: {db}")


@app.command("import")
def import_emails(
    source: Annotated[Path, typer.Option("--source", exists=True, help="Cartella o file email.")],
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
) -> None:
    create_schema(db)
    cfg = load_config(config)
    imported = 0
    duplicates = 0
    unchanged_files = 0
    errors = 0
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.get_or_create_project(project)
        for candidate in scan_local_folder(source):
            candidate_path = str(candidate.path.resolve())
            file_hash = file_sha256(candidate.path)
            if repo.source_file_is_current(project_id, candidate_path, file_hash):
                unchanged_files += 1
                continue
            stat = candidate.path.stat()
            source_file_id = repo.upsert_source_file(
                project_id,
                candidate_path,
                candidate.file_type,
                file_hash,
                "importing",
                file_size=stat.st_size,
                modified_at=str(stat.st_mtime_ns),
            )
            found_for_file = 0
            imported_for_file = 0
            errors_for_file = 0
            try:
                parsed_messages = (
                    [parse_eml(
                        candidate.path,
                        extract_attachments=cfg.attachments.enabled and cfg.attachments.extract_text,
                        max_attachment_size_mb=cfg.attachments.max_file_size_mb,
                    )]
                    if candidate.file_type == "eml"
                    else parse_mbox(
                        candidate.path,
                        extract_attachments=cfg.attachments.enabled and cfg.attachments.extract_text,
                        max_attachment_size_mb=cfg.attachments.max_file_size_mb,
                    )
                )
                for parsed in parsed_messages:
                    found_for_file += 1
                    try:
                        email_id = repo.insert_email(project_id, source_file_id, parsed)
                        if email_id is None:
                            duplicates += 1
                        else:
                            imported += 1
                            imported_for_file += 1
                    except Exception as exc:  # noqa: BLE001 - isolation per malformed message
                        errors += 1
                        errors_for_file += 1
                        repo.record_error("parsing", exc, project_id, source_file_id)
                repo.upsert_source_file(
                    project_id, candidate_path, candidate.file_type, file_hash, "ok",
                    file_size=stat.st_size, modified_at=str(stat.st_mtime_ns),
                    emails_found=found_for_file, emails_imported=imported_for_file,
                    errors_count=errors_for_file,
                )
            except Exception as exc:  # noqa: BLE001 - isolation per source file
                errors += 1
                repo.record_error("ingestion", exc, project_id, source_file_id)
                repo.upsert_source_file(
                    project_id, candidate_path, candidate.file_type, file_hash, "error",
                    file_size=stat.st_size, modified_at=str(stat.st_mtime_ns),
                    emails_found=found_for_file, emails_imported=imported_for_file,
                    errors_count=errors_for_file + 1,
                )
    console.print(f"Importate: {imported} | Email duplicate: {duplicates} | File invariati: {unchanged_files} | Errori: {errors}")


@app.command("run-pipeline")
def run_pipeline(
    source: Annotated[Path, typer.Option("--source", exists=True, help="Cartella o file email.")],
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
    skip_ml: Annotated[bool, typer.Option("--skip-ml", help="Salta embedding e clustering.")] = False,
    export_dir: Annotated[Path, typer.Option("--export-dir", help="Cartella output.")] = Path("data/output"),
) -> None:
    console.rule("Init DB")
    init_db(db)
    console.rule("Import")
    import_emails(source=source, project=project, db=db, config=config)
    console.rule("Cleaning")
    clean(project=project, db=db, config=config)
    if not skip_ml:
        console.rule("Embedding")
        embed(project=project, db=db, config=config)
        console.rule("Clustering")
        cluster(project=project, db=db, config=config)
        console.rule("Cluster report")
        report(output=export_dir / "cluster_report.md", db=db)
    console.rule("Export")
    export_cmd(output=export_dir / "emails.csv", fmt="csv", db=db)
    export_cmd(output=export_dir / "emails.json", fmt="json", db=db)


@app.command("run")
def run_v2(
    input_path: Annotated[Path, typer.Option("--input", exists=True)] = Path("data/input"),
    project: Annotated[str, typer.Option("--project")] = "mail-storiche",
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
    profile: Annotated[str, typer.Option("--profile")] = "balanced",
    skip_ml: Annotated[bool, typer.Option("--skip-ml")] = False,
) -> None:
    console.rule("Import incrementale")
    import_emails(source=input_path, project=project, db=db, config=config)
    console.rule("Cleaning")
    clean(project=project, db=db, config=config)
    console.rule("Contesto semantico")
    prepare_context(project=project, db=db, config=config)
    if not skip_ml:
        console.rule("Embedding semantici")
        embed(project=project, db=db, config=config, limit=None, mode="semantic")
        console.rule("Clustering")
        cluster(project=project, db=db, config=config, profile=profile)
        console.rule("Report")
        report(output=Path("data/output/cluster_report.md"), db=db, run=None)
    console.rule("Stato")
    status(db=db, project=project, input_path=input_path)


@app.command("clean")
def clean(
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
) -> None:
    create_schema(db)
    cfg = load_config(config)
    count = 0
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.project_id(project)
        for row in repo.emails_needing_cleaning(project_id, cfg.cleaning.version):
            cleaned = build_clean_text(
                int(row["id"]),
                subject=row["subject"],
                body=row["body_extracted_text"] or row["body_plain"] or "",
                has_attachments=bool(row["has_attachments"]),
                config=cfg.cleaning,
            )
            repo.insert_clean_text(cleaned)
            count += 1
    console.print(f"Testi puliti creati: {count}")


@app.command("prepare-context")
def prepare_context(
    project: Annotated[str, typer.Option("--project")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
) -> None:
    create_schema(db)
    cfg = load_config(config)
    created = 0
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.project_id(project)
        for row in repo.emails_needing_context(project_id, cfg.semantic_preparation.version):
            attachment_parts: list[str] = []
            for attachment in repo.attachment_rows(int(row["id"])):
                attachment_type = attachment["attachment_type"]
                keywords = json.loads(attachment["attachment_keywords_json"] or "[]")
                if not attachment_type:
                    attachment_type, keywords = classify_attachment(attachment["filename"])
                    con.execute(
                        "UPDATE attachments SET attachment_type=?, attachment_keywords_json=? WHERE id=?",
                        (attachment_type, json.dumps(keywords, ensure_ascii=False), attachment["id"]),
                    )
                if attachment_type == "altro" and not attachment["extracted_text"]:
                    continue
                attachment_parts.append(summarize_attachment(
                    attachment["filename"], attachment_type or "altro", keywords,
                    attachment["extracted_text"], cfg.semantic_preparation.max_attachment_summary_chars,
                ))
            attachment_summary = "\n".join(attachment_parts)[: cfg.semantic_preparation.max_attachment_summary_chars]
            llm_input = "\n\n".join(filter(None, [
                row["subject_clean"] or row["subject"] or "",
                row["current_message_text"] or row["body_current_message_clean"] or "",
                row["quoted_thread_text"] or "",
                attachment_summary,
            ]))
            enrichment, llm_used, llm_error = enrich_locally(llm_input, cfg.local_llm)
            context = build_context(
                int(row["id"]), row["subject_clean"] or row["subject"] or "",
                row["current_message_text"] or row["body_current_message_clean"] or "",
                row["quoted_thread_text"] or "", row["message_type"], attachment_summary,
                cfg.semantic_preparation, enrichment,
            )
            context.llm_used = llm_used
            context.llm_model = str(cfg.local_llm.model_path) if llm_used else None
            context.llm_parameters = {"backend": cfg.local_llm.backend, "error": llm_error}
            repo.insert_semantic_context(context)
            created += 1
    console.print(f"Contesti semantici creati: {created}")


@app.command("clean-preview")
def clean_preview(
    email_id: Annotated[int, typer.Option("--email-id", help="ID email.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
) -> None:
    with connect(db) as con:
        row = con.execute(
            """
            SELECT e.subject, e.body_extracted_text, e.body_plain, c.*
            FROM emails e LEFT JOIN clean_texts c ON c.id = (
                SELECT id FROM clean_texts WHERE email_id = e.id ORDER BY id DESC LIMIT 1
            ) WHERE e.id = ?
            """,
            (email_id,),
        ).fetchone()
        if not row:
            raise typer.BadParameter(f"Email non trovata: {email_id}")
        fields = [
            ("subject originale", row["subject"]),
            ("testo estratto originale", row["body_extracted_text"] or row["body_plain"]),
            ("subject_clean", row["subject_clean"]),
            ("body_current_message_clean", row["body_current_message_clean"]),
            ("semantic_text", row["semantic_text"]),
            ("message_type", row["message_type"]),
            ("quality_score", row["quality_score"]),
            ("excluded_from_main_clustering", bool(row["excluded_from_main_clustering"])),
            ("exclusion_reason", row["exclusion_reason"]),
            ("cleaning_flags", row["cleaning_flags_json"]),
        ]
        for label, value in fields:
            console.rule(label)
            console.print(value if value not in (None, "") else "[dim](vuoto)[/dim]")


@app.command("cleaning-report")
def cleaning_report(
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
) -> None:
    with connect(db) as con:
        project_id = Repository(con).project_id(project)
        rows = list(con.execute("""
            SELECT e.id, e.subject, c.* FROM emails e JOIN clean_texts c ON c.id = (
                SELECT id FROM clean_texts WHERE email_id = e.id ORDER BY id DESC LIMIT 1
            ) WHERE e.project_id = ? ORDER BY e.id
        """, (project_id,)))
    if not rows:
        console.print("Nessun testo pulito disponibile.")
        return
    excluded = [row for row in rows if row["excluded_from_main_clustering"]]
    operational = [row for row in rows if not row["excluded_from_main_clustering"]]
    flags = [json.loads(row["cleaning_flags_json"] or "{}") for row in rows]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["message_type"]] = counts.get(row["message_type"], 0) + 1
    console.print(f"Totale email: {len(rows)} | operative: {len(operational)} | escluse: {len(excluded)}")
    console.print(f"Lunghezza media clean_text: {sum(len(r['clean_text']) for r in rows)/len(rows):.1f}")
    console.print(f"Lunghezza media semantic_text: {sum(len(r['semantic_text']) for r in rows)/len(rows):.1f}")
    console.print(f"Email troppo brevi: {sum('sotto' in (r['exclusion_reason'] or '') for r in rows)}")
    console.print("Distribuzione tipi: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for key in ("quoted_reply_removed", "disclaimer_removed", "signature_removed", "forwarded_block_removed"):
        console.print(f"{key}: {sum(bool(item.get(key)) for item in flags)}")
    for title, selected in (
        ("Prime 20 escluse", excluded[:20]),
        ("Operative piu corte", sorted(operational, key=lambda r: len(r["semantic_text"]))[:20]),
        ("Operative piu lunghe", sorted(operational, key=lambda r: len(r["semantic_text"]), reverse=True)[:20]),
    ):
        table = Table(title=title)
        for column in ("id", "tipo", "caratteri", "motivo", "oggetto"):
            table.add_column(column)
        for row in selected:
            table.add_row(str(row["email_id"]), row["message_type"], str(len(row["semantic_text"])), row["exclusion_reason"] or "", _terminal_safe(row["subject"]))
        console.print(table)


@app.command("context-report")
def context_report(project: Annotated[str, typer.Option("--project")], db: DbOpt = Path("data/email_cluster.sqlite")) -> None:
    create_schema(db)
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        rows = list(con.execute("""
            SELECT sc.* FROM semantic_contexts sc JOIN emails e ON e.id=sc.email_id
            WHERE e.project_id=? AND sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=sc.email_id)
        """, (pid,)))
    if not rows:
        console.print("Nessun contesto semantico. Esegui prepare-context.")
        return
    types: dict[str, int] = {}
    strategies: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for row in rows:
        types[row["message_type"]] = types.get(row["message_type"], 0) + 1
        strategies[row["context_strategy"]] = strategies.get(row["context_strategy"], 0) + 1
        if row["exclusion_reason"]:
            reasons[row["exclusion_reason"]] = reasons.get(row["exclusion_reason"], 0) + 1
    console.print(f"Totale: {len(rows)} | escluse: {sum(r['excluded_from_main_clustering'] for r in rows)} | LLM: {sum(r['llm_used'] for r in rows)}")
    console.print("Tipi: " + ", ".join(f"{k}={v}" for k, v in sorted(types.items())))
    console.print("Strategie: " + ", ".join(f"{k}={v}" for k, v in sorted(strategies.items())))
    console.print("Esclusioni: " + ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())))
    console.print(f"Lunghezza media semantic_text: {sum(len(r['semantic_text_for_embedding']) for r in rows)/len(rows):.1f}")
    table = Table(title="Contesti piu corti e piu lunghi")
    table.add_column("id")
    table.add_column("strategia")
    table.add_column("caratteri")
    extremes = sorted(rows, key=lambda r: len(r["semantic_text_for_embedding"]))[:20]
    extremes += sorted(rows, key=lambda r: len(r["semantic_text_for_embedding"]), reverse=True)[:20]
    for row in extremes:
        table.add_row(str(row["email_id"]), row["context_strategy"], str(len(row["semantic_text_for_embedding"])))
    console.print(table)


@app.command("attachment-report")
def attachment_report(project: Annotated[str, typer.Option("--project")], db: DbOpt = Path("data/email_cluster.sqlite")) -> None:
    create_schema(db)
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        rows = list(con.execute("""SELECT a.* FROM attachments a JOIN emails e ON e.id=a.email_id WHERE e.project_id=?""", (pid,)))
        dominant = con.execute("""SELECT count(*) FROM semantic_contexts sc JOIN emails e ON e.id=sc.email_id WHERE e.project_id=? AND sc.context_strategy='attachment_dominant'""", (pid,)).fetchone()[0]
    types: dict[str, int] = {}
    statuses: dict[str, int] = {}
    formats: dict[str, int] = {}
    for row in rows:
        types[row["attachment_type"] or "altro"] = types.get(row["attachment_type"] or "altro", 0) + 1
        statuses[row["extraction_status"] or "unknown"] = statuses.get(row["extraction_status"] or "unknown", 0) + 1
        suffix = Path(row["filename"] or "").suffix.lower() or "senza_estensione"
        formats[suffix] = formats.get(suffix, 0) + 1
    console.print(f"Allegati: {len(rows)} | email attachment_dominant: {dominant}")
    console.print("Tipi: " + ", ".join(f"{k}={v}" for k, v in sorted(types.items())))
    console.print("Estrazione: " + ", ".join(f"{k}={v}" for k, v in sorted(statuses.items())))
    console.print("Formati: " + ", ".join(f"{k}={v}" for k, v in sorted(formats.items(), key=lambda item: item[1], reverse=True)[:15]))


@app.command("explain-email")
def explain_email(email_id: Annotated[int, typer.Option("--id")], db: DbOpt = Path("data/email_cluster.sqlite")) -> None:
    create_schema(db)
    with connect(db) as con:
        row = con.execute("""
            SELECT e.*, c.subject_clean, c.current_message_text, c.quoted_thread_text,
                   c.signature_text, c.disclaimer_text, sc.context_strategy,
                   sc.thread_context_summary, sc.attachment_summary, sc.semantic_summary,
                   sc.semantic_text_for_embedding, sc.message_type, sc.excluded_from_main_clustering,
                   sc.exclusion_reason
            FROM emails e
            LEFT JOIN clean_texts c ON c.id=(SELECT max(c2.id) FROM clean_texts c2 WHERE c2.email_id=e.id)
            LEFT JOIN semantic_contexts sc ON sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=e.id)
            WHERE e.id=?
        """, (email_id,)).fetchone()
        if not row:
            raise typer.BadParameter(f"Email non trovata: {email_id}")
        fields = ("subject", "sender", "sent_at", "body_extracted_text", "subject_clean", "current_message_text", "quoted_thread_text", "thread_context_summary", "attachment_summary", "semantic_summary", "semantic_text_for_embedding", "message_type", "context_strategy", "excluded_from_main_clustering", "exclusion_reason")
        for field in fields:
            console.rule(field)
            console.print(row[field] if row[field] not in (None, "") else "[dim](vuoto)[/dim]")
        attachments = list(con.execute("SELECT filename, attachment_type, extraction_status FROM attachments WHERE email_id=?", (email_id,)))
        console.rule("allegati")
        console.print([dict(item) for item in attachments])
        assignment = con.execute("""SELECT ec.cluster_id, ec.probability, ec.clustering_run_id FROM email_clusters ec WHERE ec.email_id=? ORDER BY ec.id DESC LIMIT 1""", (email_id,)).fetchone()
        console.rule("cluster")
        console.print(dict(assignment) if assignment else "[dim](non assegnata)[/dim]")


@app.command("explain-cluster")
def explain_cluster(cluster_id: Annotated[int, typer.Option("--id")], db: DbOpt = Path("data/email_cluster.sqlite"), run: Annotated[int | None, typer.Option("--run")] = None) -> None:
    create_schema(db)
    with connect(db) as con:
        if run is None:
            latest = con.execute("SELECT max(id) id FROM clustering_runs").fetchone()
            run = int(latest["id"]) if latest and latest["id"] else None
        row = con.execute("SELECT * FROM clusters WHERE clustering_run_id=? AND cluster_id=?", (run, cluster_id)).fetchone()
        if not row:
            raise typer.BadParameter("Cluster non trovato")
        console.print(f"Cluster {cluster_id} | size {row['size']} | label {row['label_manual'] or row['label_auto']}")
        console.print("Keyword: " + ", ".join(json.loads(row["keywords_json"] or "[]")))
        console.print("Domini: " + ", ".join(json.loads(row["recurring_senders_json"] or "[]")))
        console.print("Rappresentanti: " + row["representative_email_ids_json"])
        message_types = con.execute("""
            SELECT sc.message_type, count(*) n FROM email_clusters ec
            JOIN semantic_contexts sc ON sc.email_id=ec.email_id
            WHERE ec.clustering_run_id=? AND ec.cluster_id=?
              AND sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=sc.email_id)
            GROUP BY sc.message_type ORDER BY n DESC
        """, (run, cluster_id)).fetchall()
        attachment_types = con.execute("""
            SELECT a.attachment_type, count(*) n FROM email_clusters ec
            JOIN attachments a ON a.email_id=ec.email_id
            WHERE ec.clustering_run_id=? AND ec.cluster_id=?
            GROUP BY a.attachment_type ORDER BY n DESC LIMIT 10
        """, (run, cluster_id)).fetchall()
        console.print("Tipi messaggio: " + ", ".join(f"{r['message_type']}={r['n']}" for r in message_types))
        console.print("Tipi allegato: " + ", ".join(f"{r['attachment_type'] or 'altro'}={r['n']}" for r in attachment_types))


@app.command("reset-stage")
def reset_stage(
    stage: Annotated[str, typer.Option("--stage")], project: Annotated[str, typer.Option("--project")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
) -> None:
    allowed = {"cleaning", "context", "embedding", "clustering"}
    if stage not in allowed:
        raise typer.BadParameter("stage deve essere cleaning, context, embedding o clustering")
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        if stage == "cleaning":
            con.execute("DELETE FROM semantic_embeddings WHERE email_id IN (SELECT id FROM emails WHERE project_id=?)", (pid,))
            con.execute("DELETE FROM semantic_contexts WHERE email_id IN (SELECT id FROM emails WHERE project_id=?)", (pid,))
            con.execute("DELETE FROM embeddings WHERE email_id IN (SELECT id FROM emails WHERE project_id=?)", (pid,))
            con.execute("DELETE FROM clean_texts WHERE email_id IN (SELECT id FROM emails WHERE project_id=?)", (pid,))
        elif stage == "context":
            con.execute("DELETE FROM semantic_embeddings WHERE email_id IN (SELECT id FROM emails WHERE project_id=?)", (pid,))
            con.execute("DELETE FROM semantic_contexts WHERE email_id IN (SELECT id FROM emails WHERE project_id=?)", (pid,))
        elif stage == "embedding":
            con.execute("DELETE FROM semantic_embeddings WHERE email_id IN (SELECT id FROM emails WHERE project_id=?)", (pid,))
        else:
            run_ids = [r[0] for r in con.execute("SELECT id FROM clustering_runs WHERE project_id=?", (pid,))]
            for run_id in run_ids:
                con.execute("DELETE FROM email_clusters WHERE clustering_run_id=?", (run_id,))
                con.execute("DELETE FROM clusters WHERE clustering_run_id=?", (run_id,))
            con.execute("DELETE FROM clustering_runs WHERE project_id=?", (pid,))
    console.print(f"Stadio azzerato: {stage}")


@app.command("embed")
def embed(
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
    limit: Annotated[int | None, typer.Option("--limit", help="Limite batch.")] = None,
    mode: Annotated[str | None, typer.Option("--mode", help="semantic oppure legacy.")] = None,
) -> None:
    create_schema(db)
    cfg = load_config(config)
    engine = EmbeddingEngine(cfg.embedding.model_name)
    count = 0
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.project_id(project)
        model_id = repo.get_or_create_embedding_model(
            cfg.embedding.model_name,
            None,
            engine.dimension,
            {
                "chunk_size_chars": cfg.embedding.chunk_size_chars,
                "chunk_overlap_chars": cfg.embedding.chunk_overlap_chars,
            },
        )
        selected_mode = mode or cfg.embedding.mode
        if selected_mode not in {"semantic", "legacy"}:
            raise typer.BadParameter("mode deve essere semantic oppure legacy")
        rows = (
            repo.semantic_contexts_without_embedding(project_id, model_id, limit)
            if selected_mode == "semantic"
            else repo.clean_texts_without_embedding(project_id, model_id, limit)
        )
        for row in rows:
            text = row["semantic_text_for_embedding"] if selected_mode == "semantic" else row["semantic_text"]
            vector = engine.embed_email(
                text,
                cfg.embedding.chunk_size_chars,
                cfg.embedding.chunk_overlap_chars,
            )
            if selected_mode == "semantic":
                repo.insert_semantic_embedding(int(row["email_id"]), int(row["id"]), model_id, vector)
            else:
                repo.insert_embedding(
                    int(row["email_id"]), int(row["id"]), model_id, vector,
                    f"chars_{cfg.embedding.chunk_size_chars}_overlap_{cfg.embedding.chunk_overlap_chars}",
                    "weighted_mean",
                )
            count += 1
    console.print(f"Embedding generati ({selected_mode}): {count}")


@app.command("cluster")
def cluster(
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
    profile: Annotated[str | None, typer.Option("--profile", help="Profilo clustering.")] = None,
) -> None:
    create_schema(db)
    cfg = load_config(config)
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.project_id(project)
        profile_name = profile or cfg.clustering.active_profile
        selected = cfg.clustering.profiles.get(profile_name)
        if selected is None:
            raise typer.BadParameter(f"Profilo sconosciuto: {profile_name}")
        run_id = _execute_clustering(con, repo, project_id, cfg, profile_name, selected.umap.model_dump(), selected.hdbscan.model_dump())
    console.print(f"Clustering run completato: {run_id}")


def _execute_clustering(con, repo, project_id, cfg, profile_name, umap_params, hdbscan_params) -> int:
    rows = (
        repo.semantic_embeddings_for_project(project_id)
        if cfg.embedding.mode == "semantic"
        else repo.embeddings_for_project(
            project_id, min_chars=cfg.cleaning.min_semantic_chars,
            message_types=cfg.clustering.allowed_message_types,
        )
    )
    if not rows:
        raise typer.BadParameter("Nessun embedding idoneo disponibile. Esegui prima embed.")
    vectors = np.vstack([blob_to_embedding(row["embedding"]) for row in rows])
    labels, probabilities = run_clustering(vectors, umap_params, hdbscan_params, normalize_embeddings=cfg.clustering.normalize_embeddings)
    model_ids = {int(row["model_id"]) for row in rows}
    if len(model_ids) != 1:
        raise typer.BadParameter("Gli embedding selezionati appartengono a modelli diversi.")
    run_id = repo.create_clustering_run(project_id, model_ids.pop(), umap_params, hdbscan_params, profile_name)
    email_ids = [int(row["email_id"]) for row in rows]
    for email_id, label, probability in zip(email_ids, labels, probabilities, strict=True):
        repo.insert_email_cluster(run_id, email_id, int(label), float(probability))
    summaries = summarize_clusters(
        labels, vectors, [row["semantic_text"] for row in rows], email_ids,
        [row["subject"] or "" for row in rows], [row["sender"] or "" for row in rows],
        probabilities, cfg.clustering.technical_stopwords,
    )
    for summary in summaries:
        repo.insert_cluster_summary(run_id=run_id, **summary)
    total_project = con.execute("SELECT count(*) FROM emails WHERE project_id = ?", (project_id,)).fetchone()[0]
    metrics = calculate_metrics(
        labels, probabilities, vectors, excluded_before=total_project - len(rows),
        small_size=cfg.clustering.min_cluster_size_absolute,
        low_confidence=cfg.clustering.low_confidence_threshold,
    )
    warnings = diagnostic_warnings(
        metrics, max_noise=cfg.clustering.max_noise_ratio_warning,
        max_largest=cfg.clustering.max_largest_cluster_ratio_warning,
        min_clusters=cfg.clustering.min_clusters_warning,
    )
    excluded_types = dict(con.execute("""
        SELECT sc.message_type, count(*) n FROM semantic_contexts sc
        JOIN emails e ON e.id=sc.email_id
        WHERE e.project_id=? AND sc.excluded_from_main_clustering=1
          AND sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=sc.email_id)
        GROUP BY sc.message_type
    """, (project_id,)).fetchall())
    automatic_count = sum(excluded_types.get(kind, 0) for kind in (
        "auto_generated", "newsletter", "personal_or_commercial_notification",
    ))
    if total_project and automatic_count / total_project > 0.20:
        warnings.append(f"Molte email automatiche o commerciali escluse: {automatic_count / total_project:.0%} del progetto.")
    short_count = excluded_types.get("short_reply", 0) + excluded_types.get("low_information", 0)
    if total_project and short_count / total_project > 0.15:
        warnings.append(f"Molti messaggi brevi o poco informativi: {short_count / total_project:.0%} del progetto.")
    repo.save_clustering_metrics(run_id, metrics, warnings)
    repo.complete_clustering_run(run_id)
    return run_id


@app.command("cluster-sweep")
def cluster_sweep(
    project: Annotated[str, typer.Option("--project")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
    limit: Annotated[int | None, typer.Option("--limit")] = None,
) -> None:
    create_schema(db)
    cfg = load_config(config)
    sweep = cfg.clustering.sweep
    maximum = min(limit or sweep.max_combinations, sweep.max_combinations)
    combinations = islice(product(sweep.n_neighbors, sweep.n_components, sweep.min_cluster_size, sweep.min_samples), maximum)
    run_ids: list[int] = []
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.project_id(project)
        for index, (neighbors, components, cluster_size, samples) in enumerate(combinations, 1):
            umap_params = {"n_neighbors": neighbors, "n_components": components, "min_dist": 0.0, "metric": "cosine", "random_state": 42}
            hdbscan_params = {"min_cluster_size": cluster_size, "min_samples": samples, "metric": "euclidean", "cluster_selection_method": "eom"}
            run_ids.append(_execute_clustering(con, repo, project_id, cfg, f"sweep-{index}", umap_params, hdbscan_params))
            console.print(f"Sweep {index}/{maximum}: run {run_ids[-1]}")
    console.print(f"Sweep completato: {len(run_ids)} run")


@app.command("compare-runs")
def compare_runs(project: Annotated[str, typer.Option("--project")], db: DbOpt = Path("data/email_cluster.sqlite")) -> None:
    create_schema(db)
    with connect(db) as con:
        project_id = Repository(con).project_id(project)
        rows = con.execute("""
            SELECT * FROM clustering_runs WHERE project_id = ? AND status = 'completed'
                AND total_emails_considered IS NOT NULL
            ORDER BY total_clusters DESC, largest_cluster_ratio ASC, noise_ratio ASC, id DESC
        """, (project_id,))
        table = Table(title="Confronto clustering run")
        for column in ("run", "profilo", "email", "cluster", "rumore", "dominante", "mediana", "prob. media", "silhouette", "warning", "data"):
            table.add_column(column)
        for row in rows:
            warnings = json.loads(row["warnings_json"] or "[]")
            table.add_row(str(row["id"]), row["profile_name"] or "legacy", str(row["total_emails_considered"] or 0), str(row["total_clusters"] or 0), _pct(row["noise_ratio"]), _pct(row["largest_cluster_ratio"]), str(row["median_cluster_size"] or 0), _score(row["mean_cluster_probability"]), _score(row["silhouette_score"]), str(len(warnings)), row["started_at"])
        console.print(table)


@app.command("clustering-report")
def clustering_report(
    run_id: Annotated[int | None, typer.Option("--run-id")] = None,
    latest: Annotated[bool, typer.Option("--latest")] = False,
    db: DbOpt = Path("data/email_cluster.sqlite"),
) -> None:
    create_schema(db)
    with connect(db) as con:
        if latest or run_id is None:
            latest_row = con.execute("SELECT max(id) id FROM clustering_runs").fetchone()
            run_id = int(latest_row["id"]) if latest_row and latest_row["id"] else None
        if run_id is None:
            raise typer.BadParameter("Nessuna run disponibile")
        run = con.execute("SELECT * FROM clustering_runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            raise typer.BadParameter(f"Run non trovata: {run_id}")
        console.print(f"Run {run_id} | profilo: {run['profile_name'] or 'legacy'} | stato: {run['status']}")
        console.print("UMAP: " + run["umap_parameters_json"])
        console.print("HDBSCAN: " + run["hdbscan_parameters_json"])
        console.print(f"Considerate: {run['total_emails_considered']} | escluse prima: {run['excluded_before_clustering']} | rumore HDBSCAN: {run['total_noise']} ({_pct(run['noise_ratio'])})")
        console.print(f"Cluster: {run['total_clusters']} | cluster dominante: {_pct(run['largest_cluster_ratio'])} | probabilita media: {_score(run['mean_cluster_probability'])}")
        for warning in json.loads(run["warnings_json"] or "[]"):
            console.print(f"[yellow]ATTENZIONE[/yellow] {warning}")
        table = Table(title="Cluster")
        for column in ("id", "size", "label", "prob.", "keyword", "rappresentanti"):
            table.add_column(column)
        for row in con.execute("SELECT * FROM clusters WHERE clustering_run_id = ? ORDER BY size DESC", (run_id,)):
            table.add_row(str(row["cluster_id"]), str(row["size"]), row["label_manual"] or row["label_auto"], _score(row["mean_probability"]), ", ".join(json.loads(row["keywords_json"] or "[]")[:5]), row["representative_email_ids_json"] or "[]")
        console.print(table)
        noise = Table(title="Prime 20 email rumore HDBSCAN")
        noise.add_column("id")
        noise.add_column("oggetto")
        noise.add_column("prob.")
        for row in con.execute("""SELECT e.id, e.subject, ec.probability FROM email_clusters ec JOIN emails e ON e.id=ec.email_id WHERE ec.clustering_run_id=? AND ec.is_noise=1 ORDER BY ec.probability LIMIT 20""", (run_id,)):
            noise.add_row(str(row["id"]), _terminal_safe(row["subject"]), _score(row["probability"]))
        console.print(noise)


def _pct(value) -> str:
    return "n/d" if value is None else f"{value:.1%}"


def _score(value) -> str:
    return "n/d" if value is None else f"{value:.3f}"


@app.command("clusters")
def list_clusters(db: DbOpt = Path("data/email_cluster.sqlite"), run: int | None = None) -> None:
    with connect(db) as con:
        if run is None:
            row = con.execute("SELECT id FROM clustering_runs ORDER BY id DESC LIMIT 1").fetchone()
            run = int(row["id"]) if row else None
        if run is None:
            console.print("Nessun clustering run presente.")
            return
        table = Table(title=f"Cluster run {run}")
        for column in ["cluster", "size", "label", "keywords", "coherence"]:
            table.add_column(column)
        for row in con.execute(
            """
            SELECT cluster_id, size, label_auto, label_manual, keywords_json, coherence_score
            FROM clusters WHERE clustering_run_id = ? ORDER BY cluster_id
            """,
            (run,),
        ):
            table.add_row(
                str(row["cluster_id"]),
                str(row["size"]),
                row["label_manual"] or row["label_auto"] or "",
                row["keywords_json"] or "[]",
                "" if row["coherence_score"] is None else f"{row['coherence_score']:.3f}",
            )
        console.print(table)


@app.command("review-clusters")
def review_clusters(
    output: Annotated[Path, typer.Option("--output")] = Path("data/output/cluster_review.csv"),
    db: DbOpt = Path("data/email_cluster.sqlite"),
    run: Annotated[int | None, typer.Option("--run")] = None,
) -> None:
    with connect(db) as con:
        count = export_cluster_review(con, output, run)
    console.print(f"Revisione cluster esportata: {output} ({count} cluster)")


@app.command("set-label")
def set_label(
    cluster_id: Annotated[int, typer.Argument(help="ID cluster.")],
    label: Annotated[str, typer.Argument(help="Etichetta manuale.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    run: Annotated[int | None, typer.Option("--run")] = None,
) -> None:
    with connect(db) as con:
        if run is None:
            row = con.execute("SELECT id FROM clustering_runs ORDER BY id DESC LIMIT 1").fetchone()
            if not row:
                raise typer.BadParameter("Nessun clustering run presente.")
            run = int(row["id"])
        repo = Repository(con)
        repo.set_cluster_manual_label(run, cluster_id, label)
    console.print(f"Etichetta aggiornata: run {run}, cluster {cluster_id} -> {label}")


@app.command("status")
def status(
    db: DbOpt = Path("data/email_cluster.sqlite"),
    project: Annotated[str | None, typer.Option("--project")] = None,
    input_path: Annotated[Path | None, typer.Option("--input")] = None,
) -> None:
    create_schema(db)
    with connect(db) as con:
        table = Table(title=f"Database {db}")
        table.add_column("tabella")
        table.add_column("record", justify="right")
        for name in [
            "projects",
            "source_files",
            "emails",
            "attachments",
            "clean_texts",
            "embedding_models",
            "embeddings",
            "semantic_contexts",
            "semantic_embeddings",
            "clustering_runs",
            "email_clusters",
            "clusters",
            "errors",
        ]:
            count = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            table.add_row(name, str(count))
        console.print(table)
        project_row = con.execute(
            "SELECT id, name FROM projects WHERE name = ?" if project else "SELECT id, name FROM projects ORDER BY id DESC LIMIT 1",
            (project,) if project else (),
        ).fetchone()
        if project_row:
            pid = int(project_row["id"])
            counts = con.execute("""
                SELECT count(*) total,
                    sum(EXISTS(SELECT 1 FROM clean_texts c WHERE c.email_id=e.id)) cleaned,
                    sum(EXISTS(SELECT 1 FROM semantic_contexts sc WHERE sc.email_id=e.id)) contextualized
                FROM emails e WHERE e.project_id=?
            """, (pid,)).fetchone()
            latest_context = con.execute("""
                SELECT count(*) total, sum(excluded_from_main_clustering) excluded
                FROM semantic_contexts sc WHERE sc.id IN (
                    SELECT max(sc2.id) FROM semantic_contexts sc2 JOIN emails e2 ON e2.id=sc2.email_id
                    WHERE e2.project_id=? GROUP BY sc2.email_id
                )
            """, (pid,)).fetchone()
            console.print(
                f"Progetto: {project_row['name']} | email: {counts['total']} | pulite: {counts['cleaned'] or 0} | "
                f"contesto: {counts['contextualized'] or 0} | escluse: {latest_context['excluded'] or 0} | "
                f"clusterizzabili: {(latest_context['total'] or 0) - (latest_context['excluded'] or 0)}"
            )
        if input_path and input_path.exists():
            candidates = scan_local_folder(input_path)
            known = {str(Path(row["path"]).resolve()) for row in con.execute("SELECT path FROM source_files")}
            console.print(f"Input: {input_path} | file trovati: {len(candidates)} | nuovi: {sum(str(c.path.resolve()) not in known for c in candidates)}")

        latest_run = con.execute(
            "SELECT id, status, completed_at FROM clustering_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest_run:
            clustered = con.execute(
                "SELECT count(*) FROM email_clusters WHERE clustering_run_id = ?",
                (latest_run["id"],),
            ).fetchone()[0]
            noise = con.execute(
                "SELECT count(*) FROM email_clusters WHERE clustering_run_id = ? AND is_noise = 1",
                (latest_run["id"],),
            ).fetchone()[0]
            console.print(
                f"Ultimo clustering run: {latest_run['id']} | "
                f"stato: {latest_run['status']} | email: {clustered} | rumore: {noise}"
            )


@app.command("import-status")
def import_status(project: Annotated[str, typer.Option("--project")], db: DbOpt = Path("data/email_cluster.sqlite")) -> None:
    create_schema(db)
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        table = Table(title="Stato import")
        for column in ("file", "tipo", "dimensione", "trovate", "importate", "errori", "stato"):
            table.add_column(column)
        for row in con.execute("SELECT * FROM source_files WHERE project_id=? ORDER BY path", (pid,)):
            table.add_row(row["path"], row["file_type"], str(row["file_size"] or 0), str(row["emails_found"] or 0), str(row["emails_imported"] or 0), str(row["errors_count"] or 0), row["status"])
        console.print(table)


@app.command("doctor")
def doctor(
    db: DbOpt = Path("data/email_cluster.sqlite"),
    input_path: Annotated[Path, typer.Option("--input")] = Path("data/input"),
    config: ConfigOpt = Path("config/default.yaml"),
) -> None:
    cfg = load_config(config)
    checks = [
        ("Python", platform.python_version(), True),
        ("Database", str(db), db.exists()),
        ("Input", str(input_path), input_path.exists() and input_path.is_dir()),
        ("Schema V3.1", "schema_meta", False),
        ("ML", "sentence_transformers/umap/hdbscan", all(importlib.util.find_spec(x) for x in ("sentence_transformers", "umap", "hdbscan"))),
        ("PDF", "pypdf opzionale", importlib.util.find_spec("pypdf") is not None),
        ("DOCX", "python-docx opzionale", importlib.util.find_spec("docx") is not None),
        ("XLSX", "openpyxl opzionale", importlib.util.find_spec("openpyxl") is not None),
        ("LLM", "disabilitato" if not cfg.local_llm.enabled else str(cfg.local_llm.model_path), not cfg.local_llm.enabled or bool(cfg.local_llm.model_path and Path(cfg.local_llm.model_path).exists())),
    ]
    if db.exists():
        create_schema(db)
        with connect(db) as con:
            row = con.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
            checks[3] = ("Schema V3.1", row["value"] if row else "mancante", bool(row and int(row["value"]) >= 4))
    table = Table(title="Doctor")
    table.add_column("controllo")
    table.add_column("dettaglio")
    table.add_column("esito")
    for name, detail, ok in checks:
        table.add_row(name, detail, "OK" if ok else "ATTENZIONE")
    console.print(table)


@app.command("show-cluster")
def show_cluster(
    cluster_id: Annotated[int, typer.Argument(help="ID cluster.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    limit: Annotated[int, typer.Option("--limit")] = 20,
) -> None:
    with connect(db) as con:
        table = Table(title=f"Email nel cluster {cluster_id}")
        for column in ["id", "subject", "sender", "probability"]:
            table.add_column(column)
        for row in con.execute(
            """
            SELECT e.id, e.subject, e.sender, ec.probability
            FROM email_clusters ec
            JOIN emails e ON e.id = ec.email_id
            WHERE ec.cluster_id = ?
            ORDER BY ec.probability DESC
            LIMIT ?
            """,
            (cluster_id, limit),
        ):
            table.add_row(
                str(row["id"]), row["subject"] or "", row["sender"] or "", f"{row['probability']:.3f}"
            )
        console.print(table)


@app.command("search")
def search(
    db: DbOpt = Path("data/email_cluster.sqlite"),
    query: Annotated[str | None, typer.Option("--query")] = None,
    sender: Annotated[str | None, typer.Option("--sender")] = None,
    subject: Annotated[str | None, typer.Option("--subject")] = None,
    limit: Annotated[int, typer.Option("--limit")] = 20,
) -> None:
    clauses = []
    params: list[object] = []
    if query:
        clauses.append("(c.clean_text LIKE ? OR e.subject LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if sender:
        clauses.append("e.sender LIKE ?")
        params.append(f"%{sender}%")
    if subject:
        clauses.append("e.subject LIKE ?")
        params.append(f"%{subject}%")
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(limit)
    with connect(db) as con:
        table = Table(title="Risultati ricerca")
        for column in ["id", "date", "sender", "subject"]:
            table.add_column(column)
        for row in con.execute(
            f"""
            SELECT e.id, e.sent_at, e.sender, e.subject
            FROM emails e
            LEFT JOIN clean_texts c ON c.id = (
                SELECT c2.id FROM clean_texts c2
                WHERE c2.email_id = e.id
                ORDER BY c2.id DESC
                LIMIT 1
            )
            {where}
            ORDER BY e.sent_at DESC, e.id DESC
            LIMIT ?
            """,
            params,
        ):
            table.add_row(str(row["id"]), row["sent_at"] or "", row["sender"] or "", row["subject"] or "")
        console.print(table)


@app.command("export")
def export_cmd(
    output: Annotated[Path, typer.Option("--output")],
    fmt: Annotated[str, typer.Option("--format")] = "csv",
    db: DbOpt = Path("data/email_cluster.sqlite"),
    cluster: Annotated[int | None, typer.Option("--cluster")] = None,
) -> None:
    with connect(db) as con:
        count = export_emails(con, output, fmt, cluster)
    console.print(f"Esportate {count} email in {output}")


@app.command("report")
def report(
    output: Annotated[Path, typer.Option("--output")] = Path("data/output/cluster_report.md"),
    db: DbOpt = Path("data/email_cluster.sqlite"),
    run: Annotated[int | None, typer.Option("--run")] = None,
) -> None:
    with connect(db) as con:
        count = write_markdown_report(con, output, run)
    console.print(f"Report scritto: {output} ({count} cluster)")


register_review_commands(app)
register_workbench_commands(app)


if __name__ == "__main__":
    app()
