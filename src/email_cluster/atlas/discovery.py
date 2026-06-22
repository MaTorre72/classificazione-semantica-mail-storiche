from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, utcnow

from .common import STOPWORDS
from .reports import write_report


def scope_for_text(text: str) -> str:
    value = text.lower()
    if any(term in value for term in ("newsletter", "unsubscribe", "evento", "webinar")):
        return "Newsletter / eventi"
    if any(term in value for term in ("ordine", "spedizione", "amazon", "acquisto")):
        return "Acquisti / spedizioni"
    if any(term in value for term in ("fattura", "pagamento", "preventivo")):
        return "Amministrativo / fornitori"
    if any(
        term in value
        for term in ("rifiuti", "emissioni", "autorizz", "via", "aia", "seveso", "reach")
    ):
        return "Professionale operativo"
    return "Professionale generale"


def _subject_signals(subject: str) -> list[str]:
    return [
        word.lower()
        for word in re.findall(r"[A-Za-zÀ-ÿ]{4,}", subject or "")
        if word.lower() not in STOPWORDS
    ][:3]


def heuristic_discovery(
    db_path: Path,
    project: str,
    min_conversations: int = 3,
    max_categories: int = 30,
    reports: Path = Path("reports"),
) -> dict[str, Any]:
    """Create provisional candidates from lexical, entity, domain and attachment signals."""
    init_db(db_path)
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        con.execute(
            "DELETE FROM atlas_candidate_conversations WHERE candidate_id IN "
            "(SELECT id FROM atlas_candidate_categories WHERE project_id=?)",
            (pid,),
        )
        con.execute(
            "DELETE FROM atlas_candidate_categories WHERE project_id=? AND status='candidate'",
            (pid,),
        )
        documents = list(
            con.execute(
                """SELECT d.source_id conversation_id,d.content,ac.subject_normalized,
                          ac.participants_json,
                          group_concat(DISTINCT ae.display_name) entity_names,
                          group_concat(DISTINCT a.filename) attachment_names
                   FROM atlas_semantic_documents d
                   JOIN atlas_conversations ac ON ac.id=d.source_id
                   LEFT JOIN atlas_conversation_messages cm ON cm.conversation_id=ac.id
                   LEFT JOIN atlas_entity_mentions em ON em.email_id=cm.email_id
                   LEFT JOIN atlas_entities ae ON ae.id=em.entity_id
                   LEFT JOIN attachments a ON a.email_id=cm.email_id
                   WHERE d.project_id=? AND d.document_level='conversation'
                   GROUP BY d.source_id""",
                (pid,),
            )
        )
        embedding_table = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='atlas_embedding_cache'"
        ).fetchone()
        embeddings_used = bool(
            embedding_table
            and con.execute("SELECT 1 FROM atlas_embedding_cache LIMIT 1").fetchone()
        )
        buckets: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
        for row in documents:
            signals = _subject_signals(row["subject_normalized"] or "")
            entities = [item.strip() for item in (row["entity_names"] or "").split(",") if item]
            attachments = [
                item.strip() for item in (row["attachment_names"] or "").split(",") if item
            ]
            primary = next((item for item in entities if "." not in item), "")
            if not primary:
                primary = " / ".join(signals[:2])
            if not primary and attachments:
                primary = Path(attachments[0]).stem.replace("_", " ")
            primary = primary or "Da interpretare"
            buckets[(scope_for_text(row["content"]), primary.lower())].append(row)

        ordered = sorted(buckets.items(), key=lambda item: len(item[1]), reverse=True)
        truncated = max(0, len(ordered) - max_categories)
        ordered = ordered[:max_categories]
        fragile = 0
        candidate_summaries: list[dict[str, Any]] = []
        for (scope, signal), members in ordered:
            fragmented = len(members) < min_conversations
            fragile += int(fragmented)
            domains = Counter(
                re.findall(
                    r"@([\w.-]+)", " ".join(row["participants_json"] or "" for row in members)
                )
            ).most_common(8)
            attachments = Counter(
                item
                for row in members
                for item in (row["attachment_names"] or "").split(",")
                if item
            ).most_common(8)
            lexical = Counter(
                word
                for row in members
                for word in _subject_signals(row["subject_normalized"] or "")
            ).most_common(8)
            name = signal.title()
            cursor = con.execute(
                """INSERT INTO atlas_candidate_categories(
                       project_id,name,scope,description,lexical_signals_json,
                       recurring_domains_json,typical_attachments_json,rationale,confidence,
                       conversation_count,is_fragmented,status,created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,'candidate',?,?)""",
                (
                    pid,
                    name,
                    scope,
                    f"Conversazioni associate provvisoriamente a {name}.",
                    json.dumps([item[0] for item in lexical], ensure_ascii=False),
                    json.dumps([item[0] for item in domains], ensure_ascii=False),
                    json.dumps([item[0] for item in attachments], ensure_ascii=False),
                    "Discovery euristica: oggetti, Entità, domini e allegati ricorrenti.",
                    min(0.85, 0.4 + len(members) / 20),
                    len(members),
                    int(fragmented),
                    utcnow(),
                    utcnow(),
                ),
            )
            candidate_id = int(cursor.lastrowid)
            con.executemany(
                """INSERT INTO atlas_candidate_conversations(
                       candidate_id,conversation_id,relevance,representative
                   ) VALUES(?,?,?,?)""",
                [
                    (candidate_id, row["conversation_id"], 1.0, int(index < 3))
                    for index, row in enumerate(members)
                ],
            )
            candidate_summaries.append(
                {
                    "id": candidate_id,
                    "name": name,
                    "scope": scope,
                    "conversations": len(members),
                    "fragile": fragmented,
                }
            )

        total = len(ordered)
        ratio = total / max(len(documents), 1)
        merge_suggestions = []
        by_scope: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in candidate_summaries:
            by_scope[item["scope"]].append(item)
        for scope, items in by_scope.items():
            small = [item for item in items if item["fragile"]]
            if len(small) >= 2:
                merge_suggestions.append(
                    {"scope": scope, "categories": [item["name"] for item in small[:6]]}
                )
        warnings = [
            "Metodo provvisorio: i candidati richiedono sempre Revisione umana.",
            "Gli embedding, anche se presenti, non guidano ancora questa discovery.",
        ]
        if ratio > 0.25:
            warnings.append("Rapporto Categorie/Conversazioni elevato: risultato frammentato.")
        if truncated:
            warnings.append(f"{truncated} gruppi minori non sono stati trasformati in Categorie.")
    result = {
        "method": "heuristic",
        "embeddings_available": embeddings_used,
        "embeddings_used": False,
        "conversations": len(documents),
        "candidate_categories": total,
        "fragile_categories": fragile,
        "ratio": round(ratio, 3),
        "categories_to_merge": merge_suggestions,
        "limits": [
            "Non è una discovery semantica completa.",
            "I nomi sono ricavati da segnali osservabili e possono essere imprecisi.",
        ],
        "warnings": warnings,
        "next_step": "Controlla Categorie fragili e fusioni suggerite con email-atlas review.",
    }
    write_report(reports / "discovery_report.html", "Categorie candidate provvisorie", result)
    return result


def discover(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compatibility alias; use heuristic_discovery in new code."""
    return heuristic_discovery(*args, **kwargs)
