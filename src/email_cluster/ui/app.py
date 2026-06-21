from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from email_cluster.ui.data import UiData


def create_app(
    db_path: Path, project: str, config_path: Path = Path("config/default.yaml")
) -> FastAPI:
    app = FastAPI(title="Console classificazione email storiche", docs_url=None, redoc_url=None)
    data = UiData(db_path, project, config_path)
    templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
    app.state.data = data

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
        return page(request, "home.html", dashboard=data.dashboard())

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
        return page(request, "taxonomy.html", nodes=data.taxonomy())

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
