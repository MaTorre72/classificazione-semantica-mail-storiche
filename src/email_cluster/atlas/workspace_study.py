from __future__ import annotations

import csv
import html
import json
import math
import re
import sqlite3
import zipfile
from array import array
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from email_cluster.atlas.conversations import build_conversations
from email_cluster.atlas.discovery import heuristic_discovery
from email_cluster.atlas.entities import extract_entities
from email_cluster.atlas.embeddings import embed_documents
from email_cluster.atlas.parsing import parse_and_clean
from email_cluster.atlas.search import build_index
from email_cluster.atlas.semantic_docs import build_semantic_docs
from email_cluster.atlas.study import (
    _edges_and_nodes,
    _conversation_rows,
    _terms,
    _write_csv,
    export_orange,
    import_classification,
)
from email_cluster.ingestion.scanner import scan_local_folder
from email_cluster.parsing.email_parser import parse_eml, parse_mbox
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository
from email_cluster.storage.workspace_health import (
    WorkspaceIntegrityError,
    doctor_workspace,
    ensure_project,
)

STAGES = [
    "scan_input",
    "import_mbox",
    "parse_messages",
    "detect_sent_received",
    "build_conversations",
    "extract_attachments_metadata",
    "extract_attachment_text_optional",
    "build_semantic_text",
    "compute_embeddings_optional",
    "topic_discovery",
    "build_classification_workspace",
    "generate_report",
]

STAGE_OUTPUT_STAGES = {
    "topic_discovery",
    "build_classification_workspace",
    "generate_report",
}

CONVERSATION_FIELDS = [
    "conversation_id",
    "date_start",
    "date_end",
    "year",
    "month",
    "subject_normalized",
    "message_count",
    "incoming_count",
    "outgoing_count",
    "is_mixed_incoming_outgoing",
    "participants",
    "sender_domains",
    "main_domain",
    "has_attachments",
    "attachment_count",
    "attachment_types",
    "clean_summary",
    "semantic_text",
    "probable_scope",
    "scope_confidence",
    "scope_reason",
    "probable_actor",
    "probable_theme",
    "probable_project",
    "probable_activity",
    "confidence",
    "warnings",
]

CLASSIFICATION_FIELDS = [
    "candidate_id",
    "proposed_name",
    "proposed_scope",
    "proposed_activity",
    "proposed_project_context",
    "proposed_actor",
    "proposed_theme",
    "description",
    "why_it_exists",
    "conversation_count",
    "representative_conversations",
    "borderline_conversations",
    "outlier_conversations",
    "main_terms",
    "main_domains",
    "main_attachments",
    "similar_candidates",
    "possible_merge_with",
    "possible_exclusions",
    "confidence",
    "suggested_decision",
    "human_decision",
    "final_name",
    "final_scope",
    "final_activity",
    "final_theme",
    "final_description",
    "notes",
]


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _count_csv_rows(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _infer_accounts(db: Path, project: str) -> list[str]:
    sent_tokens = ("sent", "posta inviata", "inviata", "inviati", "sent mail")
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        rows = con.execute(
            """SELECT e.sender,s.path,count(*) n FROM emails e JOIN source_files s ON s.id=e.source_file_id
               WHERE e.project_id=? GROUP BY e.sender,s.path""",
            (pid,),
        )
        counts = Counter()
        for row in rows:
            if any(token in row["path"].lower() for token in sent_tokens):
                counts[row["sender"]] += row["n"]
    return [address for address, _ in counts.most_common(10) if address]


def _sql_in_clause(values: Sequence[int]) -> str:
    if not values:
        raise ValueError("Serve almeno un valore per costruire la clausola IN")
    return ",".join("?" for _ in values)


def _topic_label_terms(*texts: str) -> list[str]:
    token_re = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9]{2,}")
    noise = {"bcc", "cc", "come", "data", "date", "from", "message", "sent", "subject", "to", "your"}
    terms: list[str] = []
    for text in texts:
        for token in token_re.findall(text or ""):
            lowered = token.lower()
            if lowered in noise or re.fullmatch(r"\d{1,2}[_/-]\d{4}", lowered):
                continue
            if re.fullmatch(r"\d{1,2}[_/-]\d{1,2}[_/-]\d{2,4}", lowered):
                continue
            if re.fullmatch(r"\d{4}[_/-]\d{1,2}[_/-]\d{1,2}", lowered):
                continue
            terms.append(lowered)
    return terms


def _topic_member_domains(members: list[dict[str, Any]]) -> list[str]:
    domains: list[str] = []
    for row in members:
        for domain in row.get("domains") or []:
            lowered = str(domain or "").strip().lower()
            if lowered:
                domains.append(lowered)
    return domains


def _topic_member_attachments(members: list[dict[str, Any]]) -> list[str]:
    attachments: list[str] = []
    for row in members:
        for name in row.get("attachments") or []:
            lowered = Path(str(name or "")).name.strip().lower()
            if lowered:
                attachments.append(lowered)
    return attachments


def _describe_topic(
    members: list[dict[str, Any]],
    *,
    main_terms: list[str],
    fallback_label: str,
) -> dict[str, Any]:
    scope, _, scope_reason = _topic_scope_summary(members)
    all_terms = Counter(
        term
        for row in members
        for term in _topic_label_terms(
            row.get("subject_normalized") or "",
            row.get("semantic_text") or row.get("analysis_text") or "",
        )
    )
    domains = Counter(_topic_member_domains(members))
    attachments = Counter(_topic_member_attachments(members))
    top_terms = [term for term, _ in all_terms.most_common(8)] or list(main_terms)
    top_domains = [domain for domain, _ in domains.most_common(6)]
    top_attachments = [name for name, _ in attachments.most_common(6)]
    warnings: list[str] = []
    mixed_scopes = {
        str(row.get("probable_scope") or "Da definire")
        for row in members
        if str(row.get("probable_scope") or "").strip()
    }
    if len(members) < 3:
        warnings.append("Categoria piccola: verifica se va unita ad altre conversazioni simili.")
    if len(mixed_scopes) > 1:
        warnings.append("Scope misti nel topic: controlla i borderline prima di approvare.")

    rule_specs = (
        (
            "Account / notifiche tecniche",
            {"github", "google", "account", "accounts", "login", "password", "security", "accesso", "verifica"},
            {"github.com", "google.com", "accounts.google.com"},
            set(),
            "Scope tecnico e segnali ricorrenti di account o notifiche automatiche.",
        ),
        (
            "PEC / Hiro e notifiche collegate",
            {"pec", "hiro", "daticert", "postacert", "accettazione", "consegna", "ricevuta"},
            {"legalmail.it", "pec.it", "postacert.it"},
            {".eml", ".p7m"},
            "Messaggi riconducibili a PEC o al circuito Hiro.",
        ),
        (
            "Amministrazione / fatture e pagamenti",
            {"fattura", "pagamento", "pagamenti", "bonifico", "preventivo", "fornitore", "invoice"},
            set(),
            {".pdf"},
            "Segnali amministrativi ricorrenti su fatture, pagamenti o fornitori.",
        ),
        (
            "Newsletter / eventi",
            {"newsletter", "webinar", "evento", "eventi", "iscriviti", "unsubscribe", "registrazione"},
            set(),
            set(),
            "Segnali tipici di newsletter, iscrizioni o inviti a eventi.",
        ),
        (
            "Pratiche ambientali / autorizzazioni",
            {"aia", "aua", "autorizzazione", "autorizzazioni", "arpav", "emissioni", "rifiuti", "seveso", "reach"},
            set(),
            {".pdf", ".docx"},
            "Termini coerenti con pratiche ambientali o autorizzative.",
        ),
        (
            "Acquisti / spedizioni",
            {"ordine", "spedizione", "tracking", "consegna", "amazon", "acquisto"},
            set(),
            set(),
            "Segnali tipici di acquisti, ordini o spedizioni.",
        ),
        (
            "Personale / relazioni",
            {"cena", "vacanza", "famiglia", "compleanno", "auguri", "amico", "sabato"},
            set(),
            set(),
            "Segnali di corrispondenza personale o relazionale.",
        ),
    )

    matched_scope = scope.lower()
    label = fallback_label
    label_reason = f"Fallback lessicale basato sui termini prevalenti: {', '.join(top_terms[:4]) or fallback_label}."
    for candidate_label, term_signals, domain_signals, attachment_signals, reason in rule_specs:
        signal_hits = [term for term in top_terms if term in term_signals]
        domain_hits = [domain for domain in top_domains if domain in domain_signals]
        attachment_hits = [
            Path(name).suffix.lower()
            for name in top_attachments
            if Path(name).suffix.lower() in attachment_signals
        ]
        scope_hint = candidate_label.split(" / ", 1)[0].lower() in matched_scope
        if signal_hits or domain_hits or attachment_hits or scope_hint:
            label = candidate_label
            details = signal_hits[:3] + domain_hits[:2] + attachment_hits[:2]
            label_reason = reason
            if details:
                label_reason = f"{reason} Segnali: {', '.join(details)}."
            break
    else:
        if scope not in {"Da definire", "Professionale generale"}:
            label = scope
            label_reason = f"Categoria allineata allo scope prevalente del topic. {scope_reason}"
        elif top_terms:
            label = " / ".join(top_terms[:3])

    if label_reason.startswith("Fallback lessicale"):
        warnings.append("Nome categoria derivato da fallback lessicale: confermare manualmente.")

    scope_counts = Counter(str(row.get("probable_scope") or "Da definire") for row in members)
    best_scope = scope_counts.most_common(1)[0][0] if scope_counts else "Da definire"
    representative_ids = [row["id"] for row in members[:8]]
    borderline_ids = [
        row["id"]
        for row in members
        if str(row.get("probable_scope") or "Da definire") != best_scope
    ][:6]
    outlier_ids = [
        row["id"]
        for row in members
        if not _topic_label_terms(
            row.get("subject_normalized") or "",
            row.get("semantic_text") or row.get("analysis_text") or "",
        )
    ][:6]
    return {
        "label": label,
        "label_reason": label_reason,
        "warnings": warnings,
        "main_domains": top_domains,
        "main_attachments": top_attachments,
        "representative_conversations": representative_ids,
        "borderline_conversations": borderline_ids,
        "outlier_conversations": outlier_ids,
    }


def _topic_discovery(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[int], str]:
    if not rows:
        return [], [], "unavailable"
    texts = [row.get("semantic_text") or row.get("analysis_text") or "" for row in rows]
    if len(rows) == 1:
        labels = [0]
        matrix = TfidfVectorizer(max_features=500).fit_transform(texts)
        method = "tfidf_svd_kmeans"
    else:
        matrix = TfidfVectorizer(max_features=3000, min_df=1, stop_words=None).fit_transform(texts)
        components = min(50, max(2, matrix.shape[0] - 1), max(2, matrix.shape[1] - 1))
        reduced = TruncatedSVD(n_components=components, random_state=42).fit_transform(matrix)
        try:
            from bertopic import BERTopic

            labels, _ = BERTopic(
                embedding_model=None,
                calculate_probabilities=False,
                verbose=False,
                min_topic_size=2,
            ).fit_transform(texts, embeddings=reduced)
            method = "bertopic"
        except Exception:  # noqa: BLE001 - optional BERTopic must never block the fallback
            clusters = min(40, max(2, round(math.sqrt(len(rows) / 2))))
            clusters = min(clusters, len(rows))
            labels = KMeans(n_clusters=clusters, random_state=42, n_init=10).fit_predict(reduced)
            method = "tfidf_svd_kmeans"
    topic_ids = [int(label) for label in labels]
    topics = []
    for label in sorted(set(labels)):
        members = [row for row, item_label in zip(rows, labels) if item_label == label]
        subject_terms = [
            term
            for row in members
            for term in _topic_label_terms(row.get("subject_normalized") or "")
        ]
        semantic_terms = [
            term
            for row in members
            for term in _topic_label_terms(row.get("semantic_text") or row.get("analysis_text") or "")
        ]
        terms = [term for term, _ in Counter(subject_terms or semantic_terms).most_common(12)]
        fallback_label = " / ".join(terms[:3]) or f"Topic {label}"
        description = _describe_topic(members, main_terms=terms, fallback_label=fallback_label)
        scope, scope_confidence, scope_reason = _topic_scope_summary(members)
        topics.append(
            {
                "topic_id": int(label),
                "label": description["label"],
                "label_reason": description["label_reason"],
                "conversation_count": len(members),
                "main_terms": terms,
                "main_domains": description["main_domains"],
                "main_attachments": description["main_attachments"],
                "warnings": description["warnings"],
                "representative_conversations": description["representative_conversations"],
                "borderline_conversations": description["borderline_conversations"],
                "outlier_conversations": description["outlier_conversations"],
                "method": method,
                # Store the topic-level summaries here so the final workspace can avoid
                # rebuilding a second per-topic member map in memory.
                "scope_summary": {
                    "scope": scope,
                    "confidence": scope_confidence,
                    "reason": scope_reason,
                },
                "example_subjects": _topic_example_subjects(members),
            }
        )
    return topics, topic_ids, method


def _topic_scope_summary(
    members: list[dict[str, Any]],
) -> tuple[str, float, str]:
    if not members:
        return "Da definire", 0.0, "Scope non determinabile."
    scope_counts = Counter(str(row.get("probable_scope") or "Da definire") for row in members)
    best_scope, best_count = scope_counts.most_common(1)[0]
    confidences = [
        float(row.get("scope_confidence") or 0.0)
        for row in members
        if str(row.get("probable_scope") or "") == best_scope
    ]
    reasons = [
        str(row.get("scope_reason") or "").strip()
        for row in members
        if str(row.get("probable_scope") or "") == best_scope and str(row.get("scope_reason") or "").strip()
    ]
    average_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
    coverage = f"{best_count}/{len(members)} conversazioni"
    reason = reasons[0] if reasons else "Scope derivato dai segnali prevalenti del topic."
    if best_count < len(members):
        reason = f"{reason} Copertura topic: {coverage}."
    else:
        reason = f"{reason} Copertura topic completa."
    return best_scope, average_confidence, reason


def _topic_example_subjects(members: list[dict[str, Any]], limit: int = 3) -> list[str]:
    examples: list[str] = []
    seen: set[str] = set()
    for row in members:
        subject = str(row.get("subject_normalized") or "").strip()
        if not subject:
            continue
        lowered = subject.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        examples.append(subject)
        if len(examples) >= limit:
            break
    return examples


def _classification_suggestion(
    topic: dict[str, Any],
) -> dict[str, str]:
    scope_summary = topic.get("scope_summary") or {}
    proposed_scope = str(scope_summary.get("scope") or "Da definire")
    scope_confidence = float(scope_summary.get("confidence") or 0.0)
    scope_reason = str(scope_summary.get("reason") or "Scope non determinabile.")
    main_terms = list(topic.get("main_terms") or [])
    main_domains = list(topic.get("main_domains") or [])
    warnings = list(topic.get("warnings") or [])
    examples: list[str] = []
    for example in topic.get("example_subjects") or []:
        subject = str(example).strip()
        if subject:
            examples.append(subject)
    label = str(topic.get("label") or "Categoria da verificare")
    fallback_terms = ", ".join(main_terms[:3]) or label.lower()
    fallback_domains = ", ".join(main_domains[:2])

    activity_map = {
        "Account / notifiche tecniche": "Gestire accessi, verifiche e notifiche di sicurezza degli account.",
        "PEC / Hiro e notifiche collegate": "Verificare ricevute PEC, accettazioni e notifiche Hiro collegate.",
        "Amministrazione / fatture e pagamenti": "Gestire fatture, pagamenti e documenti dei fornitori.",
        "Newsletter / eventi": "Valutare newsletter, inviti e registrazioni a eventi o webinar.",
        "Pratiche ambientali / autorizzazioni": "Seguire pratiche autorizzative e adempimenti ambientali.",
        "Acquisti / spedizioni": "Monitorare ordini, spedizioni e consegne.",
        "Personale / relazioni": "Raccogliere scambi personali e coordinamento relazionale.",
    }
    theme_map = {
        "Account / notifiche tecniche": "Account digitali, sicurezza e accessi.",
        "PEC / Hiro e notifiche collegate": "PEC, ricevute e protocolli di consegna.",
        "Amministrazione / fatture e pagamenti": "Amministrazione, fornitori e flussi di pagamento.",
        "Newsletter / eventi": "Newsletter, webinar ed eventi informativi.",
        "Pratiche ambientali / autorizzazioni": "Autorizzazioni ambientali, compliance e pratiche tecniche.",
        "Acquisti / spedizioni": "Ordini, logistica e consegne.",
        "Personale / relazioni": "Relazioni personali e vita quotidiana.",
    }
    proposed_activity = activity_map.get(
        label,
        f"Seguire corrispondenza ricorrente su {fallback_terms}.",
    )
    proposed_theme = theme_map.get(
        label,
        f"Tema prevalente: {fallback_terms}.",
    )
    if fallback_domains:
        proposed_theme = f"{proposed_theme} Domini utili: {fallback_domains}."

    if any("Scope misti" in warning for warning in warnings) or scope_confidence < 0.55:
        suggested_decision = "unclear"
    elif any("Fallback lessicale" in warning for warning in warnings):
        suggested_decision = "unclear"
    elif any("Categoria piccola" in warning for warning in warnings) and scope_confidence < 0.75:
        suggested_decision = "unclear"
    else:
        suggested_decision = "approve"

    if proposed_scope == "Newsletter / eventi" and any(
        term in {"newsletter", "unsubscribe"} for term in main_terms
    ):
        suggested_decision = "exclude"

    example_text = (
        "; ".join(f'"{example}"' for example in examples)
        if examples
        else "nessun subject rappresentativo disponibile"
    )
    description = (
        f"Topic con {topic['conversation_count']} conversazioni. "
        f"Esempi: {example_text}."
    )
    notes = (
        f"Scope reason: {scope_reason} "
        f"Suggested decision: {suggested_decision}. "
        f"Topic warnings: {'; '.join(warnings) or 'none'}"
    )
    return {
        "proposed_scope": proposed_scope,
        "proposed_activity": proposed_activity,
        "proposed_theme": proposed_theme,
        "description": description,
        "suggested_decision": suggested_decision,
        "notes": notes,
    }


def _workspace_config(
    workspace: Path,
    with_text: bool,
    max_mb: int,
    *,
    extract_text: bool | None = None,
    filename: str = "study_config.yaml",
) -> Path:
    source = Path("config/default.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8")) if source.exists() else {}
    if extract_text is None:
        extract_text = with_text
    data.setdefault("attachments", {}).update(
        {"enabled": True, "extract_text": extract_text, "max_file_size_mb": max_mb}
    )
    path = workspace / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _stage_index(stage: str) -> int:
    try:
        return STAGES.index(stage)
    except ValueError as exc:
        raise ValueError(f"Stage non riconosciuto: {stage}") from exc


def _required_stages(targets: list[str]) -> list[str]:
    return STAGES[: max(_stage_index(stage) for stage in targets) + 1]


def _downstream_stages(stage: str) -> list[str]:
    return STAGES[_stage_index(stage) :]


def _default_state() -> dict[str, Any]:
    return {
        "version": 2,
        "selected_targets": [],
        "warnings": [],
        "stage_details": {},
        "stages": {},
        "options": {},
    }


def _load_state(path: Path, resume: bool) -> dict[str, Any]:
    if not (resume and path.exists()):
        return _default_state()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    state = _default_state()
    state.update(loaded)
    state["stage_details"] = dict(loaded.get("stage_details") or {})
    state["stages"] = dict(loaded.get("stages") or {})
    state["options"] = dict(loaded.get("options") or {})
    return state


def _set_stage_status(
    state: dict[str, Any], stage: str, status: str, *, skipped_via_resume: bool = False
) -> None:
    details = dict(state["stage_details"].get(stage) or {})
    details.update(
        {
            "status": status,
            "completed_at": datetime.now().isoformat() if status == "completed" else None,
            "skipped_via_resume": skipped_via_resume,
        }
    )
    state["stage_details"][stage] = details
    state["stages"][stage] = status


def _invalidate_stages(state: dict[str, Any], start_stage: str, reason: str) -> None:
    details = state.setdefault("stage_details", {})
    for stage in _downstream_stages(start_stage):
        entry = dict(details.get(stage) or {})
        entry.update(
            {
                "status": "pending",
                "completed_at": None,
                "skipped_via_resume": False,
                "invalidated_reason": reason,
            }
        )
        details[stage] = entry
        state["stages"][stage] = "pending"


def _should_skip_stage(
    stage: str,
    state: dict[str, Any],
    resume: bool,
    required: set[str],
    force_run: set[str],
    workspace: Path,
    db: Path,
    project: str,
) -> bool:
    if not resume or stage not in required or stage in force_run:
        return False
    if stage in STAGE_OUTPUT_STAGES:
        return False
    return state["stages"].get(stage) == "completed" and _stage_artifact_available(
        stage, workspace, db, project
    )


def _stage_artifact_available(stage: str, workspace: Path, db: Path, project: str) -> bool:
    if stage == "scan_input":
        return (workspace / "input_inventory.csv").exists()
    if not db.exists():
        return False
    if stage == "extract_attachments_metadata":
        try:
            with connect(db) as con:
                pid = Repository(con).project_id(project)
                counts = con.execute(
                    """SELECT count(*) total, coalesce(sum(has_attachments), 0) attached
                       FROM emails WHERE project_id=?""",
                    (pid,),
                ).fetchone()
                attachment_rows = con.execute(
                    """SELECT count(*) FROM attachments a
                       JOIN emails e ON e.id=a.email_id
                       WHERE e.project_id=?""",
                    (pid,),
                ).fetchone()
        except (sqlite3.Error, ValueError):
            return False
        total = int(counts["total"]) if counts else 0
        attached = int(counts["attached"]) if counts else 0
        available = int(attachment_rows[0]) if attachment_rows else 0
        return total > 0 and (attached == 0 or available >= attached)
    if stage == "extract_attachment_text_optional":
        return _stage_artifact_available("extract_attachments_metadata", workspace, db, project)
    checks = {
        "import_mbox": "SELECT count(*) FROM emails e JOIN projects p ON p.id=e.project_id WHERE p.name=?",
        "parse_messages": "SELECT count(*) FROM clean_texts c JOIN emails e ON e.id=c.email_id JOIN projects p ON p.id=e.project_id WHERE p.name=?",
        "build_conversations": "SELECT count(*) FROM atlas_conversations ac JOIN projects p ON p.id=ac.project_id WHERE p.name=?",
        "build_semantic_text": "SELECT count(*) FROM atlas_search s JOIN projects p ON p.id=s.project_id WHERE p.name=?",
    }
    query = checks.get(stage)
    if not query:
        return True
    try:
        with connect(db) as con:
            row = con.execute(query, (project,)).fetchone()
    except sqlite3.Error:
        return False
    return bool(row and row[0])


def _clear_attachment_text(db: Path, project: str) -> int:
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        cur = con.execute(
            """UPDATE attachments
               SET extracted_text=NULL,
                   text_excerpt=NULL,
                   extraction_status='metadata_only',
                   extraction_error=NULL
               WHERE email_id IN (SELECT id FROM emails WHERE project_id=?)
                 AND (
                    coalesce(extracted_text, '')!=''
                    OR coalesce(text_excerpt, '')!=''
                    OR coalesce(extraction_error, '')!=''
                    OR coalesce(extraction_status, 'metadata_only')!='metadata_only'
                 )""",
            (pid,),
        )
        return max(cur.rowcount, 0)


def _attachment_key(
    *,
    filename: str | None,
    mime_type: str | None,
    size_bytes: int | None,
    sha256: str | None,
) -> tuple[str, str, int, str]:
    return (
        filename or "",
        mime_type or "",
        int(size_bytes or -1),
        sha256 or "",
    )


def _extract_attachment_texts(input_path: Path, db: Path, project: str, max_attachment_mb: int) -> int:
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        email_lookup = {
            row["message_hash"]: int(row["id"])
            for row in con.execute(
                "SELECT id,message_hash FROM emails WHERE project_id=?",
                (pid,),
            )
        }
        attachment_rows = [
            dict(row)
            for row in con.execute(
                """SELECT a.id,a.email_id,a.filename,a.mime_type,a.size_bytes,a.sha256
                   FROM attachments a
                   JOIN emails e ON e.id=a.email_id
                   WHERE e.project_id=?
                   ORDER BY a.email_id,a.id""",
                (pid,),
            )
        ]
    if not email_lookup or not attachment_rows:
        return 0

    attachment_map: dict[int, list[dict[str, Any]]] = {}
    for row in attachment_rows:
        attachment_map.setdefault(int(row["email_id"]), []).append(row)

    updated = 0
    for candidate in scan_local_folder(input_path):
        parsed_messages = (
            [parse_eml(candidate.path, extract_attachments=True, max_attachment_size_mb=max_attachment_mb)]
            if candidate.file_type == "eml"
            else parse_mbox(candidate.path, extract_attachments=True, max_attachment_size_mb=max_attachment_mb)
        )
        for parsed in parsed_messages:
            email_id = email_lookup.get(parsed.message_hash)
            if email_id is None:
                continue
            rows_for_email = attachment_map.get(email_id) or []
            if not rows_for_email or not parsed.attachments:
                continue
            buckets: dict[tuple[str, str, int, str], list[int]] = {}
            fallback_ids = [int(row["id"]) for row in rows_for_email]
            for row in rows_for_email:
                buckets.setdefault(
                    _attachment_key(
                        filename=row.get("filename"),
                        mime_type=row.get("mime_type"),
                        size_bytes=row.get("size_bytes"),
                        sha256=row.get("sha256"),
                    ),
                    [],
                ).append(int(row["id"]))
            used_ids: set[int] = set()
            for attachment in parsed.attachments:
                key = _attachment_key(
                    filename=attachment.filename,
                    mime_type=attachment.mime_type,
                    size_bytes=attachment.size_bytes,
                    sha256=attachment.sha256,
                )
                attachment_id: int | None = None
                for candidate_id in buckets.get(key, []):
                    if candidate_id not in used_ids:
                        attachment_id = candidate_id
                        break
                if attachment_id is None:
                    for candidate_id in fallback_ids:
                        if candidate_id not in used_ids:
                            attachment_id = candidate_id
                            break
                if attachment_id is None:
                    continue
                used_ids.add(attachment_id)
                with connect(db) as con:
                    con.execute(
                        """UPDATE attachments
                           SET extracted_text=?,
                               text_excerpt=?,
                               extraction_status=?,
                               extraction_error=?
                           WHERE id=?""",
                        (
                            attachment.extracted_text,
                            attachment.text_excerpt,
                            attachment.extraction_status,
                            attachment.extraction_error,
                            attachment_id,
                        ),
                    )
                updated += 1
    return updated


def run_study(
    input_path: Path,
    workspace: Path,
    *,
    stages: list[str] | None = None,
    resume: bool = True,
    rebuild_stage: str | None = None,
    attachments_text: bool = True,
    max_attachment_mb: int = 20,
    sample_size: int | None = None,
    limit_messages: int | None = None,
    limit_conversations: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    source_folders: tuple[str, ...] = (),
    embedding_provider: str = "none",
    embedding_model: str = "",
) -> dict[str, Any]:
    if not input_path.exists() or not input_path.is_dir():
        raise ValueError("Input non valido: indica una cartella snapshot Thunderbird/MBOX offline")
    if limit_messages is not None and limit_messages <= 0:
        raise ValueError("limit_messages deve essere maggiore di zero")
    if limit_conversations is not None and limit_conversations <= 0:
        raise ValueError("limit_conversations deve essere maggiore di zero")
    for value, option_name in ((date_from, "date_from"), (date_to, "date_to")):
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"{option_name} deve usare il formato ISO YYYY-MM-DD") from exc
    if date_from and date_to and date_from > date_to:
        raise ValueError("date_from non puo essere successiva a date_to")
    source_folders = tuple(folder.strip() for folder in source_folders if folder.strip())
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "logs").mkdir(exist_ok=True)
    db = workspace / "email_atlas.sqlite"
    project = "studio"
    selected = stages or STAGES
    unknown = set(selected) - set(STAGES)
    if unknown:
        raise ValueError(f"Stage non riconosciuti: {', '.join(sorted(unknown))}")
    if rebuild_stage and rebuild_stage not in STAGES:
        raise ValueError(f"Stage rebuild non riconosciuto: {rebuild_stage}")
    required_order = _required_stages(selected)
    required = set(required_order)
    last_required_stage = required_order[-1]
    state_path = workspace / "state.json"
    state = _load_state(state_path, resume)
    current_options = {
        "input_path": str(input_path.resolve()),
        "attachments_text": attachments_text,
        "max_attachment_mb": max_attachment_mb,
        "sample_size": sample_size,
        "limit_messages": limit_messages,
        "limit_conversations": limit_conversations,
        "date_from": date_from,
        "date_to": date_to,
        "source_folders": list(source_folders),
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
    }
    previous_options = state.get("options") or {}
    if previous_options:
        if any(
            previous_options.get(key) != current_options.get(key)
            for key in ("input_path", "sample_size")
        ):
            _invalidate_stages(
                state,
                "import_mbox",
                "input o opzioni di studio cambiate: rieseguo import e stage dipendenti",
            )
        elif previous_options.get("limit_conversations") != current_options.get(
            "limit_conversations"
        ):
            _invalidate_stages(
                state,
                "build_conversations",
                "limite conversazioni cambiato: rieseguo export e stage dipendenti",
            )
        elif previous_options.get("limit_messages") != current_options.get("limit_messages"):
            _invalidate_stages(
                state,
                "build_conversations",
                "limite messaggi cambiato: rieseguo export e stage dipendenti",
            )
        elif any(
            previous_options.get(key) != current_options.get(key)
            for key in ("date_from", "date_to", "source_folders")
        ):
            _invalidate_stages(
                state,
                "build_conversations",
                "filtri data o cartella cambiati: rieseguo export e stage dipendenti",
            )
        elif any(
            previous_options.get(key) != current_options.get(key)
            for key in ("attachments_text", "max_attachment_mb")
        ):
            _invalidate_stages(
                state,
                "extract_attachment_text_optional",
                "configurazione allegati cambiata: rieseguo estrazione testo e stage dipendenti",
            )
        elif any(
            previous_options.get(key) != current_options.get(key)
            for key in ("embedding_provider", "embedding_model")
        ):
            _invalidate_stages(
                state,
                "compute_embeddings_optional",
                "configurazione embedding cambiata: rieseguo gli stage dipendenti",
            )
    if rebuild_stage:
        _invalidate_stages(state, rebuild_stage, f"richiesto rebuild-stage={rebuild_stage}")
    force_run = set(_downstream_stages(rebuild_stage)) if rebuild_stage else set()
    inventory_rows: list[dict[str, Any]] = []
    inventory_count = 0
    accounts: list[str] = []
    pipeline_warnings: list[str] = []
    topic_method = "unavailable"

    def finalize_partial() -> dict[str, Any]:
        now = datetime.now().isoformat()
        state.update(
            {
                "completed_at": now,
                "selected_targets": selected,
                "warnings": pipeline_warnings,
                "options": current_options,
            }
        )
        _write_json(state_path, state)
        return {
            "workspace": str(workspace),
            "database": str(db),
            "conversations": 0,
            "topics": 0,
            "sent": 0,
            "received": 0,
            "warnings": pipeline_warnings,
            "completed_stages": [
                stage for stage in required_order if state["stages"].get(stage) == "completed"
            ],
            "files": sorted(path.name for path in workspace.iterdir() if path.is_file()),
        }

    if not _should_skip_stage("scan_input", state, resume, required, force_run, workspace, db, project):
        candidates = scan_local_folder(input_path)
        inventory_rows = [
            {
                "path": str(item.path),
                "type": item.file_type,
                "size_bytes": item.path.stat().st_size,
                "folder": item.path.parent.name,
            }
            for item in candidates
        ]
        inventory_count = len(inventory_rows)
        _write_csv(
            workspace / "input_inventory.csv",
            inventory_rows,
            ["path", "type", "size_bytes", "folder"],
        )
        if not candidates:
            raise ValueError(
                "Nessun file MBOX/EML trovato. I file .msf e gli indici vengono ignorati."
            )
        del candidates
        del inventory_rows
        _set_stage_status(state, "scan_input", "completed")
    else:
        inventory_count = _count_csv_rows(workspace / "input_inventory.csv")
        _set_stage_status(state, "scan_input", "completed", skipped_via_resume=True)

    if required == {"scan_input"}:
        return finalize_partial()

    config = _workspace_config(workspace, attachments_text, max_attachment_mb)
    import_config = _workspace_config(
        workspace,
        attachments_text,
        max_attachment_mb,
        extract_text=False,
        filename="logs/study_import_config.yaml",
    )

    if not _should_skip_stage("import_mbox", state, resume, required, force_run, workspace, db, project):
        try:
            init_db(db)
            with connect(db) as con:
                ensure_project(con, project)
            health = doctor_workspace(db, project)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
            raise WorkspaceIntegrityError(
                "Workspace non inizializzabile. Esegui doctor-workspace o scegli una cartella nuova."
            ) from exc
        if not health["ok"]:
            raise WorkspaceIntegrityError(f"Workspace incoerente. {health['next_step']}")
        from email_cluster.cli.app import import_emails

        import_emails(
            source=input_path,
            project=project,
            db=db,
            config=import_config,
            sample_size=sample_size,
        )
        _set_stage_status(state, "import_mbox", "completed")
    else:
        _set_stage_status(state, "import_mbox", "completed", skipped_via_resume=True)

    if not _should_skip_stage("parse_messages", state, resume, required, force_run, workspace, db, project):
        parse_and_clean(db, project, config, workspace / "reports")
        _set_stage_status(state, "parse_messages", "completed")
    else:
        _set_stage_status(state, "parse_messages", "completed", skipped_via_resume=True)

    if not _should_skip_stage("detect_sent_received", state, resume, required, force_run, workspace, db, project):
        accounts = _infer_accounts(db, project)
        state["accounts_detected"] = accounts
        _set_stage_status(state, "detect_sent_received", "completed")
    else:
        accounts = list(state.get("accounts_detected") or [])
        if not accounts:
            accounts = _infer_accounts(db, project)
        _set_stage_status(state, "detect_sent_received", "completed", skipped_via_resume=True)

    if not _should_skip_stage("build_conversations", state, resume, required, force_run, workspace, db, project):
        build_conversations(
            db,
            project,
            accounts,
            workspace / "reports",
            mode="rebuild-derived" if rebuild_stage == "build_conversations" else "safe",
        )
        _set_stage_status(state, "build_conversations", "completed")
    else:
        _set_stage_status(state, "build_conversations", "completed", skipped_via_resume=True)

    if not _should_skip_stage("extract_attachments_metadata", state, resume, required, force_run, workspace, db, project):
        _set_stage_status(state, "extract_attachments_metadata", "completed")
    else:
        _set_stage_status(
            state,
            "extract_attachments_metadata",
            "completed",
            skipped_via_resume=True,
        )

    if not _should_skip_stage("extract_attachment_text_optional", state, resume, required, force_run, workspace, db, project):
        if attachments_text:
            _extract_attachment_texts(input_path, db, project, max_attachment_mb)
        else:
            _clear_attachment_text(db, project)
        _set_stage_status(state, "extract_attachment_text_optional", "completed")
    else:
        _set_stage_status(
            state,
            "extract_attachment_text_optional",
            "completed",
            skipped_via_resume=True,
        )

    if not _should_skip_stage("build_semantic_text", state, resume, required, force_run, workspace, db, project):
        build_index(db, project)
        extract_entities(db, project, reports=workspace / "reports")
        build_semantic_docs(db, project)
        _set_stage_status(state, "build_semantic_text", "completed")
    else:
        _set_stage_status(state, "build_semantic_text", "completed", skipped_via_resume=True)
    if last_required_stage == "build_semantic_text":
        return finalize_partial()

    pipeline_warnings: list[str] = []
    if "compute_embeddings_optional" in required:
        if embedding_provider.lower() not in {"", "none", "disabled"}:
            if embedding_provider.lower() not in {"local", "sentence-transformers"}:
                pipeline_warnings.append(
                    f"Provider embedding {embedding_provider} non supportato: uso fallback testuale."
                )
            else:
                model = embedding_model or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                try:
                    embed_documents(db, project, model, batch_size=16, low_power=False)
                except (ImportError, RuntimeError, OSError) as exc:
                    pipeline_warnings.append(
                        f"Embedding non disponibili: {exc}. Uso fallback testuale."
                    )
        _set_stage_status(state, "compute_embeddings_optional", "completed")
    if last_required_stage == "compute_embeddings_optional":
        return finalize_partial()
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        if not con.execute(
            "SELECT 1 FROM atlas_candidate_categories WHERE project_id=?", (pid,)
        ).fetchone():
            heuristic_discovery(
                db, project, min_conversations=2, max_categories=40, reports=workspace / "reports"
            )
        rows = _conversation_rows(
            con,
            pid,
            limit=limit_conversations,
            date_from=date_from,
            date_to=date_to,
            source_folders=source_folders,
        )
        # `_conversation_rows()` already returns conversations ordered by id, so keep
        # that order without building an extra sorted list.
        selected_conversation_ids = array("I", (int(row["id"]) for row in rows))
        message_fields = [
            "conversation_id",
            "message_id",
            "sent_at",
            "sender",
            "recipients",
            "subject",
            "position",
            "relation_method",
        ]
        conversation_message_fields = [
            "conversation_id",
            "message_id",
            "position",
            "relation_method",
        ]

        def _csv_row(row: Any, fields: list[str]) -> dict[str, Any]:
            return {
                key: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (list, dict))
                else value
                for key in fields
                for value in (row[key],)
            }

        collect_message_ids = limit_messages is not None

        def _write_message_exports(rows_iter: Any) -> array | None:
            selected_ids = array("I") if collect_message_ids else None
            with (workspace / "messages.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as messages_handle, (workspace / "conversation_messages.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as conversation_handle:
                messages_writer = csv.DictWriter(
                    messages_handle, fieldnames=message_fields, extrasaction="ignore"
                )
                conversation_writer = csv.DictWriter(
                    conversation_handle,
                    fieldnames=conversation_message_fields,
                    extrasaction="ignore",
                )
                messages_writer.writeheader()
                conversation_writer.writeheader()
                for item in rows_iter:
                    row = dict(item)
                    if selected_ids is not None:
                        selected_ids.append(int(row["message_id"]))
                    messages_writer.writerow(_csv_row(row, message_fields))
                    conversation_writer.writerow(_csv_row(row, conversation_message_fields))
            return selected_ids

        selected_message_ids: array | None
        if selected_conversation_ids:
            conversation_clause = _sql_in_clause(selected_conversation_ids)
            message_query = (
                "SELECT cm.conversation_id,e.id message_id,e.sent_at,e.sender,e.recipients,e.subject,"
                "cm.position,cm.relation_method "
                "FROM atlas_conversation_messages cm "
                "JOIN atlas_conversations c ON c.id=cm.conversation_id "
                "JOIN emails e ON e.id=cm.email_id "
                f"WHERE c.project_id=? AND cm.conversation_id IN ({conversation_clause}) "
                "ORDER BY cm.conversation_id,cm.position"
            )
            message_params: list[int] = [pid, *selected_conversation_ids]
            if limit_messages is not None:
                message_query += " LIMIT ?"
                message_params.append(limit_messages)
            selected_message_ids = _write_message_exports(
                con.execute(message_query, tuple(message_params))
            )
        else:
            selected_message_ids = _write_message_exports(iter(()))
        attachment_text_handle = None
        attachment_text_writer = None
        if attachments_text:
            attachment_text_handle = (workspace / "attachment_texts.csv").open(
                "w", encoding="utf-8-sig", newline=""
            )
            attachment_text_writer = csv.DictWriter(
                attachment_text_handle,
                fieldnames=[
                    "conversation_id",
                    "email_id",
                    "filename",
                    "extraction_status",
                    "attachment_text_excerpt",
                ],
                extrasaction="ignore",
            )
            attachment_text_writer.writeheader()
        attachment_contexts_by_conversation: dict[int, str] = {}
        attachment_count = 0
        attachment_analyzed = 0
        attachment_status = Counter()
        # Stream the attachment export so the full attachment row set does not stay resident.
        attachment_query = None
        attachment_params: list[int] = []
        if selected_conversation_ids:
            conversation_clause = _sql_in_clause(selected_conversation_ids)
            attachment_query = (
                "SELECT cm.conversation_id,a.email_id,a.filename,a.mime_type,a.size_bytes,"
                "a.attachment_type,a.extraction_status,"
                "a.attachment_keywords_json attachment_keywords,"
                "a.text_excerpt attachment_text_excerpt,"
                "case when a.extracted_text is not null and a.extracted_text!='' then 1 else 0 end "
                "attachment_text_available "
                "FROM attachments a "
                "JOIN atlas_conversation_messages cm ON cm.email_id=a.email_id "
                "JOIN atlas_conversations c ON c.id=cm.conversation_id "
                f"WHERE c.project_id=? AND cm.conversation_id IN ({conversation_clause}) "
            )
            attachment_params = [pid, *selected_conversation_ids]
            if selected_message_ids is not None:
                message_clause = _sql_in_clause(selected_message_ids)
                attachment_query += f" AND a.email_id IN ({message_clause})"
                attachment_params.extend(selected_message_ids)

        def iter_attachment_rows():
            nonlocal attachment_count, attachment_analyzed, selected_message_ids
            nonlocal attachment_contexts_by_conversation
            nonlocal attachment_text_writer
            if not attachment_query:
                return
            for attachment in con.execute(
                attachment_query,
                tuple(attachment_params),
            ):
                row = dict(attachment)
                conversation_id = int(row["conversation_id"])
                attachment_context = attachment_contexts_by_conversation.get(conversation_id, "")
                snippet = (
                    f"{row['filename'] or ''}: {row['attachment_keywords'] or ''} "
                    f"{row['attachment_text_excerpt'] or ''}"
                )
                attachment_contexts_by_conversation[conversation_id] = (
                    f"{attachment_context}\n{snippet}" if attachment_context else snippet
                )[:3000]
                attachment_count += 1
                attachment_analyzed += int(row["attachment_text_available"] or 0)
                attachment_status.update([row["extraction_status"] or "unknown"])
                if attachment_text_writer is not None:
                    attachment_text_writer.writerow(
                        {
                            "conversation_id": row["conversation_id"],
                            "email_id": row["email_id"],
                            "filename": row["filename"],
                            "extraction_status": row["extraction_status"],
                            "attachment_text_excerpt": row["attachment_text_excerpt"],
                        }
                    )
                yield row

        try:
            _write_csv(
                workspace / "attachments.csv",
                iter_attachment_rows(),
                [
                    "conversation_id",
                    "email_id",
                    "filename",
                    "mime_type",
                    "size_bytes",
                    "attachment_type",
                    "extraction_status",
                    "attachment_text_available",
                    "attachment_keywords",
                    "attachment_text_excerpt",
                ],
            )
        finally:
            if attachment_text_handle is not None:
                attachment_text_handle.close()
        if not attachments_text:
            attachment_texts = workspace / "attachment_texts.csv"
            if attachment_texts.exists():
                attachment_texts.unlink()
        del selected_conversation_ids
        del selected_message_ids
        # Stream the entity export directly so large vocabularies do not stay resident.
        entity_rows = con.execute(
            "SELECT display_name entity,entity_type,frequency,confidence FROM atlas_entities WHERE project_id=? ORDER BY frequency DESC",
            (pid,),
        )
    topics, topic_ids, topic_method = _topic_discovery(rows)
    topics_by_id = {topic["topic_id"]: topic for topic in topics}
    if "topic_discovery" in required:
        _set_stage_status(state, "topic_discovery", "completed")
    conversation_years: Counter[str] = Counter()
    conversation_domains: Counter[str] = Counter()
    conversation_subjects: Counter[str] = Counter()
    conversation_scopes: Counter[str] = Counter()
    noise_count = 0
    personal_count = 0
    mixed_count = 0
    sent_count = 0
    received_count = 0
    conversation_total = 0
    with (
        (workspace / "conversations.csv").open("w", encoding="utf-8-sig", newline="") as conversations_handle,
        (workspace / "conversations_enriched.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as conversations_enriched_handle,
    ):
        conversations_writer = csv.DictWriter(
            conversations_handle, fieldnames=CONVERSATION_FIELDS, extrasaction="ignore"
        )
        conversations_enriched_writer = csv.DictWriter(
            conversations_enriched_handle,
            fieldnames=CONVERSATION_FIELDS + ["topic_id"],
            extrasaction="ignore",
        )
        conversations_writer.writeheader()
        conversations_enriched_writer.writeheader()
        for row, topic_id in zip(rows, topic_ids):
            conversation_id = int(row["id"])
            topic = topics_by_id.get(topic_id, {})
            attachment_context = attachment_contexts_by_conversation.pop(conversation_id, "")
            semantic_text = (row.get("semantic_text") or row.get("analysis_text") or "")[:7000]
            if attachment_context:
                semantic_text += "\n\nAllegati (estratti):\n" + attachment_context
            conversation_record = {
                "conversation_id": conversation_id,
                "date_start": row["date_start"],
                "date_end": row["date_end"],
                "year": row["year"],
                "month": row["month"],
                "subject_normalized": row["subject_normalized"],
                "message_count": row["message_count"],
                "incoming_count": row["incoming_count"],
                "outgoing_count": row["outgoing_count"],
                "is_mixed_incoming_outgoing": int(
                    row["incoming_count"] > 0 and row["outgoing_count"] > 0
                ),
                "participants": row["participants"],
                "sender_domains": row["domains"],
                "main_domain": row["domains"][0] if row["domains"] else "",
                "has_attachments": int(row["attachments_count"] > 0),
                "attachment_count": row["attachments_count"],
                "attachment_types": sorted(
                    {Path(name).suffix.lower() for name in row["attachments"]}
                ),
                "clean_summary": (row.get("unique_clean_text") or "")[:600],
                "semantic_text": semantic_text[:10000],
                "probable_scope": row["probable_scope"],
                "scope_confidence": row.get("scope_confidence", ""),
                "scope_reason": row.get("scope_reason", ""),
                "probable_actor": row["entities"][0] if row["entities"] else "",
                "probable_theme": topic.get("label", ""),
                "probable_project": "",
                "probable_activity": topic.get("label", ""),
                "confidence": row["confidence"],
                "warnings": row["warnings"],
            }
            conversation_row = _csv_row(conversation_record, CONVERSATION_FIELDS)
            conversations_writer.writerow(conversation_row)
            conversations_enriched_writer.writerow(
                {**conversation_row, "topic_id": topic_id if topic_id is not None else ""}
            )
            conversation_total += 1
            conversation_years.update([row["year"] or "Senza data"])
            conversation_domains.update(row["domains"])
            conversation_subjects.update([row["subject_normalized"] or "Senza oggetto"])
            conversation_scopes.update([row["probable_scope"] or "Non definito"])
            lowered_semantic = semantic_text.lower()
            if any(term in lowered_semantic for term in ("unsubscribe", "newsletter", "promozione")):
                noise_count += 1
            if any(
                term in lowered_semantic for term in ("cena", "vacanza", "famiglia", "compleanno")
            ):
                personal_count += 1
            mixed_count += int(row["incoming_count"] > 0 and row["outgoing_count"] > 0)
            sent_count += int(row["outgoing_count"])
            received_count += int(row["incoming_count"])
            # Keep only the fields still needed for term and graph generation.
            for field in (
                "participants",
                "warnings",
                "unique_clean_text",
                "attachments",
                "date_start",
                "date_end",
                "year",
                "month",
                "incoming_count",
                "outgoing_count",
                "is_mixed_incoming_outgoing",
                "has_attachments",
                "attachment_count",
                "attachment_types",
                "scope_confidence",
                "scope_reason",
                "probable_actor",
                "probable_theme",
                "probable_project",
                "probable_activity",
                "confidence",
            ):
                row.pop(field, None)
    del topics_by_id
    del topic_ids
    del attachment_contexts_by_conversation
    report_counts = {
        "years": conversation_years,
        "domains": conversation_domains,
        "subjects": conversation_subjects,
        "scopes": conversation_scopes,
        "noise": noise_count,
        "personal": personal_count,
    }
    _write_csv(
        workspace / "topics.csv",
        topics,
        [
            "topic_id",
            "label",
            "label_reason",
            "conversation_count",
            "main_terms",
            "main_domains",
            "main_attachments",
            "warnings",
            "representative_conversations",
            "borderline_conversations",
            "outlier_conversations",
            "method",
        ],
    )
    _write_csv(
        workspace / "clusters.csv",
        topics,
        ["topic_id", "label", "conversation_count", "main_terms"],
    )
    _write_csv(
        workspace / "entities.csv",
        entity_rows,
        ["entity", "entity_type", "frequency", "confidence"],
    )
    del entity_rows
    if last_required_stage == "topic_discovery":
        return finalize_partial()
    term_rows = _terms(rows)
    # Term extraction has finished, so drop the large text payload before the remaining exports.
    for row in rows:
        row.pop("semantic_text", None)
        row.pop("analysis_text", None)
    if "build_classification_workspace" in required:
        _set_stage_status(state, "build_classification_workspace", "completed")
    graph_edges, graph_nodes = _edges_and_nodes(rows, term_rows)
    _write_csv(
        workspace / "nodes.csv",
        graph_nodes,
        ["node_id", "label", "node_type", "size", "group", "frequency", "description"],
    )
    _write_csv(
        workspace / "edges.csv",
        graph_edges,
        ["source", "target", "edge_type", "weight", "example", "source_type", "target_type"],
    )
    del term_rows
    del graph_edges
    del graph_nodes
    del rows
    with (workspace / "classification_workspace.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as classification_handle:
        classification_writer = csv.DictWriter(
            classification_handle, fieldnames=CLASSIFICATION_FIELDS, extrasaction="ignore"
        )
        classification_writer.writeheader()
        for topic in topics:
            ids = topic["representative_conversations"]
            scope_summary = topic.get("scope_summary") or {}
            proposed_scope = str(scope_summary.get("scope") or "Da definire")
            scope_confidence = float(scope_summary.get("confidence") or 0.0)
            scope_reason = str(scope_summary.get("reason") or "Scope non determinabile.")
            suggestions = _classification_suggestion(topic)
            classification_writer.writerow(
                _csv_row(
                    {
                        "candidate_id": topic["topic_id"],
                        "proposed_name": topic["label"],
                        "proposed_scope": suggestions["proposed_scope"],
                        "proposed_activity": suggestions["proposed_activity"],
                        "proposed_project_context": "",
                        "proposed_actor": "",
                        "proposed_theme": suggestions["proposed_theme"],
                        "description": suggestions["description"],
                        "why_it_exists": (
                            f"Categoria proposta: {topic['label']}. {topic['label_reason']} "
                            f"Termini ricorrenti: {', '.join(topic['main_terms'][:8])}. "
                            f"Scope preliminare: {proposed_scope}. {scope_reason}"
                        ),
                        "conversation_count": topic["conversation_count"],
                        "representative_conversations": ids,
                        "borderline_conversations": topic.get("borderline_conversations", []),
                        "outlier_conversations": topic.get("outlier_conversations", []),
                        "main_terms": topic["main_terms"],
                        "main_domains": topic.get("main_domains", []),
                        "main_attachments": topic.get("main_attachments", []),
                        "similar_candidates": [],
                        "possible_merge_with": [],
                        "possible_exclusions": [],
                        "confidence": max(
                            scope_confidence,
                            0.7 if topic["conversation_count"] >= 3 else 0.45,
                        ),
                        "suggested_decision": suggestions["suggested_decision"],
                        "human_decision": "",
                        "final_name": "",
                        "final_scope": "",
                        "final_activity": "",
                        "final_theme": "",
                        "final_description": "",
                        "notes": suggestions["notes"],
                    },
                    CLASSIFICATION_FIELDS,
                )
            )
            topic.pop("scope_summary", None)
            topic.pop("example_subjects", None)
    if last_required_stage == "build_classification_workspace":
        del topics
        return finalize_partial()
    for topic in topics:
        for field in list(topic):
            if field not in {"conversation_count", "label", "warnings"}:
                topic.pop(field, None)
    mixed = mixed_count
    sent = sent_count
    received = received_count
    warnings = list(pipeline_warnings)
    if not accounts or sent == 0:
        warnings.append("Risultato fragile: la posta inviata sembra assente o non riconosciuta.")
    if not attachments_text:
        warnings.append("Testo allegati non analizzato; sono disponibili solo i metadati.")
    if sample_size is not None:
        warnings.append(
            f"Campione limitato a {sample_size} messaggi importati: risultati utili per prova rapida, non per analisi completa."
        )
    if limit_messages is not None:
        warnings.append(
            f"Export workspace limitato ai primi {limit_messages} messaggi: conversazioni e topic restano calcolati sul dataset selezionato, ma il dettaglio messaggi/allegati e ridotto per prove rapide."
        )
    if limit_conversations is not None:
        warnings.append(
            f"Analisi limitata alle prime {limit_conversations} conversazioni ricostruite: utile per prove rapide e tuning locale."
        )
    topic_total = len(topics)
    report = _study_report(
        workspace,
        inventory_count,
        conversation_total,
        topics,
        attachment_count,
        attachment_status,
        attachment_analyzed,
        attachments_text,
        received,
        sent,
        mixed,
        warnings,
        topic_method,
        report_counts,
    )
    (workspace / "study_report.html").write_text(report, encoding="utf-8")
    del topics
    now = datetime.now().isoformat()
    state.update(
        {
            "completed_at": now,
            "selected_targets": selected,
            "warnings": warnings,
            "options": current_options,
        }
    )
    _set_stage_status(state, "generate_report", "completed")
    _write_json(state_path, state)
    manifest = {
        "version": 1,
        "project": project,
        "input_snapshot": str(input_path.resolve()),
        "database": str(db),
        "local_only": True,
        "accounts_detected": accounts,
        "attachment_text_enabled": attachments_text,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "topic_method": topic_method,
        "sample_size": sample_size,
        "limit_messages": limit_messages,
        "limit_conversations": limit_conversations,
        "date_from": date_from,
        "date_to": date_to,
        "source_folders": list(source_folders),
        "files": sorted(path.name for path in workspace.iterdir() if path.is_file()),
    }
    _write_json(workspace / "workspace.json", manifest)
    (workspace / "logs" / "study.log").write_text(f"{now} study completed\n", encoding="utf-8")
    return {
        "workspace": str(workspace),
        "database": str(db),
        "conversations": conversation_total,
        "topics": topic_total,
        "sent": sent,
        "received": received,
        "warnings": warnings,
        "completed_stages": [stage for stage in required_order if state["stages"].get(stage) == "completed"],
        "files": manifest["files"],
    }


def _study_report(
    workspace,
    inventory_count,
    conversation_total,
    topics,
    attachment_count,
    attachment_status,
    attachment_analyzed,
    attachments_text_enabled,
    received,
    sent,
    mixed,
    warnings,
    method,
    report_counts,
):
    def esc(value: Any) -> str:
        return html.escape(str(value))

    def label_method(raw: str) -> str:
        labels = {
            "bertopic": "BERTopic locale",
            "tfidf_svd_kmeans": "TF-IDF + SVD + KMeans",
            "unavailable": "Metodo non disponibile",
        }
        return labels.get(raw, raw)

    links = "".join(
        f"<li><a href='{name}'>{name}</a></li>"
        for name in (
            "input_inventory.csv",
            "messages.csv",
            "conversations.csv",
            "attachments.csv",
            "topics.csv",
            "classification_workspace.csv",
            "edges.csv",
            "entities.csv",
        )
    )
    warning_html = (
        "".join(f"<li>{esc(warning)}</li>" for warning in warnings)
        or "<li>Nessun warning bloccante.</li>"
    )
    topic_html = "".join(
        "<tr>"
        f"<td>{esc(topic['label'])}</td>"
        f"<td>{topic['conversation_count']}</td>"
        f"<td>{esc(', '.join(topic.get('warnings') or []) or 'nessuno')}</td>"
        "</tr>"
        for topic in topics[:15]
    ) or "<tr><td colspan='3'>Nessun topic disponibile.</td></tr>"
    attachment_status_html = "".join(
        f"<tr><td>{esc(status)}</td><td>{count}</td></tr>"
        for status, count in attachment_status.most_common()
    ) or "<tr><td colspan='2'>Nessun allegato censito.</td></tr>"
    years = report_counts["years"]
    domains = report_counts["domains"]
    subjects = report_counts["subjects"]
    scopes = report_counts["scopes"]
    noise = report_counts["noise"]
    personal = report_counts["personal"]

    def ranking(values):
        return "".join(f"<tr><td>{esc(key)}</td><td>{value}</td></tr>" for key, value in values)

    topic_method = label_method(method)
    topic_method_note = (
        "Metodo attivo per i topic: BERTopic locale. Se non disponibile, la pipeline torna al fallback deterministico TF-IDF + SVD + KMeans."
        if method == "bertopic"
        else "Metodo topic in fallback deterministico: TF-IDF + SVD + KMeans. BERTopic resta opzionale e non richiesto per usare il workspace."
    )
    attachment_mode = (
        "Estrazione testo allegati attiva: oltre ai metadati, il report conta anche gli allegati con testo disponibile."
        if attachments_text_enabled
        else "Estrazione testo allegati disattivata: il workspace conserva solo metadati e keyword finche non rilanci con --with-attachments-text."
    )

    return f"""<!doctype html><meta charset='utf-8'><title>Email Atlas Study</title><style>body{{font:15px system-ui;max-width:1100px;margin:30px auto}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.card,section{{border:1px solid #ccd5d8;padding:14px;margin:12px 0}}strong{{font-size:24px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:6px;border-bottom:1px solid #ddd;text-align:left}}ul{{padding-left:20px}}</style><h1>Studio archivio email storico</h1><p>Report locale autosufficiente per leggere stato pipeline, limiti e file da revisionare senza GUI.</p><div class='grid'><div class='card'><strong>{received + sent}</strong><br>Email</div><div class='card'><strong>{conversation_total}</strong><br>Conversazioni</div><div class='card'><strong>{sent}</strong><br>Inviate</div><div class='card'><strong>{received}</strong><br>Ricevute</div><div class='card'><strong>{mixed}</strong><br>Conversazioni miste</div><div class='card'><strong>{attachment_count}</strong><br>Allegati censiti</div><div class='card'><strong>{attachment_analyzed}</strong><br>Allegati con testo</div><div class='card'><strong>{len(topics)}</strong><br>Topic candidati</div></div><section><h2>Qualita stimata e warning</h2><ul>{warning_html}</ul><p>Tutto elaborato localmente dentro il workspace: nessun dato email esce dal computer.</p></section><section><h2>Input analizzati</h2><p>{inventory_count} file MBOX/EML.</p></section><section><h2>Stato allegati</h2><p>{esc(attachment_mode)}</p><table><thead><tr><th>Stato</th><th>Conteggio</th></tr></thead><tbody>{attachment_status_html}</tbody></table></section><section><h2>Metodo topic</h2><p><strong>{esc(topic_method)}</strong></p><p>{esc(topic_method_note)}</p></section><section><h2>Limiti e fallback dichiarati</h2><ul><li>Le categorie sono proposte revisionabili, non decisioni definitive.</li><li>Il fallback topic basato su TF-IDF + SVD + KMeans resta valido e dichiarato nel report.</li><li>Se il testo allegati non e attivo, il workspace resta utile ma legge solo metadati e keyword degli allegati.</li></ul></section><section><h2>Distribuzione temporale</h2><table>{ranking(years.most_common())}</table></section><section><h2>Domini principali</h2><table>{ranking(domains.most_common(30))}</table></section><section><h2>Soggetti principali</h2><table>{ranking(subjects.most_common(30))}</table></section><section><h2>Ambiti provvisori</h2><table>{ranking(scopes.most_common())}</table><p>Rumore/newsletter probabile: {noise}. Personale probabile: {personal}.</p></section><section><h2>Topic principali</h2><table><thead><tr><th>Categoria candidata</th><th>Conversazioni</th><th>Warning</th></tr></thead><tbody>{topic_html}</tbody></table></section><section><h2>Prossimi passi</h2><p>Apri classification_workspace.csv, verifica esempi rappresentativi, borderline e outlier, poi compila human_decision.</p></section><section><h2>Dataset</h2><ul>{links}</ul></section>"""


def _minimal_xlsx(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ["name", "scope", "theme", "description"]
    values = [fields] + [[str(row.get(field, "")) for field in fields] for row in rows]
    sheet_rows = []
    for row_number, row in enumerate(values, 1):
        cells = []
        for column, value in enumerate(row):
            escaped = str(value).replace("&", "&amp;").replace("<", "&lt;")
            cells.append(
                f'<c r="{chr(65 + column)}{row_number}" t="inlineStr"><is><t>{escaped}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        )
        book.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        )
        book.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Atlante finale" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        book.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        book.writestr(
            "xl/worksheets/sheet1.xml",
            f'<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>',
        )


def build_atlas_from_workspace(workspace: Path) -> dict[str, Any]:
    manifest = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))
    db = Path(manifest["database"])
    source = workspace / "classification_workspace.csv"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0]) if rows else CLASSIFICATION_FIELDS
    allowed_decisions = {"", "approve", "rename", "merge", "exclude", "unclear", "split_later"}
    for row in rows:
        decision = row.get("human_decision", "").strip().lower()
        if decision not in allowed_decisions:
            raise ValueError(f"Decisione non supportata: {decision}")
        if decision in {"rename", "merge"} and not row.get("final_name"):
            raise ValueError(f"Decisione {decision} senza final_name")
        if decision in {"approve", "rename", "merge"}:
            row["human_decision"] = "approve"
    normalized = workspace / ".classification_import.csv"
    with normalized.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    # The workspace candidate_id is the exported topic identifier and is not
    # guaranteed to be the database candidate primary key.
    result = import_classification(
        db,
        manifest["project"],
        normalized,
        workspace,
        validate_candidate_ids=False,
    )
    normalized.unlink(missing_ok=True)
    try:
        from openpyxl import Workbook

        data = json.loads((workspace / "atlas_final.json").read_text(encoding="utf-8"))
        book = Workbook()
        sheet = book.active
        sheet.title = "Atlante finale"
        fields = list(data[0]) if data else ["name", "scope", "theme", "description"]
        sheet.append(fields)
        for row in data:
            sheet.append([row.get(field) for field in fields])
        book.save(workspace / "atlas_final.xlsx")
        result["files"].append("atlas_final.xlsx")
    except ImportError:
        data = json.loads((workspace / "atlas_final.json").read_text(encoding="utf-8"))
        _minimal_xlsx(workspace / "atlas_final.xlsx", data)
        result["files"].append("atlas_final.xlsx")
    return result


def export_orange_workspace(workspace: Path) -> dict[str, Any]:
    manifest = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))
    result = export_orange(Path(manifest["database"]), manifest["project"], workspace / "orange")
    (workspace / "orange" / "orange_topics.csv").write_bytes(
        (workspace / "topics.csv").read_bytes()
    )
    readme = workspace / "orange" / "orange_readme.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n## Colonne\nFeature: x, y, conteggi, confidence. Meta: semantic_text_short, termini, domini, warning. Target/color: probable_scope o cluster_label. Label: subject_normalized. Size: message_count.\n",
        encoding="utf-8",
    )
    (workspace / "orange" / "orange_workflow_suggestions.md").write_text(
        """# Workflow Orange suggeriti

## Workflow 1 - Mappa conversazioni
File -> Select Columns -> Scatter Plot -> Data Table
Feature: x, y, confidence, message_count. Meta: semantic_text_short, domini, warning. Color: probable_scope o cluster_label. Size: message_count. Label: subject_normalized.

## Workflow 2 - Topic testuali
Corpus -> Preprocess Text -> Topic Modelling -> LDAvis -> Data Table
Testo: semantic_text_short. Meta: conversation_id, subject_normalized, main_domain.

## Workflow 3 - Document Map
Corpus -> Preprocess Text -> Document Embedding -> Document Map
Color: probable_scope o cluster_label. Label: subject_normalized.

## Workflow 4 - Reti
File nodes/edges -> Network Explorer
Node label: label. Node size: size/frequency. Group/color: group. Edge weight: weight.
""",
        encoding="utf-8",
    )
    return result
