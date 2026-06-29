from __future__ import annotations

import csv
import json
import math
import zipfile
from collections import Counter
from datetime import datetime
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
    _conversation_rows,
    _write_csv,
    export_orange,
    export_study_pack,
    import_classification,
)
from email_cluster.ingestion.scanner import scan_local_folder
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository

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


def _topic_discovery(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, int], str]:
    if not rows:
        return [], {}, "unavailable"
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
    assignments = {int(row["id"]): int(label) for row, label in zip(rows, labels)}
    topics = []
    for label in sorted(set(labels)):
        members = [row for row, item_label in zip(rows, labels) if item_label == label]
        corpus = " ".join(row.get("subject_normalized") or "" for row in members).lower().split()
        terms = [
            term
            for term, _ in Counter(
                word.strip(".,:;()[]") for word in corpus if len(word) > 3
            ).most_common(12)
        ]
        topics.append(
            {
                "topic_id": int(label),
                "label": " / ".join(terms[:3]) or f"Topic {label}",
                "conversation_count": len(members),
                "main_terms": terms,
                "representative_conversations": [row["id"] for row in members[:8]],
                "method": method,
            }
        )
    return topics, assignments, method


def _workspace_config(workspace: Path, with_text: bool, max_mb: int) -> Path:
    source = Path("config/default.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8")) if source.exists() else {}
    data.setdefault("attachments", {}).update(
        {"enabled": True, "extract_text": with_text, "max_file_size_mb": max_mb}
    )
    path = workspace / "study_config.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


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
    embedding_provider: str = "none",
    embedding_model: str = "",
) -> dict[str, Any]:
    if not input_path.exists() or not input_path.is_dir():
        raise ValueError("Input non valido: indica una cartella snapshot Thunderbird/MBOX offline")
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "logs").mkdir(exist_ok=True)
    db = workspace / "email_atlas.sqlite"
    project = "studio"
    selected = stages or STAGES
    unknown = set(selected) - set(STAGES)
    if unknown:
        raise ValueError(f"Stage non riconosciuti: {', '.join(sorted(unknown))}")
    state_path = workspace / "state.json"
    state = (
        json.loads(state_path.read_text(encoding="utf-8"))
        if resume and state_path.exists()
        else {"stages": {}}
    )
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
    _write_csv(
        workspace / "input_inventory.csv", inventory_rows, ["path", "type", "size_bytes", "folder"]
    )
    if not candidates:
        raise ValueError("Nessun file MBOX/EML trovato. I file .msf e gli indici vengono ignorati.")
    config = _workspace_config(workspace, attachments_text, max_attachment_mb)
    init_db(db)
    from email_cluster.cli.app import import_emails

    import_emails(source=input_path, project=project, db=db, config=config)
    parse_and_clean(db, project, config, workspace / "reports")
    accounts = _infer_accounts(db, project)
    build_conversations(
        db,
        project,
        accounts,
        workspace / "reports",
        mode="rebuild-derived" if rebuild_stage == "build_conversations" else "safe",
    )
    build_index(db, project)
    extract_entities(db, project, reports=workspace / "reports")
    build_semantic_docs(db, project)
    pipeline_warnings: list[str] = []
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
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        if not con.execute(
            "SELECT 1 FROM atlas_candidate_categories WHERE project_id=?", (pid,)
        ).fetchone():
            heuristic_discovery(
                db, project, min_conversations=2, max_categories=40, reports=workspace / "reports"
            )
        rows = _conversation_rows(con, pid)
        message_rows = [
            dict(row)
            for row in con.execute(
                """SELECT cm.conversation_id,e.id message_id,e.sent_at,e.sender,e.recipients,e.subject,cm.position,cm.relation_method FROM atlas_conversation_messages cm JOIN atlas_conversations c ON c.id=cm.conversation_id JOIN emails e ON e.id=cm.email_id WHERE c.project_id=? ORDER BY cm.conversation_id,cm.position""",
                (pid,),
            )
        ]
        attachment_rows = [
            dict(row)
            for row in con.execute(
                """SELECT cm.conversation_id,a.email_id,a.filename,a.mime_type,a.size_bytes,a.attachment_type,a.extraction_status,a.attachment_keywords_json attachment_keywords,a.text_excerpt attachment_text_excerpt,case when a.extracted_text is not null and a.extracted_text!='' then 1 else 0 end attachment_text_available FROM attachments a JOIN atlas_conversation_messages cm ON cm.email_id=a.email_id JOIN atlas_conversations c ON c.id=cm.conversation_id WHERE c.project_id=?""",
                (pid,),
            )
        ]
        entity_rows = [
            dict(row)
            for row in con.execute(
                "SELECT display_name entity,entity_type,frequency,confidence FROM atlas_entities WHERE project_id=? ORDER BY frequency DESC",
                (pid,),
            )
        ]
    topics, assignments, topic_method = _topic_discovery(rows)
    attachments_by_conversation: dict[int, list[dict[str, Any]]] = {}
    for attachment in attachment_rows:
        attachments_by_conversation.setdefault(int(attachment["conversation_id"]), []).append(
            attachment
        )
    enriched = []
    for row in rows:
        topic = next(
            (item for item in topics if item["topic_id"] == assignments.get(row["id"])), {}
        )
        attachment_context = "\n".join(
            f"{item.get('filename') or ''}: {item.get('attachment_keywords') or ''} "
            f"{item.get('attachment_text_excerpt') or ''}"
            for item in attachments_by_conversation.get(int(row["id"]), [])
        )[:3000]
        semantic_text = (row.get("semantic_text") or row.get("analysis_text") or "")[:7000]
        if attachment_context:
            semantic_text += "\n\nAllegati (estratti):\n" + attachment_context
        enriched.append(
            {
                "conversation_id": row["id"],
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
                "probable_actor": row["entities"][0] if row["entities"] else "",
                "probable_theme": topic.get("label", ""),
                "probable_project": "",
                "probable_activity": topic.get("label", ""),
                "topic_id": assignments.get(row["id"], ""),
                "confidence": row["confidence"],
                "warnings": row["warnings"],
            }
        )
    _write_csv(
        workspace / "messages.csv",
        message_rows,
        [
            "conversation_id",
            "message_id",
            "sent_at",
            "sender",
            "recipients",
            "subject",
            "position",
            "relation_method",
        ],
    )
    _write_csv(
        workspace / "conversation_messages.csv",
        message_rows,
        ["conversation_id", "message_id", "position", "relation_method"],
    )
    _write_csv(workspace / "conversations.csv", enriched, CONVERSATION_FIELDS)
    _write_csv(
        workspace / "conversations_enriched.csv", enriched, CONVERSATION_FIELDS + ["topic_id"]
    )
    _write_csv(
        workspace / "attachments.csv",
        attachment_rows,
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
    if attachments_text:
        _write_csv(
            workspace / "attachment_texts.csv",
            attachment_rows,
            [
                "conversation_id",
                "email_id",
                "filename",
                "extraction_status",
                "attachment_text_excerpt",
            ],
        )
    _write_csv(
        workspace / "topics.csv",
        topics,
        [
            "topic_id",
            "label",
            "conversation_count",
            "main_terms",
            "representative_conversations",
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
    export_study_pack(db, project, workspace / "_base_pack")
    for name in ("edges.csv", "nodes.csv"):
        (workspace / name).write_bytes((workspace / "_base_pack" / name).read_bytes())
    classification = []
    for topic in topics:
        ids = topic["representative_conversations"]
        classification.append(
            {
                "candidate_id": topic["topic_id"],
                "proposed_name": topic["label"],
                "proposed_scope": "Da definire",
                "proposed_activity": topic["label"],
                "proposed_project_context": "",
                "proposed_actor": "",
                "proposed_theme": topic["label"],
                "description": f"Topic con {topic['conversation_count']} conversazioni.",
                "why_it_exists": f"Termini ricorrenti: {', '.join(topic['main_terms'][:8])}",
                "conversation_count": topic["conversation_count"],
                "representative_conversations": ids,
                "borderline_conversations": [],
                "outlier_conversations": [],
                "main_terms": topic["main_terms"],
                "main_domains": [],
                "main_attachments": [],
                "similar_candidates": [],
                "possible_merge_with": [],
                "possible_exclusions": [],
                "confidence": 0.7 if topic["conversation_count"] >= 3 else 0.45,
                "suggested_decision": "approve" if topic["conversation_count"] >= 3 else "unclear",
                "human_decision": "",
                "final_name": "",
                "final_scope": "",
                "final_activity": "",
                "final_theme": "",
                "final_description": "",
                "notes": "",
            }
        )
    _write_csv(workspace / "classification_workspace.csv", classification, CLASSIFICATION_FIELDS)
    mixed = sum(item["is_mixed_incoming_outgoing"] for item in enriched)
    sent = sum(item["outgoing_count"] for item in enriched)
    received = sum(item["incoming_count"] for item in enriched)
    warnings = list(pipeline_warnings)
    if not accounts or sent == 0:
        warnings.append("Risultato fragile: la posta inviata sembra assente o non riconosciuta.")
    if not attachments_text:
        warnings.append("Testo allegati non analizzato; sono disponibili solo i metadati.")
    report = _study_report(
        workspace,
        inventory_rows,
        enriched,
        topics,
        attachment_rows,
        received,
        sent,
        mixed,
        warnings,
        topic_method,
    )
    (workspace / "study_report.html").write_text(report, encoding="utf-8")
    now = datetime.now().isoformat()
    state.update(
        {
            "completed_at": now,
            "stages": {stage: "completed" for stage in selected},
            "warnings": warnings,
        }
    )
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
        "files": sorted(path.name for path in workspace.iterdir() if path.is_file()),
    }
    _write_json(workspace / "workspace.json", manifest)
    (workspace / "logs" / "study.log").write_text(f"{now} study completed\n", encoding="utf-8")
    return {
        "workspace": str(workspace),
        "database": str(db),
        "conversations": len(enriched),
        "topics": len(topics),
        "sent": sent,
        "received": received,
        "warnings": warnings,
        "files": manifest["files"],
    }


def _study_report(
    workspace,
    inventory,
    conversations,
    topics,
    attachments,
    received,
    sent,
    mixed,
    warnings,
    method,
):
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
        "".join(f"<li>{warning}</li>" for warning in warnings)
        or "<li>Nessun warning bloccante.</li>"
    )
    topic_html = "".join(
        f"<li>{topic['label']}: {topic['conversation_count']}</li>" for topic in topics[:30]
    )
    analyzed = sum(item.get("attachment_text_available", 0) for item in attachments)
    years = Counter(item.get("year") or "Senza data" for item in conversations)
    domains = Counter(domain for item in conversations for domain in item.get("sender_domains", []))
    subjects = Counter(item.get("subject_normalized") or "Senza oggetto" for item in conversations)
    scopes = Counter(item.get("probable_scope") or "Non definito" for item in conversations)
    noise = sum(
        any(
            term in (item.get("semantic_text") or "").lower()
            for term in ("unsubscribe", "newsletter", "promozione")
        )
        for item in conversations
    )
    personal = sum(
        any(
            term in (item.get("semantic_text") or "").lower()
            for term in ("cena", "vacanza", "famiglia", "compleanno")
        )
        for item in conversations
    )

    def ranking(values):
        return "".join(f"<tr><td>{key}</td><td>{value}</td></tr>" for key, value in values)

    return f"""<!doctype html><meta charset='utf-8'><title>Email Atlas Study</title><style>body{{font:15px system-ui;max-width:1100px;margin:30px auto}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.card,section{{border:1px solid #ccd5d8;padding:14px;margin:12px 0}}strong{{font-size:24px}}table{{width:100%;border-collapse:collapse}}td{{padding:6px;border-bottom:1px solid #ddd}}</style><h1>Studio archivio email storico</h1><div class='grid'><div class='card'><strong>{received + sent}</strong><br>Email</div><div class='card'><strong>{len(conversations)}</strong><br>Conversazioni</div><div class='card'><strong>{sent}</strong><br>Inviate</div><div class='card'><strong>{received}</strong><br>Ricevute</div><div class='card'><strong>{mixed}</strong><br>Conversazioni miste</div><div class='card'><strong>{len(attachments)}</strong><br>Allegati censiti</div><div class='card'><strong>{analyzed}</strong><br>Allegati analizzati</div><div class='card'><strong>{len(topics)}</strong><br>Topic candidati</div></div><section><h2>Qualita stimata e warning</h2><ul>{warning_html}</ul><p>Topic: {method}. Tutto elaborato localmente.</p></section><section><h2>Input analizzati</h2><p>{len(inventory)} file MBOX/EML.</p></section><section><h2>Distribuzione temporale</h2><table>{ranking(years.most_common())}</table></section><section><h2>Domini principali</h2><table>{ranking(domains.most_common(30))}</table></section><section><h2>Soggetti principali</h2><table>{ranking(subjects.most_common(30))}</table></section><section><h2>Ambiti provvisori</h2><table>{ranking(scopes.most_common())}</table><p>Rumore/newsletter probabile: {noise}. Personale probabile: {personal}.</p></section><section><h2>Topic principali</h2><ul>{topic_html}</ul></section><section><h2>Prossimi passi</h2><p>Apri classification_workspace.csv, verifica esempi rappresentativi, borderline e outlier, poi compila human_decision.</p></section><section><h2>Dataset</h2><ul>{links}</ul></section>"""


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
    for row in rows:
        decision = row.get("human_decision", "").strip().lower()
        if decision in {"rename", "merge"} and not row.get("final_name"):
            raise ValueError(f"Decisione {decision} senza final_name")
        if decision in {"approve", "rename", "merge"}:
            row["human_decision"] = "approve"
    normalized = workspace / ".classification_import.csv"
    with normalized.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    result = import_classification(db, manifest["project"], normalized, workspace)
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
