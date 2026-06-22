from __future__ import annotations

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
from email_cluster.atlas.search import build_index, search
from email_cluster.atlas.semantic_docs import build_semantic_docs
from email_cluster.storage.database import connect
from email_cluster.storage.repository import Repository


class AtlasUiData:
    """Thin GUI adapter over existing Email Atlas services."""

    def __init__(self, db_path: Path, project: str, config_path: Path):
        self.db_path = db_path
        self.project = project
        self.config_path = config_path

    def status(self) -> dict[str, Any]:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            counts = {
                "emails": con.execute(
                    "SELECT count(*) FROM emails WHERE project_id=?", (pid,)
                ).fetchone()[0],
                "conversations": con.execute(
                    "SELECT count(*) FROM atlas_conversations WHERE project_id=?", (pid,)
                ).fetchone()[0],
                "semantic_docs": con.execute(
                    "SELECT count(*) FROM atlas_semantic_documents WHERE project_id=? AND document_level='conversation'",
                    (pid,),
                ).fetchone()[0],
                "candidates": con.execute(
                    "SELECT count(*) FROM atlas_candidate_categories WHERE project_id=? AND status='candidate'",
                    (pid,),
                ).fetchone()[0],
                "approved": con.execute(
                    "SELECT count(*) FROM atlas_categories WHERE project_id=? AND status='approved'",
                    (pid,),
                ).fetchone()[0],
            }
            indexed = bool(
                con.execute("SELECT 1 FROM sqlite_master WHERE name='atlas_search'").fetchone()
            )
        phases = [
            {
                "key": "inventory",
                "name": "1. Inventario",
                "done": counts["emails"] > 0,
                "description": "Capisci cosa contiene la cartella prima di elaborarla.",
            },
            {
                "key": "parse",
                "name": "2. Preparazione",
                "done": counts["emails"] > 0,
                "description": "Pulisce i testi senza modificare le email originali.",
            },
            {
                "key": "conversations",
                "name": "3. Conversazioni",
                "done": counts["conversations"] > 0,
                "description": "Ricostruisce thread e mostra Affidabilità e anomalie.",
            },
            {
                "key": "index",
                "name": "4. Ricerca",
                "done": indexed,
                "description": "Rende l'Archivio interrogabile localmente.",
            },
            {
                "key": "entities",
                "name": "5. Soggetti",
                "done": counts["semantic_docs"] > 0,
                "description": "Rileva domini, enti e termini ricorrenti.",
            },
            {
                "key": "semantic_docs",
                "name": "6. Documenti",
                "done": counts["semantic_docs"] > 0,
                "description": "Prepara le Conversazioni per l'analisi.",
            },
            {
                "key": "discover",
                "name": "7. Categorie candidate",
                "done": counts["candidates"] > 0,
                "description": "Propone gruppi euristici e provvisori.",
            },
            {
                "key": "review",
                "name": "8. Revisione",
                "done": counts["approved"] > 0,
                "description": "Trasforma proposte in Categorie approvate.",
            },
            {
                "key": "export",
                "name": "9. Atlante",
                "done": counts["approved"] > 0,
                "description": "Esporta l'Atlante revisionato.",
            },
        ]
        next_phase = next((item for item in phases if not item["done"]), phases[-1])
        return counts | {"indexed": indexed, "phases": phases, "next_phase": next_phase}

    def conversations(self, limit: int = 100) -> list[dict[str, Any]]:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            return [
                dict(row)
                for row in con.execute(
                    """SELECT id,subject_normalized,date_start,date_end,message_count,incoming_count,
                          outgoing_count,confidence,reconstruction_method,warnings_json
                   FROM atlas_conversations WHERE project_id=?
                   ORDER BY confidence,message_count DESC LIMIT ?""",
                    (pid, limit),
                )
            ]

    def candidates(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            return [
                dict(row)
                for row in con.execute(
                    """SELECT * FROM atlas_candidate_categories WHERE project_id=?
                   ORDER BY status='candidate' DESC,is_fragmented DESC,conversation_count DESC""",
                    (pid,),
                )
            ]

    def approved(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as con:
            pid = Repository(con).project_id(self.project)
            return [
                dict(row)
                for row in con.execute(
                    "SELECT * FROM atlas_categories WHERE project_id=? ORDER BY scope,operational_theme",
                    (pid,),
                )
            ]

    def run_phase(self, phase: str, values: dict[str, Any]) -> dict[str, Any]:
        reports = Path(values.get("reports") or "reports")
        input_path = Path(values.get("input_path") or "mail")
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
        return review_action(self.db_path, self.project, candidate_id, action, name, notes)

    def search(self, query: str) -> list[dict[str, Any]]:
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
        path = Path("reports") / name
        if not path.exists():
            raise ValueError("Il report non è ancora disponibile: completa prima la relativa fase")
        return path.read_text(encoding="utf-8")
