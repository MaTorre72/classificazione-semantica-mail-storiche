from __future__ import annotations

import sqlite3
from typing import Any

from email_cluster.review.priority import cluster_priority, email_priority
from email_cluster.storage.repository import json_dumps, utcnow


class ReviewRepository:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def resolve_run(self, project_id: int, run: str | int = "latest") -> int:
        if str(run) != "latest":
            return int(run)
        row = self.con.execute(
            "SELECT id FROM clustering_runs WHERE project_id=? AND status='completed' ORDER BY id DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if not row:
            raise ValueError("Nessuna clustering run completata")
        return int(row["id"])

    def start_session(self, project_id: int, run_id: int, name: str | None = None) -> int:
        cur = self.con.execute(
            "INSERT INTO review_sessions (project_id, clustering_run_id, name, status, created_at) VALUES (?, ?, ?, 'open', ?)",
            (project_id, run_id, name or f"Review run {run_id}", utcnow()),
        )
        session_id = int(cur.lastrowid)
        clusters = list(self.con.execute("SELECT * FROM clusters WHERE clustering_run_id=?", (run_id,)))
        for row in clusters:
            self.con.execute("""
                INSERT INTO cluster_reviews (
                    review_session_id, clustering_run_id, cluster_id, auto_label, final_label,
                    review_status, suggested_action, review_priority, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', 'inspect_emails', ?, ?, ?)
            """, (session_id, run_id, row["cluster_id"], row["label_auto"], row["label_auto"], cluster_priority(row), utcnow(), utcnow()))
        emails = self.con.execute("""
            SELECT ec.*, sc.message_type, sc.context_strategy, sc.excluded_from_main_clustering
            FROM email_clusters ec
            LEFT JOIN semantic_contexts sc ON sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=ec.email_id)
            WHERE ec.clustering_run_id=?
        """, (run_id,))
        for row in emails:
            self.con.execute("""
                INSERT INTO email_reviews (
                    review_session_id, email_id, clustering_run_id, original_cluster_id,
                    auto_message_type, review_status, review_priority, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """, (session_id, row["email_id"], run_id, row["cluster_id"], row["message_type"],
                  email_priority(row["probability"], bool(row["is_noise"]), row["context_strategy"], bool(row["excluded_from_main_clustering"])), utcnow(), utcnow()))
        excluded = self.con.execute("""
            SELECT e.id email_id, sc.message_type, sc.context_strategy
            FROM emails e JOIN semantic_contexts sc ON sc.id=(
                SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=e.id
            )
            WHERE e.project_id=? AND sc.excluded_from_main_clustering=1
              AND NOT EXISTS (
                SELECT 1 FROM email_reviews er WHERE er.review_session_id=? AND er.email_id=e.id
              )
        """, (project_id, session_id))
        for row in excluded:
            self.con.execute("""
                INSERT INTO email_reviews (
                    review_session_id, email_id, clustering_run_id, original_cluster_id,
                    auto_message_type, review_status, review_priority, created_at, updated_at
                ) VALUES (?, ?, ?, NULL, ?, 'pending', ?, ?, ?)
            """, (session_id, row["email_id"], run_id, row["message_type"],
                  email_priority(None, False, row["context_strategy"], True), utcnow(), utcnow()))
        return session_id

    def update_cluster(self, session_id: int, cluster_id: int, status: str, *, label: str | None = None, notes: str | None = None, action: str | None = None) -> None:
        row = self.con.execute(
            "SELECT auto_label, llm_label, human_label, final_label FROM cluster_reviews WHERE review_session_id=? AND cluster_id=?",
            (session_id, cluster_id),
        ).fetchone()
        if not row:
            raise ValueError("Cluster review non trovata")
        final_label = label or row["human_label"] or row["final_label"] or row["llm_label"] or row["auto_label"]
        self.con.execute("""
            UPDATE cluster_reviews SET human_label=COALESCE(?, human_label), final_label=?,
                review_status=?, human_notes=COALESCE(?, human_notes), suggested_action=COALESCE(?, suggested_action), updated_at=?
            WHERE review_session_id=? AND cluster_id=?
        """, (label, final_label, status, notes, action, utcnow(), session_id, cluster_id))

    def update_email(self, session_id: int, email_id: int, status: str, *, cluster_id: int | None = None, label: str | None = None, notes: str | None = None) -> None:
        self.con.execute("""
            UPDATE email_reviews SET review_status=?, human_cluster_id=COALESCE(?, human_cluster_id),
                human_topic_label=COALESCE(?, human_topic_label), human_notes=COALESCE(?, human_notes), updated_at=?
            WHERE review_session_id=? AND email_id=?
        """, (status, cluster_id, label, notes, utcnow(), session_id, email_id))

    def add_taxonomy_label(self, project_id: int, label: str, label_type: str, description: str = "", source: str = "human") -> int:
        self.con.execute("""
            INSERT OR IGNORE INTO taxonomy_labels
                (project_id, label, description, label_type, source, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (project_id, label, description, label_type, source, utcnow(), utcnow()))
        row = self.con.execute("SELECT id FROM taxonomy_labels WHERE project_id=? AND label=?", (project_id, label)).fetchone()
        return int(row["id"])

    def add_example(self, label_id: int, email_id: int, example_type: str) -> None:
        self.con.execute("INSERT OR IGNORE INTO label_examples (taxonomy_label_id, email_id, example_type, created_at) VALUES (?, ?, ?, ?)", (label_id, email_id, example_type, utcnow()))

    def add_rule(self, project_id: int, label_id: int, rule_type: str, pattern: str, target_field: str | None = None, priority: int = 100) -> int:
        cur = self.con.execute("""
            INSERT INTO label_rules (project_id, label_id, rule_type, pattern, target_field, priority, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (project_id, label_id, rule_type, pattern, target_field, priority, utcnow()))
        return int(cur.lastrowid)

    def save_suggestion(self, session_id: int | None, run_id: int, cluster_id: int | None, kind: str, payload: dict[str, Any]) -> int:
        cur = self.con.execute("""
            INSERT INTO review_suggestions (review_session_id, clustering_run_id, cluster_id, suggestion_type, suggestion_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (session_id, run_id, cluster_id, kind, json_dumps(payload), utcnow()))
        return int(cur.lastrowid)
