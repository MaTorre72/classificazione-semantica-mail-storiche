from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from email_cluster.config import AppConfig, load_config
from email_cluster.llm.prompts import operational_context_prompt
from email_cluster.llm.review_assistant import validated_suggestion
from email_cluster.llm.schemas import OperationalContextSuggestion
from email_cluster.operational.builder import build_operational_contexts
from email_cluster.operational.export import export_context_report
from email_cluster.operational.service import (
    exclude_email,
    move_email,
    split_context,
    update_context,
)
from email_cluster.review.repository import ReviewRepository
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, utcnow


class UiData:
    def __init__(self, db_path: Path, project: str, config_path: Path):
        self.db_path = db_path
        self.project = project
        self.config_path = config_path
        init_db(db_path)

    @property
    def config(self) -> AppConfig:
        return load_config(self.config_path)

    def ensure_contexts(self) -> dict[str, int]:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            run_id = ReviewRepository(con).resolve_run(pid, "latest")
            return build_operational_contexts(con, pid, run_id)

    def dashboard(self) -> dict[str, Any]:
        self.ensure_contexts()
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            total = con.execute(
                "SELECT count(*) FROM emails WHERE project_id=?", (pid,)
            ).fetchone()[0]
            source_files = con.execute(
                "SELECT count(*) FROM source_files WHERE project_id=? AND status='ok'", (pid,)
            ).fetchone()[0]
            cleaned = con.execute(
                "SELECT count(DISTINCT c.email_id) FROM clean_texts c JOIN emails e ON e.id=c.email_id WHERE e.project_id=?",
                (pid,),
            ).fetchone()[0]
            contexts = con.execute(
                "SELECT count(*) FROM operational_contexts WHERE project_id=? AND review_status!='archived'",
                (pid,),
            ).fetchone()[0]
            approved = con.execute(
                "SELECT count(*) FROM operational_contexts WHERE project_id=? AND review_status IN ('approved','human_corrected','export_ready')",
                (pid,),
            ).fetchone()[0]
            pending = con.execute(
                "SELECT count(*) FROM operational_contexts WHERE project_id=? AND review_status='pending'",
                (pid,),
            ).fetchone()[0]
            suspicious = con.execute(
                """SELECT count(*) FROM email_context_assignments eca JOIN operational_contexts oc ON oc.id=eca.operational_context_id WHERE oc.project_id=? AND eca.is_suspicious=1 AND eca.review_status NOT IN ('excluded','moved')""",
                (pid,),
            ).fetchone()[0]
            macro_count = con.execute(
                """SELECT count(DISTINCT eca.macro_category) FROM email_context_assignments eca JOIN operational_contexts oc ON oc.id=eca.operational_context_id WHERE oc.project_id=? AND eca.review_status!='moved'""",
                (pid,),
            ).fetchone()[0]
            latest_run = con.execute(
                "SELECT completed_at FROM clustering_runs WHERE project_id=? ORDER BY id DESC LIMIT 1",
                (pid,),
            ).fetchone()
            next_context = con.execute(
                "SELECT id,name,review_priority FROM operational_contexts WHERE project_id=? AND review_status='pending' ORDER BY review_priority DESC LIMIT 1",
                (pid,),
            ).fetchone()
            exported = (Path("data/output/context_report.html")).exists()
        cfg = self.config
        workflow = [
            {"name": "Import", "status": "completed" if source_files else "todo"},
            {"name": "Cleaning", "status": "completed" if cleaned >= total and total else "todo"},
            {"name": "Macro-categorie", "status": "completed" if macro_count else "todo"},
            {"name": "Contesti operativi", "status": "completed" if contexts else "todo"},
            {"name": "Revisione umana", "status": "human" if pending else "completed"},
            {"name": "Esportazione", "status": "completed" if exported else "todo"},
        ]
        if next_context:
            next_action = {
                "title": "Rivedi il prossimo contesto operativo",
                "detail": next_context["name"],
                "href": f"/contexts/{next_context['id']}",
                "button": "Apri contesto",
            }
        elif not cfg.local_llm.enabled:
            next_action = {
                "title": "Esporta oppure configura il LLM locale",
                "detail": "La revisione è completa; il LLM resta opzionale.",
                "href": "/export",
                "button": "Controlla export",
            }
        else:
            next_action = {
                "title": "Esporta la classificazione finale",
                "detail": "I contesti non hanno decisioni pendenti.",
                "href": "/export",
                "button": "Apri export",
            }
        return {
            "project": self.project,
            "database": str(self.db_path),
            "total": total,
            "contexts": contexts,
            "macro_count": macro_count,
            "approved": approved,
            "pending": pending,
            "suspicious": suspicious,
            "llm_enabled": cfg.local_llm.enabled,
            "llm_backend": cfg.local_llm.backend,
            "latest": latest_run["completed_at"] if latest_run else None,
            "workflow": workflow,
            "next_action": next_action,
        }

    def macro_summary(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            rows = con.execute(
                """
                SELECT eca.macro_category,count(DISTINCT eca.email_id) email_count,
                    sum(eca.is_suspicious) suspicious,avg(eca.confidence) confidence,
                    sum(CASE WHEN eca.review_status='approved' THEN 1 ELSE 0 END) approved
                FROM email_context_assignments eca JOIN operational_contexts oc ON oc.id=eca.operational_context_id
                WHERE oc.project_id=? AND eca.review_status!='moved' GROUP BY eca.macro_category ORDER BY email_count DESC
            """,
                (pid,),
            )
            return [
                dict(row)
                | {"action": "Controlla anomalie" if row["suspicious"] else "Nessuna urgenza"}
                for row in rows
            ]

    def macro_emails(
        self, category: str | None = None, suspicious_only: bool = False
    ) -> list[dict[str, Any]]:
        clauses = ["oc.project_id=?", "eca.review_status!='moved'"]
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            params: list[Any] = [pid]
            if category:
                clauses.append("eca.macro_category=?")
                params.append(category)
            if suspicious_only:
                clauses.append(
                    "(eca.is_suspicious=1 OR (eca.macro_category='professionale_operativo' AND (lower(e.sender) LIKE '%no-reply%' OR lower(e.subject) GLOB '*amazon*' OR lower(e.subject) GLOB '*google*' OR lower(e.subject) GLOB '*microsoft*' OR lower(e.subject) GLOB '*telepass*')) OR (eca.macro_category NOT LIKE 'professionale%' AND (lower(e.subject) LIKE '%via%' OR lower(e.subject) LIKE '%aia%' OR lower(e.subject) LIKE '%mud%' OR lower(e.subject) LIKE '%rifiuti%' OR lower(e.subject) LIKE '%autorizzazione%')))"
                )
            sql = f"""SELECT e.id,e.subject,e.sender,e.sent_at,eca.macro_category,eca.reason,eca.confidence,eca.review_status,
                    CASE WHEN eca.is_suspicious=1 THEN 1 ELSE 0 END suspicious
                FROM email_context_assignments eca JOIN operational_contexts oc ON oc.id=eca.operational_context_id
                JOIN emails e ON e.id=eca.email_id WHERE {" AND ".join(clauses)} ORDER BY suspicious DESC,eca.confidence LIMIT 300"""
            return [dict(row) for row in con.execute(sql, params)]

    def contexts(self, filters: dict[str, str]) -> list[dict[str, Any]]:
        clauses = ["oc.project_id=?", "oc.review_status!='archived'"]
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            params: list[Any] = [pid]
            for field in ("review_status", "macro_category", "context_type"):
                if filters.get(field):
                    clauses.append(f"oc.{field}=?")
                    params.append(filters[field])
            if filters.get("entity"):
                clauses.append("oc.client_or_entity LIKE ?")
                params.append(f"%{filters['entity']}%")
            if filters.get("suspicious") == "1":
                clauses.append(
                    "EXISTS(SELECT 1 FROM email_context_assignments x WHERE x.operational_context_id=oc.id AND x.is_suspicious=1 AND x.review_status!='moved')"
                )
            sql = f"""SELECT oc.*,count(CASE WHEN eca.review_status NOT IN ('moved','excluded') THEN 1 END) email_count,
                    sum(CASE WHEN eca.is_suspicious=1 AND eca.review_status!='moved' THEN 1 ELSE 0 END) suspicious_count,
                    min(e.sent_at) first_date,max(e.sent_at) last_date
                FROM operational_contexts oc LEFT JOIN email_context_assignments eca ON eca.operational_context_id=oc.id
                LEFT JOIN emails e ON e.id=eca.email_id WHERE {" AND ".join(clauses)} GROUP BY oc.id
                HAVING email_count>0 ORDER BY oc.review_status='pending' DESC,oc.review_priority DESC"""
            return [dict(row) for row in con.execute(sql, params)]

    def context_detail(self, context_id: int) -> dict[str, Any]:
        with connect(self.db_path) as con:
            row = con.execute(
                """SELECT oc.*,count(CASE WHEN eca.review_status NOT IN ('moved','excluded') THEN 1 END) email_count,min(e.sent_at) first_date,max(e.sent_at) last_date FROM operational_contexts oc LEFT JOIN email_context_assignments eca ON eca.operational_context_id=oc.id LEFT JOIN emails e ON e.id=eca.email_id WHERE oc.id=? GROUP BY oc.id""",
                (context_id,),
            ).fetchone()
            if not row:
                raise ValueError("Contesto non trovato")
            context = dict(row)
            emails = [
                dict(row)
                for row in con.execute(
                    """SELECT e.id,e.subject,e.sender,e.sent_at,eca.confidence,eca.reason,eca.is_suspicious,eca.review_status FROM email_context_assignments eca JOIN emails e ON e.id=eca.email_id WHERE eca.operational_context_id=? AND eca.review_status!='moved' ORDER BY eca.is_suspicious DESC,eca.confidence""",
                    (context_id,),
                )
            ]
            senders = [
                dict(row)
                for row in con.execute(
                    """SELECT e.sender,count(*) n FROM email_context_assignments eca JOIN emails e ON e.id=eca.email_id WHERE eca.operational_context_id=? AND eca.review_status!='moved' GROUP BY e.sender ORDER BY n DESC LIMIT 8""",
                    (context_id,),
                )
            ]
            attachments = [
                dict(row)
                for row in con.execute(
                    """SELECT a.attachment_type,count(*) n FROM email_context_assignments eca JOIN attachments a ON a.email_id=eca.email_id WHERE eca.operational_context_id=? AND eca.review_status!='moved' GROUP BY a.attachment_type ORDER BY n DESC LIMIT 8""",
                    (context_id,),
                )
            ]
        context["decision"] = (
            "Controlla le email sospette prima di approvare"
            if any(row["is_suspicious"] for row in emails)
            else "Il sistema propone di approvare questo contesto"
        )
        return {
            "context": context,
            "emails": emails,
            "senders": senders,
            "attachments": attachments,
        }

    def email_detail(self, email_id: int) -> dict[str, Any]:
        with connect(self.db_path) as con:
            row = con.execute(
                """SELECT e.*,eca.macro_category,eca.confidence assignment_confidence,eca.reason,eca.review_status,
                    oc.id context_id,oc.name context_name,c.current_message_text,sc.thread_context_summary,
                    sc.attachment_summary,sc.semantic_text_for_embedding
                FROM emails e LEFT JOIN email_context_assignments eca ON eca.id=(SELECT max(x.id) FROM email_context_assignments x WHERE x.email_id=e.id AND x.review_status!='moved')
                LEFT JOIN operational_contexts oc ON oc.id=eca.operational_context_id
                LEFT JOIN clean_texts c ON c.id=(SELECT max(c2.id) FROM clean_texts c2 WHERE c2.email_id=e.id)
                LEFT JOIN semantic_contexts sc ON sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=e.id)
                WHERE e.id=?""",
                (email_id,),
            ).fetchone()
            attachments = [
                dict(item)
                for item in con.execute(
                    "SELECT filename,attachment_type,extraction_status,text_excerpt FROM attachments WHERE email_id=?",
                    (email_id,),
                )
            ]
        if not row:
            raise ValueError("Email non trovata")
        return {"email": dict(row), "attachments": attachments}

    def taxonomy(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            return [
                dict(row)
                for row in con.execute(
                    """SELECT macro_category,client_or_entity,technical_domain,context_type,count(*) contexts,sum((SELECT count(*) FROM email_context_assignments eca WHERE eca.operational_context_id=oc.id AND eca.review_status!='moved')) emails FROM operational_contexts oc WHERE project_id=? AND review_status!='archived' GROUP BY macro_category,client_or_entity,technical_domain,context_type ORDER BY macro_category,client_or_entity""",
                    (pid,),
                )
            ]

    def export_quality(self) -> dict[str, int]:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            row = con.execute(
                """SELECT count(*) contexts,sum(review_status IN ('approved','human_corrected','export_ready')) approved,sum(review_status='pending') pending FROM operational_contexts WHERE project_id=? AND review_status!='archived'""",
                (pid,),
            ).fetchone()
            suspicious = con.execute(
                """SELECT count(*) FROM email_context_assignments eca JOIN operational_contexts oc ON oc.id=eca.operational_context_id WHERE oc.project_id=? AND eca.is_suspicious=1 AND eca.review_status!='moved'""",
                (pid,),
            ).fetchone()[0]
            no_context = con.execute(
                """SELECT count(*) FROM emails e WHERE e.project_id=? AND NOT EXISTS(SELECT 1 FROM email_context_assignments x WHERE x.email_id=e.id AND x.review_status!='moved')""",
                (pid,),
            ).fetchone()[0]
        return {
            "contexts": row["contexts"] or 0,
            "approved": row["approved"] or 0,
            "pending": row["pending"] or 0,
            "suspicious": suspicious,
            "no_context": no_context,
        }

    def ollama_status(self) -> dict[str, Any]:
        cfg = self.config.local_llm
        result = {"reachable": False, "models": [], "error": None, "endpoint": cfg.ollama_url}
        if not cfg.ollama_url.startswith(("http://localhost", "http://127.0.0.1")):
            result["error"] = "Per sicurezza Ollama deve usare localhost"
            return result
        try:
            with urllib.request.urlopen(
                cfg.ollama_url.rstrip("/") + "/api/tags", timeout=2
            ) as response:
                data = json.loads(response.read().decode())
                result["reachable"] = True
                result["models"] = data.get("models", [])
        except (OSError, urllib.error.URLError, ValueError) as exc:
            result["error"] = str(exc)
        return result

    def save_llm(self, values: dict[str, Any]) -> None:
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        section = data.setdefault("local_llm", {})
        for key in ("enabled", "backend", "ollama_url", "model", "model_path", "mode"):
            if key in values:
                section[key] = values[key]
        self.config_path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

    def update_context(self, context_id: int, action: str, values: dict[str, Any]) -> None:
        with connect(self.db_path) as con:
            if action == "approve":
                update_context(
                    con,
                    context_id,
                    "approve",
                    review_status="approved",
                    source="human",
                    suggested_user_action="completato",
                )
            elif action == "rename":
                update_context(
                    con,
                    context_id,
                    "rename",
                    name=values["name"],
                    review_status="human_corrected",
                    source="human",
                )
            elif action == "nonprofessional":
                update_context(
                    con,
                    context_id,
                    "mark_nonprofessional",
                    macro_category="personale",
                    context_type="personale",
                    review_status="non_professional",
                    source="human",
                )
            elif action == "split":
                split_context(con, context_id)

    def update_email_macro(self, email_id: int, macro: str) -> None:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            context = con.execute(
                "SELECT id FROM operational_contexts WHERE project_id=? AND macro_category=? AND source='human' ORDER BY id LIMIT 1",
                (pid, macro),
            ).fetchone()
            if not context:
                cur = con.execute(
                    """INSERT INTO operational_contexts(project_id,name,description,context_type,macro_category,why_grouped,suggested_user_action,source,confidence,review_status,review_priority,created_at,updated_at) VALUES(?,?,?,?,?,?,'completato','human',1.0,'approved',0,?,?)""",
                    (
                        pid,
                        macro.replace("_", " ").title(),
                        "Correzione macro categoria umana",
                        macro,
                        macro,
                        "Assegnazione confermata manualmente",
                        utcnow(),
                        utcnow(),
                    ),
                )
                context_id = int(cur.lastrowid)
            else:
                context_id = int(context["id"])
            move_email(con, email_id, context_id)

    def email_action(self, email_id: int, action: str, values: dict[str, Any]) -> None:
        with connect(self.db_path) as con:
            if action == "move":
                move_email(con, email_id, int(values["target_context_id"]))
            elif action == "exclude":
                row = con.execute(
                    "SELECT operational_context_id FROM email_context_assignments WHERE email_id=? AND review_status!='moved' ORDER BY id DESC LIMIT 1",
                    (email_id,),
                ).fetchone()
                if row:
                    exclude_email(
                        con,
                        int(row["operational_context_id"]),
                        email_id,
                        values.get("reason", "Esclusa dall'utente"),
                    )

    def export(self, fmt: str, approved_only: bool = False) -> Path:
        if fmt not in {"html", "csv"}:
            raise ValueError("Formato di esportazione non supportato")
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            suffix = "html" if fmt == "html" else "csv"
            output = Path("data/output") / f"context_export.{suffix}"
            export_context_report(con, pid, output, fmt)
        return output

    def context_llm_suggestion(self, context_id: int) -> dict[str, Any]:
        detail = self.context_detail(context_id)
        cfg = self.config.local_llm
        cards = [
            {
                "id": row["id"],
                "subject": row["subject"],
                "sender": row["sender"],
                "suspicious": bool(row["is_suspicious"]),
            }
            for row in detail["emails"][:20]
        ]
        prompt = operational_context_prompt(
            json.dumps({"context": detail["context"], "email_cards": cards}, ensure_ascii=False)[
                : cfg.max_input_chars
            ]
        )
        with connect(self.db_path) as con:
            suggestion = validated_suggestion(con, prompt, OperationalContextSuggestion, cfg)
        return {
            "input": prompt,
            "model": cfg.model or cfg.model_path,
            "suggestion": suggestion.model_dump(),
        }

    def accept_llm_suggestion(
        self, context_id: int, suggestion: dict[str, Any], scope: str
    ) -> None:
        changes: dict[str, Any] = {"source": "llm", "review_status": "llm_suggested"}
        if scope in {"all", "name"}:
            changes["name"] = suggestion.get("context_name") or suggestion.get("suggested_label")
        if scope in {"all", "summary"}:
            changes.update(
                {"suggested_user_action": suggestion.get("suggested_user_action", "approva")}
            )
        with connect(self.db_path) as con:
            if scope in {"all", "summary"}:
                con.execute(
                    "UPDATE operational_contexts SET description=?,why_grouped=?,technical_domain=?,client_or_entity=?,practice_or_topic=?,llm_used=1 WHERE id=?",
                    (
                        suggestion.get("summary", ""),
                        suggestion.get("why_grouped", ""),
                        suggestion.get("technical_domain", ""),
                        suggestion.get("client_or_entity", ""),
                        suggestion.get("practice_or_topic", ""),
                        context_id,
                    ),
                )
            update_context(con, context_id, "accept_llm", **changes)
            if scope in {"all", "exclusions"}:
                for email_id in suggestion.get("emails_that_do_not_fit", []):
                    exclude_email(
                        con,
                        context_id,
                        int(email_id),
                        "Esclusione proposta dal LLM e accettata dall'utente",
                    )
