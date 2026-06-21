from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Any

import yaml

from email_cluster.config import AppConfig, load_config
from email_cluster.ingestion.scanner import scan_local_folder
from email_cluster.llm.prompts import operational_context_prompt
from email_cluster.llm.review_assistant import validated_suggestion
from email_cluster.llm.schemas import (
    AreasSuggestion,
    ClassesSuggestion,
    OperationalContextSuggestion,
)
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
from email_cluster.ui.terminology import AREA_NAMES, area_name


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

    def ensure_areas(self) -> None:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            for index, (internal, display) in enumerate(AREA_NAMES.items()):
                con.execute(
                    """INSERT OR IGNORE INTO classification_areas
                    (project_id,internal_name,display_name,color,active,include_in_report,is_operational,
                     review_priority,created_at,updated_at) VALUES(?,?,?,'#52616d',1,1,?,?,?,?)""",
                    (
                        pid,
                        internal,
                        display,
                        int(internal.startswith("professionale")),
                        100 - index,
                        utcnow(),
                        utcnow(),
                    ),
                )
            professional = con.execute(
                "SELECT id FROM classification_areas WHERE project_id=? AND internal_name='professionale_operativo'",
                (pid,),
            ).fetchone()
            if professional:
                defaults = [
                    "Gestione rifiuti",
                    "Autorizzazioni ambientali",
                    "Analisi e laboratorio",
                    "Emissioni in atmosfera",
                    "VIA / AIA / Seveso",
                    "Documentazione tecnica",
                ]
                for index, name in enumerate(defaults):
                    con.execute(
                        """INSERT OR IGNORE INTO classification_classes(project_id,area_id,name,description,active,review_priority,created_at,updated_at)
                        VALUES(?,?,?,'Classe iniziale modificabile',1,?,?,?)""",
                        (pid, professional[0], name, 100 - index, utcnow(), utcnow()),
                    )

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
            {"name": "Aree", "status": "completed" if macro_count else "todo"},
            {"name": "Insiemi", "status": "completed" if contexts else "todo"},
            {"name": "Controllo umano", "status": "human" if pending else "completed"},
            {"name": "Esportazione", "status": "completed" if exported else "todo"},
        ]
        if next_context:
            next_action = {
                "title": "Controlla il prossimo Insieme",
                "detail": next_context["name"],
                "href": f"/contexts/{next_context['id']}",
                "button": "Apri Insieme",
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
                "detail": "Gli Insiemi non hanno decisioni pendenti.",
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
            "llm_model": cfg.local_llm.selected_model or cfg.local_llm.model,
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

    def classification(self) -> dict[str, Any]:
        self.ensure_areas()
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            areas = [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM classification_areas WHERE project_id=? ORDER BY review_priority DESC,display_name",
                    (pid,),
                )
            ]
            labels = [
                dict(row)
                for row in con.execute(
                    """SELECT tl.*,count(el.id) usage_count FROM taxonomy_labels tl
                LEFT JOIN email_labels el ON el.label_id=tl.id WHERE tl.project_id=? GROUP BY tl.id ORDER BY tl.active DESC,tl.label""",
                    (pid,),
                )
            ]
            rules = [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM classification_rules WHERE project_id=? ORDER BY priority DESC,id",
                    (pid,),
                )
            ]
            classes = [
                dict(row)
                for row in con.execute(
                    """SELECT cc.*,ca.display_name area_name,
                count(DISTINCT oc.id) set_count,count(DISTINCT eca.email_id) email_count
                FROM classification_classes cc JOIN classification_areas ca ON ca.id=cc.area_id
                LEFT JOIN operational_contexts oc ON oc.classification_class_id=cc.id AND oc.review_status!='archived'
                LEFT JOIN email_context_assignments eca ON eca.operational_context_id=oc.id AND eca.review_status NOT IN ('moved','excluded')
                WHERE cc.project_id=? GROUP BY cc.id ORDER BY ca.review_priority DESC,cc.review_priority DESC""",
                    (pid,),
                )
            ]
        return {
            "areas": areas,
            "classes": classes,
            "labels": labels,
            "rules": rules,
            "sets": self.contexts({}),
        }

    def classification_tree(self) -> list[dict[str, Any]]:
        model = self.classification()
        classes_by_area: dict[int, list[dict[str, Any]]] = {}
        for item in model["classes"]:
            item["sets"] = []
            classes_by_area.setdefault(int(item["area_id"]), []).append(item)
        unassigned: dict[str, dict[str, Any]] = {}
        with connect(self.db_path) as con:
            for item in model["sets"]:
                item["emails"] = [
                    dict(row)
                    for row in con.execute(
                        """SELECT e.id,e.subject,e.sender FROM email_context_assignments eca
                    JOIN emails e ON e.id=eca.email_id WHERE eca.operational_context_id=? AND eca.review_status NOT IN ('moved','excluded') ORDER BY e.sent_at DESC LIMIT 8""",
                        (item["id"],),
                    )
                ]
                target = next(
                    (x for x in model["classes"] if x["id"] == item.get("classification_class_id")),
                    None,
                )
                if target:
                    target["sets"].append(item)
                else:
                    key = item["macro_category"]
                    holder = unassigned.setdefault(
                        key,
                        {
                            "id": f"unassigned-{key}",
                            "name": "Da assegnare a una Classe",
                            "sets": [],
                        },
                    )
                    holder["sets"].append(item)
        tree = []
        for area in model["areas"]:
            area["classes"] = classes_by_area.get(int(area["id"]), [])
            if area["internal_name"] in unassigned:
                area["classes"].append(unassigned[area["internal_name"]])
            tree.append(area)
        return tree

    def create_class(self, values: dict[str, Any]) -> int:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            cur = con.execute(
                """INSERT INTO classification_classes(project_id,area_id,name,description,active,
                review_priority,created_at,updated_at) VALUES(?,?,?,?,1,?,?,?)""",
                (
                    pid,
                    int(values["area_id"]),
                    values["name"].strip(),
                    values.get("description", ""),
                    int(values.get("review_priority", 100)),
                    utcnow(),
                    utcnow(),
                ),
            )
            return int(cur.lastrowid)

    def update_class(self, class_id: int, values: dict[str, Any]) -> None:
        allowed = {"name", "description", "active", "area_id", "review_priority"}
        changes = {key: values[key] for key in allowed if key in values}
        if changes:
            with connect(self.db_path) as con:
                columns = ",".join(f"{key}=?" for key in changes)
                con.execute(
                    f"UPDATE classification_classes SET {columns},updated_at=? WHERE id=?",
                    (*changes.values(), utcnow(), class_id),
                )

    def create_set(self, values: dict[str, Any]) -> int:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            area = con.execute(
                "SELECT internal_name FROM classification_areas WHERE id=?",
                (int(values["area_id"]),),
            ).fetchone()
            cur = con.execute(
                """INSERT INTO operational_contexts(project_id,name,description,context_type,macro_category,
                classification_class_id,client_or_entity,technical_domain,why_grouped,suggested_user_action,source,
                confidence,review_status,review_priority,created_at,updated_at) VALUES(?,?,?,'manuale',?,?,?,?,
                'Creato manualmente','Aggiungi email','human',1,'pending',100,?,?)""",
                (
                    pid,
                    values["name"].strip(),
                    values.get("description", ""),
                    area[0],
                    values.get("class_id"),
                    values.get("client_or_entity", ""),
                    values.get("topic", ""),
                    utcnow(),
                    utcnow(),
                ),
            )
            return int(cur.lastrowid)

    def update_set_structure(self, set_id: int, values: dict[str, Any]) -> None:
        allowed = {
            "name",
            "classification_class_id",
            "client_or_entity",
            "technical_domain",
            "review_status",
            "human_notes",
        }
        changes = {key: values[key] for key in allowed if key in values}
        with connect(self.db_path) as con:
            if "area_id" in values:
                area = con.execute(
                    "SELECT internal_name FROM classification_areas WHERE id=?",
                    (int(values["area_id"]),),
                ).fetchone()
                changes["macro_category"] = area[0]
            if changes:
                columns = ",".join(f"{key}=?" for key in changes)
                con.execute(
                    f"UPDATE operational_contexts SET {columns},source='human',updated_at=? WHERE id=?",
                    (*changes.values(), utcnow(), set_id),
                )

    def archive_status(self, input_path: Path | None = None) -> dict[str, Any]:
        path = input_path or self.config.input.path
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            total = con.execute(
                "SELECT count(*) FROM emails WHERE project_id=?", (pid,)
            ).fetchone()[0]
            sources = con.execute(
                "SELECT count(*) FROM source_files WHERE project_id=?", (pid,)
            ).fetchone()[0]
            duplicates = con.execute(
                "SELECT coalesce(sum(emails_found-emails_imported),0) FROM source_files WHERE project_id=?",
                (pid,),
            ).fetchone()[0]
            errors = con.execute(
                "SELECT count(*) FROM errors WHERE project_id=?", (pid,)
            ).fetchone()[0]
            latest = con.execute(
                "SELECT max(imported_at) FROM source_files WHERE project_id=?", (pid,)
            ).fetchone()[0]
        candidates = scan_local_folder(path) if path.exists() else []
        backups = sorted(self.db_path.parent.glob(self.db_path.name + ".backup-*"), reverse=True)
        return {
            "database": str(self.db_path),
            "input_path": str(path),
            "total": total,
            "sources": sources,
            "duplicates": duplicates,
            "errors": errors,
            "latest": latest,
            "files_found": len(candidates),
            "backups": [
                {"name": item.name, "path": str(item), "size": item.stat().st_size}
                for item in backups[:20]
            ],
        }

    def scan_archive(self, input_path: Path) -> dict[str, Any]:
        if not input_path.exists() or not input_path.is_dir():
            raise ValueError("La cartella indicata non esiste o non è accessibile")
        candidates = scan_local_folder(input_path)
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            known = {
                row["path"]: row["file_hash"]
                for row in con.execute(
                    "SELECT path,file_hash FROM source_files WHERE project_id=?", (pid,)
                )
            }
        new = sum(str(item.path.resolve()) not in known for item in candidates)
        return {"files": len(candidates), "new_files": new, "path": str(input_path)}

    def create_backup(self, reason: str = "manuale") -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = self.db_path.with_suffix(self.db_path.suffix + f".backup-{stamp}")
        shutil.copy2(self.db_path, output)
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            con.execute(
                "INSERT INTO archive_operations(project_id,operation,status,details_json,backup_path,created_at,completed_at) VALUES(?,'backup','completed',?,?,?,?)",
                (
                    pid,
                    json.dumps({"reason": reason}, ensure_ascii=False),
                    str(output),
                    utcnow(),
                    utcnow(),
                ),
            )
        return output

    def restore_backup(self, backup_name: str, confirmed: bool) -> None:
        if not confirmed:
            raise ValueError("Il ripristino richiede conferma esplicita")
        source = self.db_path.parent / Path(backup_name).name
        if not source.exists() or not source.name.startswith(self.db_path.name + ".backup-"):
            raise ValueError("Backup non valido")
        self.create_backup("prima del ripristino")
        shutil.copy2(source, self.db_path)

    def run_archive_action(self, action: str, values: dict[str, Any]) -> dict[str, Any]:
        from email_cluster.cli.app import clean, import_emails, prepare_context

        path = Path(values.get("input_path") or self.config.input.path)
        risky = action in {"reimport", "regenerate_classification", "delete_processing"}
        if risky and not values.get("confirmed"):
            raise ValueError("Questa operazione richiede conferma esplicita")
        backup = self.create_backup(f"prima di {action}") if risky else None
        if action == "import_new":
            import_emails(
                source=path, project=self.project, db=self.db_path, config=self.config_path
            )
        elif action == "clean":
            clean(project=self.project, db=self.db_path, config=self.config_path)
            prepare_context(project=self.project, db=self.db_path, config=self.config_path)
        elif action == "regenerate_classification":
            self.ensure_contexts()
        elif action == "backup":
            backup = self.create_backup("richiesto dall'utente")
        else:
            raise ValueError("Operazione non supportata dalla console")
        return {
            "ok": True,
            "backup": str(backup) if backup else None,
            "status": self.archive_status(path),
        }

    def create_area(self, values: dict[str, Any]) -> None:
        display = values["display_name"].strip()
        internal = re.sub(r"[^a-z0-9]+", "_", display.lower()).strip("_") or "area_personalizzata"
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            con.execute(
                """INSERT INTO classification_areas(project_id,internal_name,display_name,color,active,
                include_in_report,is_operational,review_priority,created_at,updated_at) VALUES(?,?,?,?,1,?,?,?,?,?)""",
                (
                    pid,
                    internal,
                    display,
                    values.get("color", "#52616d"),
                    int(values.get("include_in_report", True)),
                    int(values.get("is_operational", True)),
                    int(values.get("review_priority", 100)),
                    utcnow(),
                    utcnow(),
                ),
            )

    def update_area(self, area_id: int, values: dict[str, Any]) -> None:
        allowed = {
            "display_name",
            "color",
            "active",
            "include_in_report",
            "is_operational",
            "review_priority",
        }
        changes = {key: values[key] for key in allowed if key in values}
        if changes:
            columns = ",".join(f"{key}=?" for key in changes)
            with connect(self.db_path) as con:
                con.execute(
                    f"UPDATE classification_areas SET {columns},updated_at=? WHERE id=?",
                    (*changes.values(), utcnow(), area_id),
                )

    def create_label(self, values: dict[str, Any]) -> None:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            ReviewRepository(con).add_taxonomy_label(
                pid, values["label"].strip(), "user", values.get("description", "")
            )

    def update_label(self, label_id: int, values: dict[str, Any]) -> None:
        with connect(self.db_path) as con:
            if "label" in values:
                con.execute(
                    "UPDATE taxonomy_labels SET label=?,updated_at=? WHERE id=?",
                    (values["label"].strip(), utcnow(), label_id),
                )
            if "active" in values:
                con.execute(
                    "UPDATE taxonomy_labels SET active=?,updated_at=? WHERE id=?",
                    (int(values["active"]), utcnow(), label_id),
                )

    def create_rule(self, values: dict[str, Any]) -> int:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            cur = con.execute(
                """INSERT INTO classification_rules(project_id,name,condition_type,pattern,action_type,
                action_value,active,priority,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,?)""",
                (
                    pid,
                    values["name"],
                    values["condition_type"],
                    values["pattern"],
                    values["action_type"],
                    values["action_value"],
                    int(values.get("priority", 100)),
                    utcnow(),
                    utcnow(),
                ),
            )
            return int(cur.lastrowid)

    def _rule_email_ids(self, con, rule: dict[str, Any]) -> list[int]:
        fields = {
            "sender_contains": "lower(e.sender)",
            "sender_domain": "lower(e.sender)",
            "subject_contains": "lower(e.subject)",
            "text_contains": "lower(coalesce(c.clean_text,''))",
            "attachment_name_contains": "lower(coalesce(a.filename,''))",
            "attachment_type": "lower(coalesce(a.attachment_type,''))",
        }
        field = fields.get(rule["condition_type"])
        if not field:
            return []
        joins = "LEFT JOIN clean_texts c ON c.id=(SELECT max(c2.id) FROM clean_texts c2 WHERE c2.email_id=e.id) LEFT JOIN attachments a ON a.email_id=e.id"
        rows = con.execute(
            f"SELECT DISTINCT e.id FROM emails e {joins} WHERE e.project_id=? AND {field} LIKE ?",
            (rule["project_id"], f"%{rule['pattern'].lower()}%"),
        )
        return [int(row[0]) for row in rows]

    def preview_rule(self, rule_id: int) -> dict[str, Any]:
        with connect(self.db_path) as con:
            row = con.execute(
                "SELECT * FROM classification_rules WHERE id=?", (rule_id,)
            ).fetchone()
            if not row:
                raise ValueError("Regola non trovata")
            ids = self._rule_email_ids(con, dict(row))
        return {"count": len(ids), "email_ids": ids[:20]}

    def apply_rule(self, rule_id: int) -> int:
        with connect(self.db_path) as con:
            row = con.execute(
                "SELECT * FROM classification_rules WHERE id=?", (rule_id,)
            ).fetchone()
            if not row:
                raise ValueError("Regola non trovata")
            rule = dict(row)
            ids = self._rule_email_ids(con, rule)
            if rule["action_type"] == "area":
                for email_id in ids:
                    self._move_email_to_area(con, email_id, rule["action_value"])
            elif rule["action_type"] == "label":
                label_id = ReviewRepository(con).add_taxonomy_label(
                    rule["project_id"], rule["action_value"], "rule"
                )
                con.executemany(
                    "INSERT OR IGNORE INTO email_labels(email_id,label_id,source,created_at) VALUES(?,?,'rule',?)",
                    [(email_id, label_id, utcnow()) for email_id in ids],
                )
            elif rule["action_type"] == "client_or_entity":
                con.executemany(
                    """UPDATE operational_contexts SET client_or_entity=?,updated_at=? WHERE id IN
                    (SELECT operational_context_id FROM email_context_assignments WHERE email_id=? AND review_status!='moved')""",
                    [(rule["action_value"], utcnow(), email_id) for email_id in ids],
                )
        return len(ids)

    def _move_email_to_area(self, con, email_id: int, area: str) -> None:
        pid = Repository(con).project_id(self.project)
        row = con.execute(
            "SELECT id FROM operational_contexts WHERE project_id=? AND macro_category=? AND source='rule' LIMIT 1",
            (pid, area),
        ).fetchone()
        if row:
            context_id = int(row[0])
        else:
            cur = con.execute(
                """INSERT INTO operational_contexts(project_id,name,description,context_type,macro_category,
                why_grouped,suggested_user_action,source,confidence,review_status,review_priority,created_at,updated_at)
                VALUES(?,?,?,'regola',?,?,'Controlla assegnazione','rule',1,'pending',100,?,?)""",
                (
                    pid,
                    f"{area_name(area)} - regole",
                    "Email assegnate da regole utente",
                    area,
                    "Regola confermata dall'utente",
                    utcnow(),
                    utcnow(),
                ),
            )
            context_id = int(cur.lastrowid)
        move_email(con, email_id, context_id)

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
        except (OSError, urllib.error.URLError, ValueError):
            result["error"] = (
                f"Ollama non è in esecuzione o non è installato. Il programma ha provato a "
                f"collegarsi a {cfg.ollama_url} ma non ha ricevuto risposta."
            )
        result["selected_model"] = cfg.selected_model or cfg.model
        result["recommendations"] = self.recommended_models()
        return result

    def recommended_models(self) -> list[dict[str, str]]:
        specs = {
            "smollm:135m": (
                "Ultraleggero / test",
                "bassa",
                "alta",
                "scarso",
                "Solo verifica hardware",
            ),
            "smollm:360m": ("Ultraleggero / test", "bassa", "alta", "scarso", "Test rapidi"),
            "qwen2.5:0.5b": ("Ultraleggero / test", "bassa", "alta", "discreto", "Prime prove"),
            "qwen2.5:1.5b": (
                "Leggero consigliato",
                "media",
                "alta",
                "buono",
                "Primo test consigliato",
            ),
            "gemma3:1b": ("Leggero consigliato", "media", "alta", "discreto", "Sintesi brevi"),
            "llama3.2:1b": ("Leggero consigliato", "media", "alta", "discreto", "Uso generale"),
            "smollm:1.7b": (
                "Leggero consigliato",
                "media",
                "media",
                "discreto",
                "Hardware limitato",
            ),
            "qwen2.5:3b": ("Qualità migliore", "buona", "media", "buono", "Testi tecnici"),
            "llama3.2:3b": ("Qualità migliore", "buona", "media", "discreto", "Uso generale"),
            "gemma3:4b": ("Qualità migliore", "buona", "bassa", "buono", "PC più capienti"),
        }
        return [
            {
                "name": name,
                "category": values[0],
                "quality": values[1],
                "speed": values[2],
                "italian": values[3],
                "use": values[4],
            }
            for name, values in specs.items()
        ]

    def pull_model(self, model: str, confirmed: bool) -> dict[str, Any]:
        allowed = {item["name"] for item in self.recommended_models()}
        if not confirmed:
            raise ValueError("Il download richiede una conferma esplicita")
        if model not in allowed:
            raise ValueError("Modello non incluso nell'elenco consentito")
        try:
            process = subprocess.run(
                ["ollama", "pull", model], capture_output=True, text=True, timeout=3600, check=False
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Ollama non è installato o non è disponibile nel PATH") from exc
        return {"ok": process.returncode == 0, "log": (process.stdout + process.stderr)[-12000:]}

    def test_llm(self, model: str) -> dict[str, Any]:
        cfg = self.config.local_llm
        if not cfg.ollama_url.startswith(("http://localhost", "http://127.0.0.1")):
            raise ValueError("Ollama deve usare localhost")
        payload = json.dumps(
            {
                "model": model,
                "prompt": "Riassumi in 10 parole: email relative a registri rifiuti Tenax.",
                "stream": False,
            }
        ).encode()
        request = urllib.request.Request(
            cfg.ollama_url.rstrip("/") + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=cfg.timeout_seconds) as response:
                answer = json.loads(response.read().decode()).get("response", "").strip()
        except (OSError, urllib.error.URLError, ValueError) as exc:
            raise RuntimeError(
                "Il modello non ha risposto. Verifica che Ollama sia avviato e il modello installato."
            ) from exc
        if not answer:
            raise RuntimeError("Il modello ha restituito una risposta vuota")
        self.save_llm(
            {"enabled": True, "backend": "ollama", "model": model, "selected_model": model}
        )
        return {"ok": True, "answer": answer}

    def save_llm(self, values: dict[str, Any]) -> None:
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        section = data.setdefault("local_llm", {})
        for key in (
            "enabled",
            "backend",
            "ollama_url",
            "model",
            "selected_model",
            "model_path",
            "mode",
        ):
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

    def classification_ai_suggestion(
        self, kind: str, target_id: int | None = None
    ) -> dict[str, Any]:
        model = self.classification()
        if kind == "areas":
            payload = {
                "areas": model["areas"],
                "sets": [
                    {"name": x["name"], "area": x["macro_category"], "emails": x["email_count"]}
                    for x in model["sets"][:80]
                ],
            }
            schema = AreasSuggestion
            instruction = "Proponi una struttura di Aree semplice. Restituisci JSON con areas, areas_to_merge, areas_to_rename, warnings, email_reclassification_proposal."
        elif kind == "classes":
            area = next(
                (x for x in model["areas"] if int(x["id"]) == int(target_id or 0)),
                model["areas"][0],
            )
            payload = {
                "area": area,
                "classes": [x for x in model["classes"] if x["area_id"] == area["id"]],
                "sets": [x for x in model["sets"] if x["macro_category"] == area["internal_name"]][
                    :80
                ],
            }
            schema = ClassesSuggestion
            instruction = "Proponi Classi operative per questa Area. Restituisci JSON con classes, sets_to_move, emails_to_reclassify."
        else:
            raise ValueError("Tipo di suggerimento AI non supportato")
        prompt = (
            instruction
            + "\nDati locali:\n"
            + json.dumps(payload, ensure_ascii=False, default=str)[
                : self.config.local_llm.max_input_chars
            ]
        )
        with connect(self.db_path) as con:
            suggestion = validated_suggestion(con, prompt, schema, self.config.local_llm)
        return {
            "kind": kind,
            "model": self.config.local_llm.selected_model or self.config.local_llm.model,
            "suggestion": suggestion.model_dump(by_alias=True),
            "requires_confirmation": True,
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
