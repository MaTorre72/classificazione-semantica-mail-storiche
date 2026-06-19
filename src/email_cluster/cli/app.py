from __future__ import annotations

from pathlib import Path
from typing import Annotated

import numpy as np
import typer
from rich.console import Console
from rich.table import Table

from email_cluster.cleaning.normalizer import build_clean_text
from email_cluster.clustering.engine import run_clustering, summarize_clusters
from email_cluster.config import load_config
from email_cluster.embeddings.engine import EmbeddingEngine
from email_cluster.export.writers import export_cluster_review, export_emails, write_markdown_report
from email_cluster.ingestion.scanner import file_sha256, scan_local_folder
from email_cluster.parsing.email_parser import parse_eml, parse_mbox
from email_cluster.storage.database import connect, init_db as create_schema
from email_cluster.storage.repository import Repository, blob_to_embedding


app = typer.Typer(help="Pipeline locale per classificazione semantica di archivi email.")
console = Console()


DbOpt = Annotated[Path, typer.Option("--db", help="Percorso database SQLite.")]
ConfigOpt = Annotated[Path | None, typer.Option("--config", help="File YAML di configurazione.")]


def _db_path(db: Path | None, config_path: Path | None) -> Path:
    config = load_config(config_path)
    return db or config.database.path


@app.command("init-db")
def init_db(db: DbOpt = Path("data/email_cluster.sqlite")) -> None:
    create_schema(db)
    console.print(f"Database pronto: {db}")


@app.command("import")
def import_emails(
    source: Annotated[Path, typer.Option("--source", exists=True, help="Cartella o file email.")],
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
) -> None:
    create_schema(db)
    imported = 0
    duplicates = 0
    errors = 0
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.get_or_create_project(project)
        for candidate in scan_local_folder(source):
            source_file_id = repo.upsert_source_file(
                project_id,
                str(candidate.path),
                candidate.file_type,
                file_sha256(candidate.path),
                "importing",
            )
            try:
                parsed_messages = (
                    [parse_eml(candidate.path)]
                    if candidate.file_type == "eml"
                    else parse_mbox(candidate.path)
                )
                for parsed in parsed_messages:
                    try:
                        email_id = repo.insert_email(project_id, source_file_id, parsed)
                        if email_id is None:
                            duplicates += 1
                        else:
                            imported += 1
                    except Exception as exc:  # noqa: BLE001 - isolation per malformed message
                        errors += 1
                        repo.record_error("parsing", exc, project_id, source_file_id)
                repo.upsert_source_file(
                    project_id, str(candidate.path), candidate.file_type, file_sha256(candidate.path), "ok"
                )
            except Exception as exc:  # noqa: BLE001 - isolation per source file
                errors += 1
                repo.record_error("ingestion", exc, project_id, source_file_id)
                repo.upsert_source_file(
                    project_id, str(candidate.path), candidate.file_type, file_sha256(candidate.path), "error"
                )
    console.print(f"Importate: {imported} | Duplicate: {duplicates} | Errori: {errors}")


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
    import_emails(source=source, project=project, db=db)
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


@app.command("clean")
def clean(
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
) -> None:
    cfg = load_config(config)
    count = 0
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.project_id(project)
        for row in repo.emails_needing_cleaning(project_id, cfg.cleaning.version):
            text = row["body_extracted_text"] or row["body_plain"] or ""
            cleaned = build_clean_text(int(row["id"]), text, cfg.cleaning.version)
            repo.insert_clean_text(cleaned)
            count += 1
    console.print(f"Testi puliti creati: {count}")


@app.command("embed")
def embed(
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
    limit: Annotated[int | None, typer.Option("--limit", help="Limite batch.")] = None,
) -> None:
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
        rows = repo.clean_texts_without_embedding(project_id, model_id, limit)
        for row in rows:
            vector = engine.embed_email(
                row["clean_text"],
                cfg.embedding.chunk_size_chars,
                cfg.embedding.chunk_overlap_chars,
            )
            repo.insert_embedding(
                int(row["email_id"]),
                int(row["id"]),
                model_id,
                vector,
                f"chars_{cfg.embedding.chunk_size_chars}_overlap_{cfg.embedding.chunk_overlap_chars}",
                "weighted_mean",
            )
            count += 1
    console.print(f"Embedding generati: {count}")


@app.command("cluster")
def cluster(
    project: Annotated[str, typer.Option("--project", help="Nome progetto.")],
    db: DbOpt = Path("data/email_cluster.sqlite"),
    config: ConfigOpt = Path("config/default.yaml"),
) -> None:
    cfg = load_config(config)
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.project_id(project)
        rows = repo.embeddings_for_project(project_id)
        if not rows:
            raise typer.BadParameter("Nessun embedding disponibile. Esegui prima embed.")
        vectors = np.vstack([blob_to_embedding(row["embedding"]) for row in rows])
        labels, probabilities = run_clustering(
            vectors,
            cfg.umap.model_dump(),
            cfg.hdbscan.model_dump(),
        )
        model_id = int(rows[0]["model_id"])
        run_id = repo.create_clustering_run(
            project_id, model_id, cfg.umap.model_dump(), cfg.hdbscan.model_dump()
        )
        email_ids = [int(row["email_id"]) for row in rows]
        texts = [row["clean_text"] for row in rows]
        for email_id, label, probability in zip(email_ids, labels, probabilities, strict=True):
            repo.insert_email_cluster(run_id, email_id, int(label), float(probability))
        for summary in summarize_clusters(labels, vectors, texts, email_ids):
            repo.insert_cluster_summary(run_id=run_id, **summary)
        repo.complete_clustering_run(run_id)
    console.print(f"Clustering run completato: {run_id}")


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
def status(db: DbOpt = Path("data/email_cluster.sqlite")) -> None:
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
            "clustering_runs",
            "email_clusters",
            "clusters",
            "errors",
        ]:
            count = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
            table.add_row(name, str(count))
        console.print(table)

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


if __name__ == "__main__":
    app()
