from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from email_cluster.atlas.conversations import build_conversations
from email_cluster.atlas.discovery import discover
from email_cluster.atlas.embeddings import embed_documents
from email_cluster.atlas.entities import extract_entities
from email_cluster.atlas.evaluation import evaluate
from email_cluster.atlas.export import export_atlas
from email_cluster.atlas.inventory import inventory
from email_cluster.atlas.parsing import parse_and_clean
from email_cluster.atlas.review import review_action
from email_cluster.atlas.reset import reset_project
from email_cluster.atlas.search import build_index, search as atlas_search
from email_cluster.atlas.semantic_docs import build_semantic_docs
from email_cluster.atlas.study import build_study_dataset, export_orange, import_classification
from email_cluster.atlas.workspace_study import (
    STAGES,
    build_atlas_from_workspace,
    export_orange_workspace,
    run_study,
)
from email_cluster.atlas.update import update_archive
from email_cluster.storage.database import connect
from email_cluster.storage.repository import Repository
from email_cluster.storage.workspace_health import doctor_workspace, repair_workspace

app = typer.Typer(help="Atlante semantico locale fondato sulle Conversazioni storiche.")
console = Console()
Db = Annotated[Path, typer.Option("--db")]
Project = Annotated[str, typer.Option("--project")]


def show(data) -> None:
    console.print_json(json.dumps(data, ensure_ascii=False, default=str))


@app.command("inventory")
def inventory_cmd(
    input_path: Annotated[Path, typer.Option("--input")],
    db: Db,
    project: Project,
    reports: Annotated[Path, typer.Option("--reports")] = Path("reports"),
) -> None:
    """Descrive l'Archivio senza classificarlo o modificare le sorgenti."""
    show(inventory(input_path, db, project, reports))


@app.command("parse")
def parse_cmd(
    db: Db,
    project: Project,
    config: Annotated[Path, typer.Option("--config")] = Path("config/default.yaml"),
) -> None:
    show(parse_and_clean(db, project, config))


@app.command("build-conversations")
def conversations_cmd(
    db: Db, project: Project, account: Annotated[list[str] | None, typer.Option("--account")] = None
) -> None:
    show(build_conversations(db, project, account))


@app.command("index")
def index_cmd(db: Db, project: Project) -> None:
    show(build_index(db, project))


@app.command("search")
def search_cmd(
    db: Db,
    query: Annotated[str, typer.Option("--query")],
    project: Annotated[str | None, typer.Option("--project")] = None,
    limit: int = 20,
) -> None:
    rows = atlas_search(db, query, project, limit)
    table = Table(title=f"Risultati: {query}")
    for name in ("tipo", "id", "oggetto", "evidenza", "score"):
        table.add_column(name)
    for row in rows:
        table.add_row(
            str(row["document_type"]),
            str(row["source_id"]),
            row["subject"] or "",
            row["evidence"] or "",
            f"{row['score']:.3f}",
        )
    console.print(table)


@app.command("extract-entities")
def entities_cmd(db: Db, project: Project, config_dir: Path = Path("config/entities")) -> None:
    show(extract_entities(db, project, config_dir))


@app.command("build-semantic-docs")
def semantic_docs_cmd(db: Db, project: Project) -> None:
    show(build_semantic_docs(db, project))


@app.command("embed")
def embed_cmd(
    db: Db,
    project: Project,
    model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    batch_size: int = 16,
    low_power: bool = False,
) -> None:
    show(embed_documents(db, project, model, batch_size, low_power))


@app.command("discover")
def discover_cmd(
    db: Db, project: Project, min_conversations: int = 3, max_categories: int = 30
) -> None:
    show(discover(db, project, min_conversations, max_categories))


@app.command("review")
def review_cmd(
    db: Db,
    project: Project,
    candidate: Annotated[int | None, typer.Option("--candidate")] = None,
    action: Annotated[str | None, typer.Option("--action")] = None,
    name: str | None = None,
    notes: str = "",
) -> None:
    if candidate is not None and action:
        show(review_action(db, project, candidate, action, name, notes))
        return
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        rows = list(
            con.execute(
                "SELECT id,name,scope,conversation_count,confidence,status FROM atlas_candidate_categories WHERE project_id=? ORDER BY status,conversation_count DESC",
                (pid,),
            )
        )
    table = Table(title="Categorie candidate")
    for col in ("id", "nome", "Ambito", "Conversazioni", "Affidabilità", "Stato"):
        table.add_column(col)
    for row in rows:
        table.add_row(*[str(x) for x in row])
    console.print(table)


@app.command("export-atlas")
def export_cmd(
    db: Db,
    project: Project,
    output: Annotated[Path, typer.Option("--output")],
    public_safe: bool = False,
) -> None:
    show(export_atlas(db, project, output, public_safe))


@app.command("update")
def update_cmd(
    input_path: Annotated[Path, typer.Option("--input")],
    db: Db,
    project: Project,
    config: Path = Path("config/default.yaml"),
) -> None:
    show(update_archive(input_path, db, project, config))


@app.command("evaluate")
def evaluate_cmd(db: Db, project: Project) -> None:
    show(evaluate(db, project))


@app.command("build-study-dataset")
def build_study_dataset_cmd(
    input_path: Annotated[Path, typer.Option("--input")],
    db: Db,
    project: Project,
    output: Annotated[Path, typer.Option("--output")] = Path("outputs/study_pack"),
    config: Path = Path("config/default.yaml"),
    account: Annotated[list[str] | None, typer.Option("--account")] = None,
    rebuild_derived: Annotated[bool, typer.Option("--rebuild-derived")] = False,
) -> None:
    """Prepara il pacchetto completo per lo studio dell'archivio storico."""
    try:
        show(build_study_dataset(input_path, db, project, output, config, account, rebuild_derived))
    except (ValueError, RuntimeError, OSError) as exc:
        console.print(f"Errore: {exc}", style="bold red")
        raise typer.Exit(2) from exc


@app.command("reset-project")
def reset_project_cmd(
    db: Db,
    project: Project,
    confirm: Annotated[bool, typer.Option("--confirm")] = False,
) -> None:
    """Azzera i dati Atlas del progetto dopo backup e conferma esplicita."""
    try:
        show(reset_project(db, project, confirm=confirm).to_dict())
    except ValueError as exc:
        console.print(f"Errore: {exc}", style="bold red")
        raise typer.Exit(2) from exc


@app.command("export-orange")
def export_orange_cmd(
    db: Annotated[Path | None, typer.Option("--db")] = None,
    project: Annotated[str | None, typer.Option("--project")] = None,
    output: Annotated[Path, typer.Option("--output")] = Path("outputs/orange_pack"),
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    """Esporta conversazioni, termini, entita e rete in CSV per Orange."""
    if workspace is not None:
        show(export_orange_workspace(workspace))
        return
    if db is None or project is None:
        raise typer.BadParameter("Usa --workspace oppure specifica --db e --project")
    show(export_orange(db, project, output))


@app.command("study")
def study_cmd(
    input_path: Annotated[Path, typer.Option("--input")],
    workspace: Annotated[Path, typer.Option("--workspace")],
    stages: Annotated[str, typer.Option("--stages")] = "",
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = True,
    rebuild_stage: Annotated[str | None, typer.Option("--rebuild-stage")] = None,
    no_attachments_text: Annotated[bool, typer.Option("--no-attachments-text")] = False,
    with_attachments_text: Annotated[bool, typer.Option("--with-attachments-text")] = False,
    max_attachment_mb: Annotated[int, typer.Option("--max-attachment-mb")] = 20,
    sample_size: Annotated[int | None, typer.Option("--sample-size")] = None,
    limit_messages: Annotated[int | None, typer.Option("--limit-messages")] = None,
    limit_conversations: Annotated[int | None, typer.Option("--limit-conversations")] = None,
    date_from: Annotated[str | None, typer.Option("--date-from", help="Data iniziale ISO YYYY-MM-DD.")] = None,
    date_to: Annotated[str | None, typer.Option("--date-to", help="Data finale ISO YYYY-MM-DD.")] = None,
    source_folder: Annotated[list[str] | None, typer.Option("--source-folder", help="Cartella o file sorgente; opzione ripetibile.")] = None,
    embedding_provider: Annotated[str, typer.Option("--embedding-provider")] = "none",
    embedding_model: Annotated[str, typer.Option("--embedding-model")] = "",
) -> None:
    """Studia uno snapshot Thunderbird/MBOX e produce un workspace autonomo."""
    selected = [item.strip() for item in stages.split(",") if item.strip()] or None
    if stages.strip().lower() == "list":
        show({"stages": STAGES})
        return
    try:
        show(
            run_study(
                input_path,
                workspace,
                stages=selected,
                resume=resume,
                rebuild_stage=rebuild_stage,
                attachments_text=with_attachments_text or not no_attachments_text,
                max_attachment_mb=max_attachment_mb,
                sample_size=sample_size,
                limit_messages=limit_messages,
                limit_conversations=limit_conversations,
                date_from=date_from,
                date_to=date_to,
                source_folders=tuple(source_folder or ()),
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
            )
        )
    except (ValueError, RuntimeError, OSError) as exc:
        console.print(f"Errore: {exc}", style="bold red")
        raise typer.Exit(2) from exc


@app.command("doctor-workspace")
def doctor_workspace_cmd(
    workspace: Annotated[Path, typer.Option("--workspace")],
    project: Annotated[str, typer.Option("--project")] = "studio",
) -> None:
    """Verifica schema, progetto, foreign key e tabelle derivate del workspace."""
    result = doctor_workspace(workspace / "email_atlas.sqlite", project)
    show(result)
    if not result["ok"]:
        raise typer.Exit(2)


@app.command("repair-workspace")
def repair_workspace_cmd(
    workspace: Annotated[Path, typer.Option("--workspace")],
    project: Annotated[str, typer.Option("--project")] = "studio",
) -> None:
    """Ripara solo schema/progetto mancanti, creando sempre un backup del database esistente."""
    try:
        show(repair_workspace(workspace / "email_atlas.sqlite", project))
    except (ValueError, RuntimeError, OSError) as exc:
        console.print(f"Errore: {exc}", style="bold red")
        raise typer.Exit(2) from exc


@app.command("build-atlas")
def build_atlas_cmd(
    workspace: Annotated[Path, typer.Option("--workspace")],
) -> None:
    """Genera l'Atlante finale dalle decisioni del workspace."""
    try:
        show(build_atlas_from_workspace(workspace))
    except (ValueError, OSError, KeyError) as exc:
        console.print(f"Errore: {exc}", style="bold red")
        raise typer.Exit(2) from exc


@app.command("import-classification")
def import_classification_cmd(
    db: Db,
    project: Project,
    file: Annotated[Path, typer.Option("--file")],
    output: Annotated[Path, typer.Option("--output")] = Path("outputs/atlas_finale"),
) -> None:
    """Importa le decisioni dal workspace CSV e genera l'Atlante finale."""
    show(import_classification(db, project, file, output))


@app.command("llm-status")
def llm_status(config: Path = Path("config/default.yaml")) -> None:
    from email_cluster.config import load_config

    cfg = load_config(config)
    show(
        {
            "enabled": cfg.local_llm.enabled,
            "backend": cfg.local_llm.backend,
            "model": cfg.local_llm.selected_model or cfg.local_llm.model,
            "local_only": True,
        }
    )


@app.command("llm-test")
def llm_test(config: Path = Path("config/default.yaml")) -> None:
    from email_cluster.config import load_config
    from email_cluster.llm.client import LocalLlmClient

    cfg = load_config(config)
    parsed, _, elapsed = LocalLlmClient(cfg.local_llm).generate_json(
        'Restituisci solo JSON: {"status":"ok","purpose":"atlante"}'
    )
    show({"ok": True, "elapsed_ms": elapsed, "response": parsed})


@app.command("suggest-category-names")
def suggest_category_names(db: Db, project: Project) -> None:
    from email_cluster.config import load_config
    from email_cluster.llm.client import LocalLlmClient

    with connect(db) as con:
        pid = Repository(con).project_id(project)
        rows = [
            dict(row)
            for row in con.execute(
                "SELECT id,name,scope,lexical_signals_json,description FROM atlas_candidate_categories WHERE project_id=? AND status='candidate' LIMIT 30",
                (pid,),
            )
        ]
    prompt = (
        "Proponi nomi più chiari senza decidere automaticamente. Restituisci JSON con "
        "suggestions: [{candidate_id,name,reason}]. Dati: " + json.dumps(rows, ensure_ascii=False)
    )
    parsed, _, _ = LocalLlmClient(load_config(Path("config/default.yaml")).local_llm).generate_json(
        prompt
    )
    show(parsed)


@app.command("summarize-conversations")
def summarize_conversations(db: Db, project: Project, only_candidates: bool = True) -> None:
    from email_cluster.config import load_config
    from email_cluster.llm.client import LocalLlmClient

    with connect(db) as con:
        pid = Repository(con).project_id(project)
        rows = [
            dict(row)
            for row in con.execute(
                "SELECT id,subject_normalized,analysis_text FROM atlas_conversations WHERE project_id=? ORDER BY message_count DESC LIMIT 20",
                (pid,),
            )
        ]
    client = LocalLlmClient(load_config(Path("config/default.yaml")).local_llm)
    output = []
    for row in rows:
        parsed, _, _ = client.generate_json(
            "Sintetizza senza dati superflui. Restituisci JSON con summary e operational_theme.\n"
            + (row["analysis_text"] or "")[:3000]
        )
        output.append({"conversation_id": row["id"], **parsed})
    show({"summaries": output, "only_candidates": only_candidates})


@app.command("smoke-test")
def smoke_test(keep: bool = False) -> None:
    from email_cluster.atlas.smoke import run_smoke_test

    root = Path(tempfile.mkdtemp(prefix="email-atlas-smoke-"))
    result = run_smoke_test(root)
    show(result)
    if keep:
        console.print(f"File conservati in: {root}")


if __name__ == "__main__":
    app()
