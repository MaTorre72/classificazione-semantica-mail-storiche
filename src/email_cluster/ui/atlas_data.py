from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from email_cluster.atlas.conversations import build_conversations
from email_cluster.atlas.discovery import heuristic_discovery
from email_cluster.atlas.entities import extract_entities
from email_cluster.atlas.evaluation import evaluate
from email_cluster.atlas.export import export_atlas
from email_cluster.atlas.inventory import inventory
from email_cluster.atlas.parsing import parse_and_clean
from email_cluster.atlas.review import review_action
from email_cluster.atlas.reset import reset_project
from email_cluster.atlas.search import build_index, search
from email_cluster.atlas.semantic_docs import build_semantic_docs
from email_cluster.atlas.study import build_study_dataset, export_orange, import_classification
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository

METHOD_LABELS = {
    "headers": "Header di risposta",
    "subject_participants_date": "Fallback: oggetto, partecipanti e data",
    "isolated": "Messaggio isolato",
}


class MissingProjectError(ValueError):
    """The configured study does not exist in the selected database."""


class AtlasUiData:
    """Read-model and command adapter for the existing Email Atlas services."""

    def __init__(self, db_path: Path, project: str, config_path: Path):
        self.db_path = db_path
        self.project = project
        self.config_path = config_path
        self.reports_dir = Path("reports")
        init_db(db_path)

    def _project_id_or_none(self, con) -> int | None:
        try:
            return Repository(con).project_id(self.project)
        except ValueError:
            return None

    def _require_project_id(self, con) -> int:
        pid = self._project_id_or_none(con)
        if pid is None:
            raise MissingProjectError(
                f"Il progetto {self.project} non esiste. Crea un nuovo studio o importa un archivio."
            )
        return pid

    @staticmethod
    def _empty_conversation_summary() -> dict[str, Any]:
        return {
            "conversations": 0,
            "emails": 0,
            "isolated": 0,
            "multi_message": 0,
            "incoming": 0,
            "outgoing": 0,
            "header_based": 0,
            "fallback_based": 0,
            "low_confidence": 0,
            "with_warnings": 0,
            "isolated_percent": 0.0,
            "report_available": False,
            "warning": "Nessun progetto attivo: non ci sono conversazioni da analizzare.",
        }

    def conversation_summary(self) -> dict[str, Any]:
        with connect(self.db_path) as con:
            pid = self._project_id_or_none(con)
            if pid is None:
                return self._empty_conversation_summary()
            row = con.execute(
                """SELECT count(*) conversations,coalesce(sum(message_count),0) emails,
                          sum(message_count=1) isolated,sum(message_count>1) multi_message,
                          coalesce(sum(incoming_count),0) incoming,coalesce(sum(outgoing_count),0) outgoing,
                          sum(reconstruction_method='headers') header_based,
                          sum(reconstruction_method='subject_participants_date') fallback_based,
                          sum(confidence<0.6) low_confidence,
                          sum(warnings_json IS NOT NULL AND warnings_json NOT IN ('','[]')) with_warnings
                   FROM atlas_conversations WHERE project_id=?""",
                (pid,),
            ).fetchone()
        result = {key: int(row[key] or 0) for key in row.keys()}
        result["isolated_percent"] = round(
            result["isolated"] * 100 / max(result["conversations"], 1), 1
        )
        result["report_available"] = (self.reports_dir / "conversation_report.html").exists()
        return result

    def conversation_quality(self, summary: dict[str, Any] | None = None) -> dict[str, Any]:
        summary = summary or self.conversation_summary()
        if not summary["conversations"] or not summary["emails"]:
            judgement = "Non verificabile"
        elif summary["isolated_percent"] >= 75 or (
            summary["fallback_based"] > summary["header_based"]
            and summary["low_confidence"] >= summary["conversations"] / 2
        ):
            judgement = "Fragile"
        elif summary["header_based"] >= 3 and summary["multi_message"] >= 3:
            judgement = "Buono"
        else:
            judgement = "Accettabile"
        actions = ["Controlla prima le conversazioni a bassa affidabilita."]
        if summary["isolated_percent"] > 50:
            actions += [
                "Verifica se hai importato anche la posta inviata.",
                "Il risultato sembra frammentato: non procedere ancora alla discovery senza un controllo.",
            ]
        actions.append("Verifica almeno 10 conversazioni rappresentative prima di procedere.")
        return {"judgement": judgement, "actions": actions}

    @staticmethod
    def _decode_conversation(row: dict[str, Any]) -> dict[str, Any]:
        row["participants"] = json.loads(row.pop("participants_json", "[]") or "[]")
        row["warnings"] = json.loads(row.pop("warnings_json", "[]") or "[]")
        row["method_label"] = METHOD_LABELS.get(
            row["reconstruction_method"], row["reconstruction_method"]
        )
        row["reason"] = {
            "headers": "Uno o piu messaggi citano Message-ID precedenti in References o In-Reply-To.",
            "subject_participants_date": "Oggetto normalizzato uguale, partecipanti comuni e distanza massima di 45 giorni.",
            "isolated": "Non sono stati trovati collegamenti abbastanza affidabili con altri messaggi.",
        }.get(row["reconstruction_method"], "Metodo non documentato.")
        return row

    def conversations(self, limit: int = 500) -> list[dict[str, Any]]:
        with connect(self.db_path) as con:
            pid = self._project_id_or_none(con)
            if pid is None:
                return []
            rows = con.execute(
                """SELECT id,subject_normalized,date_start,date_end,message_count,incoming_count,
                          outgoing_count,attachments_count,participants_json,confidence,
                          reconstruction_method,warnings_json
                   FROM atlas_conversations WHERE project_id=?
                   ORDER BY confidence,message_count DESC LIMIT ?""",
                (pid, limit),
            )
            return [self._decode_conversation(dict(row)) for row in rows]

    def conversation_groups(self) -> dict[str, list[dict[str, Any]]]:
        rows = self.conversations()
        return {
            "to_check": [row for row in rows if row["confidence"] < 0.7 or row["warnings"]],
            "long": sorted(rows, key=lambda row: row["message_count"], reverse=True)[:20],
            "headers": [row for row in rows if row["reconstruction_method"] == "headers"],
            "fallback": [
                row for row in rows if row["reconstruction_method"] == "subject_participants_date"
            ],
            "isolated": [row for row in rows if row["message_count"] == 1],
            "warnings": [row for row in rows if row["warnings"]],
        }

    def conversation_detail(self, conversation_id: int) -> dict[str, Any]:
        with connect(self.db_path) as con:
            pid = self._require_project_id(con)
            row = con.execute(
                "SELECT * FROM atlas_conversations WHERE id=? AND project_id=?",
                (conversation_id, pid),
            ).fetchone()
            if not row:
                raise ValueError("Conversazione non trovata")
            messages = [
                dict(item)
                for item in con.execute(
                    """SELECT cm.position,cm.relation_method,cm.relation_confidence,e.id email_id,
                              e.subject subject_original,e.sender,e.recipients,e.cc,e.sent_at,
                              e.has_attachments,c.subject_clean subject_normalized,
                              substr(coalesce(c.current_message_text,e.body_extracted_text,e.body_plain,''),1,1200) preview,
                              substr(coalesce(c.quoted_thread_text,''),1,1200) quoted_text,
                              group_concat(a.filename,' | ') attachment_names
                       FROM atlas_conversation_messages cm JOIN emails e ON e.id=cm.email_id
                       LEFT JOIN clean_texts c ON c.id=(SELECT max(c2.id) FROM clean_texts c2 WHERE c2.email_id=e.id)
                       LEFT JOIN attachments a ON a.email_id=e.id
                       WHERE cm.conversation_id=? GROUP BY cm.position,e.id ORDER BY cm.position""",
                    (conversation_id,),
                )
            ]
        conversation = self._decode_conversation(dict(row))
        for message in messages:
            message["recipients"] = json.loads(message["recipients"] or "[]")
            message["cc"] = json.loads(message["cc"] or "[]")
            message["relation_label"] = METHOD_LABELS.get(
                message["relation_method"], message["relation_method"]
            )
        return {"conversation": conversation, "messages": messages}

    def status(self) -> dict[str, Any]:
        with connect(self.db_path) as con:
            pid = self._project_id_or_none(con)
            if pid is None:
                summary = self._empty_conversation_summary()
                counts = {
                    "emails": 0,
                    "cleaned": 0,
                    "conversations": 0,
                    "entities": 0,
                    "semantic_docs": 0,
                    "candidates": 0,
                    "approved": 0,
                }
                return counts | {
                    "project_exists": False,
                    "state": "missing_project",
                    "message": (f"Nessun progetto presente o progetto {self.project} non trovato."),
                    "next_action": "Importa un archivio o crea un nuovo studio.",
                    "email_count": 0,
                    "conversation_count": 0,
                    "candidate_category_count": 0,
                    "approved_category_count": 0,
                    "indexed": False,
                    "phases": [],
                    "next_phase": None,
                    "conversation_summary": summary,
                    "conversation_quality": self.conversation_quality(summary),
                }

        summary = self.conversation_summary()
        quality = self.conversation_quality(summary)
        with connect(self.db_path) as con:
            pid = self._require_project_id(con)

            def scalar(sql: str) -> int:
                return int(con.execute(sql, (pid,)).fetchone()[0] or 0)

            counts = {
                "emails": scalar("SELECT count(*) FROM emails WHERE project_id=?"),
                "cleaned": scalar(
                    "SELECT count(*) FROM clean_texts c JOIN emails e ON e.id=c.email_id WHERE e.project_id=?"
                ),
                "conversations": summary["conversations"],
                "entities": scalar("SELECT count(*) FROM atlas_entities WHERE project_id=?"),
                "semantic_docs": scalar(
                    "SELECT count(*) FROM atlas_semantic_documents WHERE project_id=? AND document_level='conversation'"
                ),
                "candidates": scalar(
                    "SELECT count(*) FROM atlas_candidate_categories WHERE project_id=? AND status='candidate'"
                ),
                "approved": scalar(
                    "SELECT count(*) FROM atlas_categories WHERE project_id=? AND status='approved'"
                ),
            }
            indexed = bool(
                con.execute("SELECT 1 FROM sqlite_master WHERE name='atlas_search'").fetchone()
            )

        def phase(key: str, name: str, state: str, description: str, report: str = ""):
            return {
                "key": key,
                "name": name,
                "state": state,
                "done": state == "completed",
                "description": description,
                "report": report,
            }

        conversation_state = "not_ready"
        if summary["conversations"]:
            conversation_state = "fragile" if quality["judgement"] == "Fragile" else "warning"
            if summary["report_available"] and quality["judgement"] in {"Buono", "Accettabile"}:
                conversation_state = "completed"
        phases = [
            phase(
                "inventory",
                "1. Inventario",
                "completed" if counts["emails"] else "pending",
                "Misura il contenuto della cartella.",
            ),
            phase(
                "parse",
                "2. Preparazione",
                "completed"
                if counts["cleaned"]
                else "not_ready"
                if not counts["emails"]
                else "pending",
                "Pulisce i testi senza modificare le sorgenti.",
            ),
            phase(
                "conversations",
                "3. Conversazioni",
                conversation_state,
                "Verifica collegamenti, isolamento e affidabilita.",
                "conversation_report.html",
            ),
            phase(
                "index",
                "4. Ricerca",
                "completed"
                if indexed
                else "not_ready"
                if not counts["conversations"]
                else "pending",
                "Indicizza le conversazioni localmente.",
            ),
            phase(
                "entities",
                "5. Soggetti",
                "completed"
                if counts["entities"] and (self.reports_dir / "entity_report.html").exists()
                else "not_ready"
                if not indexed
                else "pending",
                "Rileva domini, soggetti e termini ricorrenti.",
                "entity_report.html",
            ),
            phase(
                "semantic_docs",
                "6. Documenti",
                "completed"
                if counts["semantic_docs"]
                else "not_ready"
                if not counts["entities"]
                else "pending",
                "Prepara documenti di livello conversazione.",
            ),
            phase(
                "discover",
                "7. Categorie candidate",
                "completed"
                if counts["candidates"]
                else "not_ready"
                if not counts["semantic_docs"]
                else "pending",
                "Propone categorie euristiche e provvisorie.",
                "discovery_report.html",
            ),
            phase(
                "review",
                "8. Revisione",
                "completed"
                if counts["approved"]
                else "not_ready"
                if not counts["candidates"]
                else "pending",
                "Registra decisioni umane.",
            ),
            phase(
                "export",
                "9. Atlante",
                "completed" if counts["approved"] else "not_ready",
                "Esporta solo categorie revisionate.",
            ),
        ]
        next_phase = next(
            (item for item in phases if item["state"] not in {"completed", "warning", "fragile"}),
            phases[-1],
        )
        return counts | {
            "project_exists": True,
            "state": "ready" if counts["emails"] else "empty_project",
            "indexed": indexed,
            "phases": phases,
            "next_phase": next_phase,
            "conversation_summary": summary,
            "conversation_quality": quality,
        }

    def candidates(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as con:
            pid = self._project_id_or_none(con)
            if pid is None:
                return []
            return [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM atlas_candidate_categories WHERE project_id=? ORDER BY status='candidate' DESC,is_fragmented DESC,conversation_count DESC",
                    (pid,),
                )
            ]

    def approved(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as con:
            pid = self._project_id_or_none(con)
            if pid is None:
                return []
            return [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM atlas_categories WHERE project_id=? ORDER BY scope,operational_theme",
                    (pid,),
                )
            ]

    def _require_discovery_prerequisites(self) -> None:
        status = self.status()
        if not status["conversations"]:
            raise ValueError(
                "Non posso proporre categorie: mancano le Conversazioni. Esegui prima la fase 3."
            )
        if not status["indexed"]:
            raise ValueError(
                "Non posso proporre categorie: manca l'indice di ricerca. Esegui prima la fase 4."
            )
        if not status["entities"]:
            raise ValueError(
                "Non posso proporre categorie: mancano i Soggetti. Esegui prima la fase 5."
            )
        if not status["semantic_docs"]:
            raise ValueError(
                "Non posso proporre categorie: mancano i Documenti conversazione. Esegui prima la fase 6."
            )

    def run_phase(self, phase: str, values: dict[str, Any]) -> dict[str, Any]:
        reports = Path(values.get("reports") or self.reports_dir)
        input_path = Path(values.get("input_path") or "mail")
        if phase == "build_study":
            accounts = [
                item.strip() for item in values.get("accounts", "").split(",") if item.strip()
            ]
            return build_study_dataset(
                input_path,
                self.db_path,
                self.project,
                Path(values.get("output") or "outputs/study_pack"),
                self.config_path,
                accounts,
                bool(values.get("rebuild_derived")),
            )
        if not self.status()["project_exists"]:
            raise MissingProjectError(
                f"Il progetto {self.project} non esiste. Crea un nuovo studio o importa un archivio."
            )
        if phase == "reset_project":
            return reset_project(
                self.db_path, self.project, confirm=bool(values.get("confirm"))
            ).to_dict()
        if phase == "export_orange":
            return export_orange(
                self.db_path, self.project, Path(values.get("output") or "outputs/orange_pack")
            )
        if phase == "import_classification":
            return import_classification(
                self.db_path,
                self.project,
                Path(values.get("file") or "outputs/study_pack/classification_workspace.csv"),
                Path(values.get("output") or "outputs/atlas_finale"),
            )
        if phase == "inventory":
            return inventory(input_path, self.db_path, self.project, reports)
        if phase == "parse":
            return parse_and_clean(self.db_path, self.project, self.config_path, reports)
        if phase == "conversations":
            accounts = [
                item.strip() for item in values.get("accounts", "").split(",") if item.strip()
            ]
            return build_conversations(self.db_path, self.project, accounts, reports)
        if phase == "index":
            return build_index(self.db_path, self.project)
        if phase == "entities":
            return extract_entities(self.db_path, self.project, reports=reports)
        if phase == "semantic_docs":
            return build_semantic_docs(self.db_path, self.project)
        if phase == "discover":
            self._require_discovery_prerequisites()
            return heuristic_discovery(self.db_path, self.project, reports=reports)
        if phase == "export":
            return export_atlas(
                self.db_path,
                self.project,
                Path(values.get("output") or "data/atlas"),
                bool(values.get("public_safe")),
            )
        if phase == "evaluate":
            return evaluate(self.db_path, self.project, reports)
        raise ValueError("Fase non disponibile dalla GUI")

    def review(
        self, candidate_id: int, action: str, name: str | None, notes: str
    ) -> dict[str, Any]:
        if not self.status()["project_exists"]:
            raise MissingProjectError(f"Il progetto {self.project} non esiste")
        return review_action(self.db_path, self.project, candidate_id, action, name, notes)

    def search(self, query: str) -> list[dict[str, Any]]:
        if not self.status()["project_exists"]:
            return []
        return search(self.db_path, query, self.project)

    def report(self, name: str) -> str:
        allowed = {
            "inventory_report.html",
            "parsing_report.html",
            "cleaning_report.html",
            "conversation_report.html",
            "entity_report.html",
            "discovery_report.html",
            "evaluation_report.html",
        }
        if name not in allowed:
            raise ValueError("Report non riconosciuto")
        path = self.reports_dir / name
        if not path.exists():
            raise ValueError("Il report non e ancora disponibile: completa prima la relativa fase")
        return path.read_text(encoding="utf-8")
