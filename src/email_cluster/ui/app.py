from __future__ import annotations

from pathlib import Path
import sqlite3
import traceback
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from email_cluster.ui.data import UiData
from email_cluster.ui.atlas_data import AtlasUiData, MissingProjectError
from email_cluster.ui.terminology import TERMS, area_name, status_name


def create_app(
    db_path: Path, project: str, config_path: Path = Path("config/default.yaml")
) -> FastAPI:
    app = FastAPI(title="Console classificazione email storiche", docs_url=None, redoc_url=None)
    data = UiData(db_path, project, config_path)
    atlas = AtlasUiData(db_path, project, config_path)
    templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
    templates.env.globals.update(
        term=lambda key: TERMS[key], area_name=area_name, status_name=status_name
    )
    app.state.data = data
    app.state.atlas = atlas

    @app.exception_handler(ValueError)
    async def missing_data_handler(request: Request, exc: ValueError):
        payload = {
            "ok": False,
            "error_type": "missing_project" if "Project not found" in str(exc) else "missing_data",
            "message": (
                f"Il progetto {project} non esiste. Crea un nuovo studio o importa un archivio."
                if "Project not found" in str(exc)
                else str(exc)
            ),
            "technical_detail": str(exc),
        }
        if request.url.path.startswith("/api/"):
            return JSONResponse(payload, status_code=409)
        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'><title>Dati non disponibili</title>"
            f"<h1>Dati non disponibili</h1><p>{payload['message']}</p>"
            "<p><a href='/'>Torna allo Studio Workbench</a></p>",
            status_code=409,
        )

    def page(request: Request, template: str, **context: Any) -> HTMLResponse:
        base = {
            "request": request,
            "project": project,
            "db_path": str(db_path),
            "active": template.split(".")[0],
        }
        return templates.TemplateResponse(request, template, base | context)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        study_dir = Path("outputs/study_pack")
        orange_dir = Path("outputs/orange_pack")
        final_dir = Path("outputs/atlas_finale")
        return page(
            request,
            "atlas_home.html",
            atlas=atlas.status(),
            study_files=sorted(p.name for p in study_dir.glob("*") if p.is_file()),
            orange_files=sorted(p.name for p in orange_dir.glob("*") if p.is_file()),
            final_files=sorted(p.name for p in final_dir.glob("*") if p.is_file()),
        )

    @app.get("/atlas/files/{pack}/{name}")
    def atlas_file(pack: str, name: str):
        roots = {
            "study": Path("outputs/study_pack"),
            "orange": Path("outputs/orange_pack"),
            "final": Path("outputs/atlas_finale"),
        }
        root = roots.get(pack)
        if not root or Path(name).name != name:
            raise HTTPException(404, "File non riconosciuto")
        path = root / name
        if not path.is_file():
            raise HTTPException(404, "File non ancora disponibile")
        return FileResponse(path)

    @app.get("/legacy", response_class=HTMLResponse)
    def legacy_home(request: Request):
        return page(request, "home.html", dashboard=data.dashboard())

    @app.get("/advanced", response_class=HTMLResponse)
    def advanced(request: Request):
        return page(request, "advanced.html")

    @app.get("/help/troubleshooting", response_class=HTMLResponse)
    def troubleshooting():
        text = Path("docs/troubleshooting.md").read_text(encoding="utf-8")
        import html

        return HTMLResponse(
            "<!doctype html><meta charset='utf-8'><title>Troubleshooting</title>"
            f"<pre style='white-space:pre-wrap;max-width:900px;margin:30px auto'>{html.escape(text)}</pre>"
        )

    @app.get("/atlas/conversations", response_class=HTMLResponse)
    def atlas_conversations(request: Request):
        summary = atlas.conversation_summary()
        return page(
            request,
            "atlas_conversations.html",
            summary=summary,
            quality=atlas.conversation_quality(summary),
            groups=atlas.conversation_groups(),
        )

    @app.get("/atlas/conversations/{conversation_id}", response_class=HTMLResponse)
    def atlas_conversation_detail(request: Request, conversation_id: int):
        try:
            return page(
                request,
                "atlas_conversation_detail.html",
                **atlas.conversation_detail(conversation_id),
            )
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/atlas/review", response_class=HTMLResponse)
    def atlas_review(request: Request):
        return page(
            request, "atlas_review.html", candidates=atlas.candidates(), approved=atlas.approved()
        )

    @app.get("/atlas/search", response_class=HTMLResponse)
    def atlas_search_page(request: Request, query: str = ""):
        try:
            results = atlas.search(query) if query else []
            error = ""
        except Exception as exc:  # FTS errors become user guidance.
            results, error = [], str(exc)
        return page(request, "atlas_search.html", query=query, results=results, error=error)

    @app.get("/atlas/reports/{name}", response_class=HTMLResponse)
    def atlas_report(name: str):
        try:
            return HTMLResponse(atlas.report(name))
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/atlas/run/{phase}")
    async def atlas_run_phase(phase: str, request: Request):
        try:
            return atlas.run_phase(phase, await request.json())
        except MissingProjectError as exc:
            raise HTTPException(
                409,
                {
                    "ok": False,
                    "error_type": "missing_project",
                    "message": str(exc),
                    "technical_detail": f"Project not found: {project}",
                    "next_step": "Crea un nuovo studio o importa un archivio.",
                },
            ) from exc
        except (ValueError, RuntimeError, OSError, sqlite3.Error) as exc:
            message = str(exc)
            if isinstance(exc, sqlite3.Error):
                message = (
                    "Errore nella ricostruzione delle conversazioni. Il database contiene gia "
                    "dati collegati; per evitare perdite non sono stati cancellati automaticamente."
                )
            raise HTTPException(
                409,
                {
                    "message": message,
                    "phase": phase,
                    "next_step": (
                        "Aggiorna lo studio senza cancellare revisioni oppure ricostruisci i dati "
                        "derivati creando un backup. Azzera il progetto solo se necessario."
                    ),
                    "technical": traceback.format_exc(),
                },
            ) from exc

    @app.post("/api/atlas/review/{candidate_id}/{action}")
    async def atlas_review_action(candidate_id: int, action: str, request: Request):
        values = await request.json()
        try:
            return atlas.review(candidate_id, action, values.get("name"), values.get("notes", ""))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/wizard", response_class=HTMLResponse)
    def wizard(request: Request, step: int = 1):
        return page(request, "wizard.html", step=max(1, min(step, 6)), dashboard=data.dashboard())

    @app.get("/llm", response_class=HTMLResponse)
    def llm(request: Request):
        return page(request, "llm.html", config=data.config.local_llm, status=data.ollama_status())

    @app.get("/macro", response_class=HTMLResponse)
    def macro(request: Request, category: str | None = None, suspicious: int = 0):
        return page(
            request,
            "macro.html",
            summary=data.macro_summary(),
            emails=data.macro_emails(category, bool(suspicious)),
            category=category,
            suspicious=bool(suspicious),
        )

    @app.get("/contexts", response_class=HTMLResponse)
    def contexts(
        request: Request,
        review_status: str = "",
        macro_category: str = "",
        context_type: str = "",
        entity: str = "",
        suspicious: str = "",
    ):
        return page(request, "contexts.html", contexts=data.contexts(locals()), filters=locals())

    @app.get("/contexts/{context_id}", response_class=HTMLResponse)
    def context_detail(request: Request, context_id: int):
        try:
            detail = data.context_detail(context_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return page(request, "context_detail.html", **detail)

    @app.get("/emails/{email_id}", response_class=HTMLResponse)
    def email_detail(request: Request, email_id: int):
        try:
            detail = data.email_detail(email_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return page(request, "email.html", **detail, contexts=data.contexts({}))

    @app.get("/taxonomy", response_class=HTMLResponse)
    def taxonomy(request: Request):
        return page(request, "taxonomy.html", nodes=data.taxonomy(), active="classification")

    @app.get("/classification", response_class=HTMLResponse)
    def classification(request: Request):
        return page(
            request,
            "classification.html",
            section="structure",
            tree=data.classification_tree(),
            **data.classification(),
        )

    @app.get("/classification/{section}", response_class=HTMLResponse)
    def classification_section(request: Request, section: str):
        allowed = {"structure", "areas", "classes", "sets", "emails", "ai", "advanced"}
        if section not in allowed:
            raise HTTPException(404, "Sezione non trovata")
        return page(
            request,
            "classification.html",
            section=section,
            tree=data.classification_tree(),
            **data.classification(),
        )

    @app.get("/database", response_class=HTMLResponse)
    def database_page(request: Request, input_path: str = ""):
        path = Path(input_path) if input_path else None
        return page(request, "database.html", archive=data.archive_status(path))

    @app.get("/export", response_class=HTMLResponse)
    def export_page(request: Request):
        return page(
            request,
            "export.html",
            quality=data.export_quality(),
            llm_enabled=data.config.local_llm.enabled,
        )

    @app.post("/api/contexts/{context_id}/{action}")
    async def context_action(context_id: int, action: str, request: Request):
        values = await request.json()
        data.update_context(context_id, action, values)
        return {"ok": True}

    @app.post("/api/emails/{email_id}/macro")
    async def email_macro(email_id: int, request: Request):
        values = await request.json()
        data.update_email_macro(email_id, values["macro"])
        return {"ok": True}

    @app.post("/api/emails/{email_id}/{action}")
    async def email_action(email_id: int, action: str, request: Request):
        values = await request.json()
        data.email_action(email_id, action, values)
        return {"ok": True}

    @app.post("/api/llm/config")
    async def llm_config(request: Request):
        values = await request.json()
        data.save_llm(values)
        return {"ok": True}

    @app.post("/api/llm/pull")
    async def llm_pull(request: Request):
        values = await request.json()
        try:
            return data.pull_model(values["model"], bool(values.get("confirmed")))
        except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/llm/test")
    async def llm_test(request: Request):
        values = await request.json()
        try:
            return data.test_llm(values["model"])
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/classification/areas")
    async def area_create(request: Request):
        data.create_area(await request.json())
        return {"ok": True}

    @app.post("/api/classification/areas/{area_id}")
    async def area_update(area_id: int, request: Request):
        data.update_area(area_id, await request.json())
        return {"ok": True}

    @app.post("/api/classification/classes")
    async def class_create(request: Request):
        return {"ok": True, "id": data.create_class(await request.json())}

    @app.post("/api/classification/classes/{class_id}")
    async def class_update(class_id: int, request: Request):
        data.update_class(class_id, await request.json())
        return {"ok": True}

    @app.post("/api/classification/sets")
    async def set_create(request: Request):
        return {"ok": True, "id": data.create_set(await request.json())}

    @app.post("/api/classification/sets/{set_id}")
    async def set_update(set_id: int, request: Request):
        data.update_set_structure(set_id, await request.json())
        return {"ok": True}

    @app.post("/api/classification/labels")
    async def label_create(request: Request):
        data.create_label(await request.json())
        return {"ok": True}

    @app.post("/api/classification/labels/{label_id}")
    async def label_update(label_id: int, request: Request):
        data.update_label(label_id, await request.json())
        return {"ok": True}

    @app.post("/api/classification/rules")
    async def rule_create(request: Request):
        return {"ok": True, "id": data.create_rule(await request.json())}

    @app.post("/api/classification/rules/{rule_id}/preview")
    def rule_preview(rule_id: int):
        return data.preview_rule(rule_id)

    @app.post("/api/classification/rules/{rule_id}/apply")
    def rule_apply(rule_id: int):
        return {"ok": True, "count": data.apply_rule(rule_id)}

    @app.post("/api/classification/ai/{kind}")
    async def classification_ai(kind: str, request: Request):
        values = await request.json()
        try:
            return data.classification_ai_suggestion(kind, values.get("target_id"))
        except (ValueError, RuntimeError, TimeoutError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/archive/scan")
    async def archive_scan(request: Request):
        values = await request.json()
        try:
            return data.scan_archive(Path(values["input_path"]))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/archive/{action}")
    async def archive_action(action: str, request: Request):
        try:
            return data.run_archive_action(action, await request.json())
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/archive/restore/{backup_name}")
    async def archive_restore(backup_name: str, request: Request):
        values = await request.json()
        try:
            data.restore_backup(backup_name, bool(values.get("confirmed")))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"ok": True}

    @app.post("/api/contexts/{context_id}/llm-suggest")
    def llm_suggest(context_id: int):
        try:
            return data.context_llm_suggestion(context_id)
        except RuntimeError as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=409)

    @app.post("/api/contexts/{context_id}/llm-accept")
    async def llm_accept(context_id: int, request: Request):
        values = await request.json()
        data.accept_llm_suggestion(context_id, values["suggestion"], values.get("scope", "all"))
        return {"ok": True}

    @app.post("/api/export")
    async def export_action(request: Request):
        values = await request.json()
        try:
            output = data.export(values.get("format", "html"), bool(values.get("approved_only")))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"ok": True, "path": str(output)}

    return app
