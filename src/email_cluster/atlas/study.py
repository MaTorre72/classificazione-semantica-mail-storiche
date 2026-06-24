from __future__ import annotations

import csv
import html
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from email_cluster.atlas.conversations import build_conversations
from email_cluster.atlas.discovery import heuristic_discovery, scope_for_text
from email_cluster.atlas.entities import extract_entities
from email_cluster.atlas.inventory import inventory
from email_cluster.atlas.parsing import parse_and_clean
from email_cluster.atlas.search import build_index
from email_cluster.atlas.semantic_docs import build_semantic_docs
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository
from email_cluster.storage.repository import blob_to_embedding


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )


def _loads(value: str | None) -> list[Any]:
    try:
        result = json.loads(value or "[]")
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


def _conversation_rows(con, project_id: int) -> list[dict[str, Any]]:
    rows = []
    for row in con.execute(
        """SELECT c.*,d.content semantic_text,d.metadata_json,
                  group_concat(DISTINCT ae.display_name) entity_names,
                  group_concat(DISTINCT ae.entity_type || ':' || ae.display_name) typed_entities,
                  group_concat(DISTINCT a.filename) attachment_names
           FROM atlas_conversations c
           LEFT JOIN atlas_semantic_documents d ON d.project_id=c.project_id
                AND d.document_level='conversation' AND d.source_id=c.id
           LEFT JOIN atlas_conversation_messages cm ON cm.conversation_id=c.id
           LEFT JOIN atlas_entity_mentions em ON em.email_id=cm.email_id
           LEFT JOIN atlas_entities ae ON ae.id=em.entity_id
           LEFT JOIN attachments a ON a.email_id=cm.email_id
           WHERE c.project_id=? GROUP BY c.id ORDER BY c.id""",
        (project_id,),
    ):
        item = dict(row)
        item["participants"] = _loads(item.pop("participants_json", "[]"))
        item["warnings"] = _loads(item.pop("warnings_json", "[]"))
        item["entities"] = [x for x in (item.get("entity_names") or "").split(",") if x]
        item["attachments"] = [x for x in (item.get("attachment_names") or "").split(",") if x]
        item["domains"] = sorted(
            {
                match.lower()
                for value in item["participants"]
                for match in re.findall(r"@([\w.-]+)", value)
            }
        )
        item["year"] = (item.get("date_start") or "")[:4]
        item["month"] = (item.get("date_start") or "")[5:7]
        item["probable_scope"] = scope_for_text(
            item.get("semantic_text") or item.get("analysis_text") or ""
        )
        rows.append(item)
    return rows


def _semantic_points(con, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    vectors: list[np.ndarray] = []
    source_ids: list[int] = []
    try:
        cached = list(
            con.execute(
                """SELECT d.source_id,e.embedding FROM atlas_embedding_cache e
                   JOIN atlas_semantic_documents d ON d.id=e.semantic_document_id
                   WHERE d.document_level='conversation' ORDER BY d.source_id"""
            )
        )
        for item in cached:
            vectors.append(blob_to_embedding(item["embedding"]))
            source_ids.append(int(item["source_id"]))
    except Exception:
        cached = []
    method = "embeddings_pca" if vectors else "tfidf_pca"
    if not vectors and rows:
        texts = [row.get("semantic_text") or row.get("analysis_text") or "" for row in rows]
        matrix = TfidfVectorizer(max_features=500, min_df=1).fit_transform(texts).toarray()
        vectors = [vector for vector in matrix]
        source_ids = [int(row["id"]) for row in rows]
    if not vectors:
        return [], "unavailable"
    matrix = np.vstack(vectors)
    if len(matrix) == 1:
        coordinates = np.array([[0.0, 0.0]])
    else:
        coordinates = PCA(
            n_components=min(2, matrix.shape[0], matrix.shape[1]), random_state=42
        ).fit_transform(matrix)
        if coordinates.shape[1] == 1:
            coordinates = np.column_stack([coordinates[:, 0], np.zeros(len(coordinates))])
    by_id = {int(row["id"]): row for row in rows}
    points = []
    for source_id, coordinate in zip(source_ids, coordinates):
        row = by_id.get(source_id, {})
        points.append(
            {
                "conversation_id": source_id,
                "x": round(float(coordinate[0]), 6),
                "y": round(float(coordinate[1]), 6),
                "label": (row.get("subject_normalized") or "Senza oggetto")[:100],
                "group": row.get("probable_scope", ""),
                "message_count": row.get("message_count", 0),
                "method": method,
            }
        )
    return points, method


def _terms(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    token_re = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9_-]{3,}")
    frequency: Counter[str] = Counter()
    documents: dict[str, set[int]] = {}
    examples: dict[str, list[int]] = {}
    for row in rows:
        tokens = [token.lower() for token in token_re.findall(row.get("semantic_text") or "")]
        frequency.update(tokens)
        for token in set(tokens):
            documents.setdefault(token, set()).add(row["id"])
            examples.setdefault(token, []).append(row["id"])
    return [
        {
            "term": term,
            "frequency": count,
            "document_frequency": len(documents[term]),
            "probable_area": "",
            "example_conversations": examples[term][:10],
        }
        for term, count in frequency.most_common(500)
    ]


def _similarity_edges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) < 2:
        return []
    texts = [row.get("semantic_text") or row.get("analysis_text") or "" for row in rows]
    matrix = TfidfVectorizer(max_features=1000, min_df=1).fit_transform(texts)
    similarities = cosine_similarity(matrix)
    edges = []
    for left in range(len(rows)):
        ranked = sorted(
            ((right, similarities[left, right]) for right in range(left + 1, len(rows))),
            key=lambda item: item[1],
            reverse=True,
        )[:5]
        edges.extend(
            {
                "source": rows[left]["id"],
                "target": rows[right]["id"],
                "similarity": round(float(score), 6),
            }
            for right, score in ranked
            if score > 0
        )
    return edges


def _edges_and_nodes(
    rows: list[dict[str, Any]], terms: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    edges: list[dict[str, Any]] = []
    nodes: dict[str, dict[str, Any]] = {}
    for row in rows:
        cid = f"conversation:{row['id']}"
        nodes[cid] = {
            "node_id": cid,
            "label": row.get("subject_normalized") or cid,
            "node_type": "conversation",
            "size": row["message_count"],
            "group": row["probable_scope"],
            "frequency": row["message_count"],
            "description": "Conversazione storica",
        }
        for entity in row["entities"]:
            eid = f"entity:{entity.lower()}"
            nodes.setdefault(
                eid,
                {
                    "node_id": eid,
                    "label": entity,
                    "node_type": "entity",
                    "size": 1,
                    "group": "entity",
                    "frequency": 0,
                    "description": "Entita ricorrente",
                },
            )
            nodes[eid]["frequency"] += 1
            nodes[eid]["size"] = nodes[eid]["frequency"]
            edges.append(
                {
                    "source": eid,
                    "target": cid,
                    "edge_type": "entity_to_conversation",
                    "weight": 1,
                    "example": row["id"],
                    "source_type": "entity",
                    "target_type": "conversation",
                }
            )
        for domain in row["domains"]:
            did = f"domain:{domain}"
            nodes.setdefault(
                did,
                {
                    "node_id": did,
                    "label": domain,
                    "node_type": "domain",
                    "size": 1,
                    "group": "domain",
                    "frequency": 0,
                    "description": "Dominio email",
                },
            )
            nodes[did]["frequency"] += 1
            nodes[did]["size"] = nodes[did]["frequency"]
            edges.append(
                {
                    "source": did,
                    "target": cid,
                    "edge_type": "domain_to_conversation",
                    "weight": 1,
                    "example": row["id"],
                    "source_type": "domain",
                    "target_type": "conversation",
                }
            )
    for term in terms[:100]:
        tid = f"term:{term['term']}"
        nodes[tid] = {
            "node_id": tid,
            "label": term["term"],
            "node_type": "term",
            "size": term["document_frequency"],
            "group": "term",
            "frequency": term["frequency"],
            "description": "Termine ricorrente",
        }
        for cid in term["example_conversations"]:
            edges.append(
                {
                    "source": tid,
                    "target": f"conversation:{cid}",
                    "edge_type": "term_to_conversation",
                    "weight": 1,
                    "example": cid,
                    "source_type": "term",
                    "target_type": "conversation",
                }
            )
    return edges, list(nodes.values())


def _candidate_rows(con, project_id: int) -> list[dict[str, Any]]:
    result = []
    for row in con.execute(
        "SELECT * FROM atlas_candidate_categories WHERE project_id=? ORDER BY id", (project_id,)
    ):
        item = dict(row)
        conversation_ids = [
            r[0]
            for r in con.execute(
                "SELECT conversation_id FROM atlas_candidate_conversations WHERE candidate_id=? ORDER BY representative DESC,conversation_id",
                (item["id"],),
            )
        ]
        result.append(
            {
                "candidate_id": item["id"],
                "proposed_name": item["name"],
                "proposed_scope": item["scope"],
                "proposed_subject": "",
                "proposed_context": "",
                "proposed_theme": item["name"],
                "description": item["description"] or "",
                "why_it_exists": item["rationale"] or "",
                "conversation_count": item["conversation_count"],
                "example_conversation_ids": conversation_ids[:10],
                "main_terms": _loads(item["lexical_signals_json"]),
                "main_subjects": [],
                "main_domains": _loads(item["recurring_domains_json"]),
                "similar_categories": [],
                "possible_merge_with": _loads(item["merge_with_json"]),
                "possible_exclusions": [],
                "confidence": item["confidence"],
                "human_decision": "",
                "final_name": "",
                "final_scope": "",
                "final_theme": "",
                "final_description": "",
                "notes": "",
            }
        )
    return result


WORKSPACE_FIELDS = [
    "candidate_id",
    "proposed_name",
    "proposed_scope",
    "proposed_subject",
    "proposed_context",
    "proposed_theme",
    "description",
    "why_it_exists",
    "conversation_count",
    "example_conversation_ids",
    "main_terms",
    "main_subjects",
    "main_domains",
    "similar_categories",
    "possible_merge_with",
    "possible_exclusions",
    "confidence",
    "human_decision",
    "final_name",
    "final_scope",
    "final_theme",
    "final_description",
    "notes",
]


def export_study_pack(db_path: Path, project: str, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        rows = _conversation_rows(con, pid)
        points, point_method = _semantic_points(con, rows)
        point_map = {row["conversation_id"]: row for row in points}
        terms = _terms(rows)
        similarity_edges = _similarity_edges(rows)
        edges, nodes = _edges_and_nodes(rows, terms)
        candidates = _candidate_rows(con, pid)
        message_rows = [
            dict(row)
            for row in con.execute(
                """SELECT cm.conversation_id,cm.email_id,cm.position,cm.relation_method,cm.relation_confidence,e.sent_at,e.sender,e.subject FROM atlas_conversation_messages cm JOIN atlas_conversations c ON c.id=cm.conversation_id JOIN emails e ON e.id=cm.email_id WHERE c.project_id=? ORDER BY cm.conversation_id,cm.position""",
                (pid,),
            )
        ]
        entities = [
            dict(row)
            for row in con.execute(
                "SELECT id entity_id,display_name entity,entity_type,frequency,confidence FROM atlas_entities WHERE project_id=? ORDER BY frequency DESC",
                (pid,),
            )
        ]
        attachments = [
            dict(row)
            for row in con.execute(
                """SELECT cm.conversation_id,a.email_id,a.filename,a.attachment_type,a.mime_type,a.size_bytes FROM attachments a JOIN atlas_conversation_messages cm ON cm.email_id=a.email_id JOIN atlas_conversations c ON c.id=cm.conversation_id WHERE c.project_id=?""",
                (pid,),
            )
        ]
    conversation_export = []
    for row in rows:
        point = point_map.get(row["id"], {})
        conversation_export.append(
            {
                "conversation_id": row["id"],
                "subject_normalized": row["subject_normalized"],
                "date_start": row["date_start"],
                "date_end": row["date_end"],
                "year": row["year"],
                "month": row["month"],
                "message_count": row["message_count"],
                "incoming_count": row["incoming_count"],
                "outgoing_count": row["outgoing_count"],
                "participants_count": len(row["participants"]),
                "sender_domains": row["domains"],
                "main_domain": row["domains"][0] if row["domains"] else "",
                "main_subject": row["subject_normalized"],
                "main_entity": row["entities"][0] if row["entities"] else "",
                "probable_scope": row["probable_scope"],
                "probable_subject": row["entities"][0] if row["entities"] else "",
                "probable_context": "",
                "technical_terms": [
                    term["term"] for term in terms if row["id"] in term["example_conversations"]
                ][:12],
                "attachment_count": row["attachments_count"],
                "attachment_types": sorted(
                    {Path(name).suffix.lower() for name in row["attachments"]}
                ),
                "clean_summary": (row.get("unique_clean_text") or "")[:500],
                "semantic_text_short": (row.get("semantic_text") or "")[:2000],
                "cluster_id": "",
                "cluster_label": "",
                "x": point.get("x", ""),
                "y": point.get("y", ""),
                "confidence": row["confidence"],
                "warnings": row["warnings"],
                "review_status": row["status"],
            }
        )
    feature_fields = [
        "conversation_id",
        "message_count",
        "incoming_count",
        "outgoing_count",
        "participants_count",
        "attachment_count",
        "confidence",
        "probable_scope",
        "year",
        "month",
    ]
    _write_csv(
        output / "conversations.csv",
        conversation_export,
        list(conversation_export[0]) if conversation_export else ["conversation_id"],
    )
    _write_csv(
        output / "conversation_messages.csv",
        message_rows,
        [
            "conversation_id",
            "email_id",
            "position",
            "relation_method",
            "relation_confidence",
            "sent_at",
            "sender",
            "subject",
        ],
    )
    _write_csv(output / "conversation_features.csv", conversation_export, feature_fields)
    _write_csv(
        output / "semantic_points.csv",
        points,
        ["conversation_id", "x", "y", "label", "group", "message_count", "method"],
    )
    _write_csv(
        output / "similarity_edges.csv", similarity_edges, ["source", "target", "similarity"]
    )
    _write_csv(
        output / "entities.csv",
        entities,
        ["entity_id", "entity", "entity_type", "frequency", "confidence"],
    )
    _write_csv(
        output / "subjects.csv",
        [
            {
                "subject": row["subject_normalized"],
                "conversation_id": row["id"],
                "scope": row["probable_scope"],
            }
            for row in rows
        ],
        ["subject", "conversation_id", "scope"],
    )
    _write_csv(
        output / "terms.csv",
        terms,
        ["term", "frequency", "document_frequency", "probable_area", "example_conversations"],
    )
    _write_csv(
        output / "attachments.csv",
        attachments,
        ["conversation_id", "email_id", "filename", "attachment_type", "mime_type", "size_bytes"],
    )
    _write_csv(
        output / "candidate_clusters.csv",
        [
            {
                "cluster_id": row["candidate_id"],
                "label": row["proposed_name"],
                "conversation_count": row["conversation_count"],
                "warning": "Fragile" if float(row["confidence"] or 0) < 0.6 else "",
            }
            for row in candidates
        ],
        ["cluster_id", "label", "conversation_count", "warning"],
    )
    _write_csv(output / "candidate_categories.csv", candidates, WORKSPACE_FIELDS)
    _write_csv(output / "atlas_draft.csv", candidates, WORKSPACE_FIELDS)
    _write_csv(
        output / "nodes.csv",
        nodes,
        ["node_id", "label", "node_type", "size", "group", "frequency", "description"],
    )
    _write_csv(
        output / "edges.csv",
        edges,
        ["source", "target", "edge_type", "weight", "example", "source_type", "target_type"],
    )
    _write_csv(output / "classification_workspace.csv", candidates, WORKSPACE_FIELDS)
    _write_orange_docs(output)
    _write_study_report(
        output / "study_report.html", rows, points, candidates, terms, nodes, edges, point_method
    )
    return {
        "output": str(output),
        "files": sorted(path.name for path in output.iterdir()),
        "conversations": len(rows),
        "semantic_map_method": point_method,
        "embeddings_used": point_method == "embeddings_pca",
        "warnings": []
        if point_method == "embeddings_pca"
        else ["Embedding non disponibili: mappa 2D calcolata con TF-IDF e PCA."],
        "next_step": "Apri study_report.html oppure genera l'Orange Pack.",
    }


def export_orange(db_path: Path, project: str, output: Path) -> dict[str, Any]:
    study = output / "_study"
    result = export_study_pack(db_path, project, study)
    output.mkdir(parents=True, exist_ok=True)
    mapping = {
        "conversations.csv": "orange_conversations.csv",
        "terms.csv": "orange_terms.csv",
        "entities.csv": "orange_entities.csv",
        "edges.csv": "orange_edges.csv",
        "nodes.csv": "orange_nodes.csv",
        "candidate_categories.csv": "orange_candidate_categories.csv",
    }
    for source, target in mapping.items():
        (output / target).write_bytes((study / source).read_bytes())
    _write_orange_docs(output)
    return {
        "output": str(output),
        "files": sorted(path.name for path in output.iterdir() if path.is_file()),
        "embeddings_used": result["embeddings_used"],
        "warnings": result["warnings"],
    }


def _write_orange_docs(output: Path) -> None:
    (output / "orange_readme.md").write_text(
        """# Orange Export Pack\n\nApri `orange_conversations.csv` con **File**. In **Select Columns** usa testo, domini, ambito e termini come meta; usa conteggi, confidenza, x e y come feature. Collega **Scatter Plot** per la mappa, **Distributions** per confrontare ambiti, **Data Table** per leggere gli esempi e **Hierarchical Clustering** per esplorare gruppi. Con Text add-on crea un Corpus da `semantic_text_short`; con Network add-on importa `orange_nodes.csv` e `orange_edges.csv`. I gruppi sono proposte di studio, non decisioni automatiche.\n""",
        encoding="utf-8",
    )
    (output / "orange_workflow_suggestions.md").write_text(
        """# Workflow Orange suggeriti\n\n## A - Esplorazione conversazioni\nFile -> Select Columns -> Scatter Plot -> Data Table\n\n## B - Analisi distribuzioni\nFile -> Distributions -> Box Plot -> Data Table\n\n## C - Esplorazione testuale\nCreate Corpus -> Preprocess Text -> Topic Modelling / Word Cloud / Document Map\n\n## D - Analisi reti\nFile nodes/edges -> Network Explorer\n""",
        encoding="utf-8",
    )


def _write_study_report(
    path: Path, rows, points, candidates, terms, nodes, edges, method: str
) -> None:
    years = Counter(row["year"] or "Senza data" for row in rows)
    scopes = Counter(row["probable_scope"] for row in rows)
    domains = Counter(domain for row in rows for domain in row["domains"])
    isolated = sum(row["message_count"] == 1 for row in rows)

    def bars(values):
        return "".join(
            f"<tr><td>{html.escape(str(k))}</td><td>{v}</td><td><div class='bar' style='width:{min(100, v * 4)}px'></div></td></tr>"
            for k, v in values
        )

    dots = "".join(
        f"<circle cx='{50 + p['x'] * 20:.1f}' cy='{50 + p['y'] * 20:.1f}' r='{max(3, math.sqrt(p['message_count']) * 3):.1f}'><title>{html.escape(p['label'])}</title></circle>"
        for p in points[:500]
    )
    path.write_text(
        f"""<!doctype html><meta charset='utf-8'><title>Email Atlas - Studio Report</title><style>body{{font:15px system-ui;max-width:1200px;margin:30px auto;color:#17212b}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.card,section{{border:1px solid #ccd5d8;padding:16px;margin:14px 0}}.card strong{{font-size:28px;display:block}}table{{border-collapse:collapse;width:100%}}td,th{{padding:7px;border-bottom:1px solid #ddd;text-align:left}}.bar{{height:10px;background:#087f75}}svg{{width:100%;height:480px;background:#f5f7f7}}circle{{fill:#087f75;opacity:.65}}</style><h1>Studio dell'archivio storico</h1><p>Laboratorio esplorativo locale. Metodo mappa: <strong>{method}</strong>.</p><div class='grid'><div class='card'><strong>{sum(r["message_count"] for r in rows)}</strong>Email</div><div class='card'><strong>{len(rows)}</strong>Conversazioni</div><div class='card'><strong>{isolated}</strong>Isolate</div><div class='card'><strong>{len(rows) - isolated}</strong>Multi-messaggio</div></div><section><h2>Distribuzioni temporali</h2><table>{bars(years.most_common())}</table></section><section><h2>Distribuzione ambiti provvisori</h2><table>{bars(scopes.most_common())}</table></section><section><h2>Domini principali</h2><table>{bars(domains.most_common(30))}</table></section><section><h2>Mappa semantica 2D</h2><p>{"Coordinate da embedding." if method == "embeddings_pca" else "Embedding non disponibili: fallback TF-IDF + PCA."}</p><svg viewBox='0 0 100 100' preserveAspectRatio='xMidYMid meet'>{dots}</svg></section><section><h2>Cluster e categorie provvisorie</h2><p>{len(candidates)} categorie candidate. Controlla cluster piccoli, grandi o frammentati nel CSV.</p></section><section><h2>Rete relazionale</h2><p>{len(nodes)} nodi e {len(edges)} archi esportati per Orange, Gephi o Cytoscape.</p></section><section><h2>Termini principali</h2><table>{bars([(t["term"], t["document_frequency"]) for t in terms[:30]])}</table></section><section><h2>Raccomandazioni per la classificazione</h2><ul><li>Valuta prima categorie con molte conversazioni e termini coerenti.</li><li>Unisci proposte piccole con soggetti e domini simili.</li><li>Escludi rumore personale o promozionale non utile.</li><li>Compila classification_workspace.csv prima dell'import finale.</li></ul></section>""",
        encoding="utf-8",
    )


def build_study_dataset(
    input_path: Path,
    db_path: Path,
    project: str,
    output: Path,
    config_path: Path = Path("config/default.yaml"),
    accounts: list[str] | None = None,
    rebuild_derived: bool = False,
) -> dict[str, Any]:
    from email_cluster.cli.app import import_emails

    init_db(db_path)
    inventory(input_path, db_path, project, output / "reports")
    import_emails(source=input_path, project=project, db=db_path, config=config_path)
    parse_and_clean(db_path, project, config_path, output / "reports")
    conversations = build_conversations(
        db_path,
        project,
        accounts,
        output / "reports",
        mode="rebuild-derived" if rebuild_derived else "safe",
    )
    build_index(db_path, project)
    extract_entities(db_path, project, reports=output / "reports")
    build_semantic_docs(db_path, project)
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        if not con.execute(
            "SELECT 1 FROM atlas_candidate_categories WHERE project_id=?", (pid,)
        ).fetchone():
            heuristic_discovery(db_path, project, reports=output / "reports")
    result = export_study_pack(db_path, project, output)
    result["mode"] = "rebuild-derived" if rebuild_derived else "safe"
    result["conversation_build"] = conversations
    return result


def import_classification(
    db_path: Path, project: str, source: Path, output: Path
) -> dict[str, Any]:
    if not source.exists():
        raise ValueError(f"File non trovato: {source}")
    accepted = {"approve", "approved", "approva", "include", "includi"}
    with source.open(encoding="utf-8-sig", newline="") as handle:
        decisions = [
            row
            for row in csv.DictReader(handle)
            if row.get("human_decision", "").strip().lower() in accepted
        ]
    from email_cluster.atlas.review import review_action

    for row in decisions:
        try:
            review_action(
                db_path,
                project,
                int(row.get("candidate_id") or 0),
                "approve",
                row.get("final_name") or row.get("proposed_name"),
                row.get("notes", ""),
            )
        except ValueError:
            # Re-importing an already approved workspace is intentionally idempotent.
            pass
    final = []
    for row in decisions:
        final.append(
            {
                "candidate_id": row.get("candidate_id"),
                "name": row.get("final_name") or row.get("proposed_name"),
                "scope": row.get("final_scope") or row.get("proposed_scope"),
                "theme": row.get("final_theme") or row.get("proposed_theme"),
                "description": row.get("final_description") or row.get("description"),
                "confidence": row.get("confidence"),
                "notes": row.get("notes", ""),
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    fields = ["candidate_id", "name", "scope", "theme", "description", "confidence", "notes"]
    _write_csv(output / "atlas_final.csv", final, fields)
    (output / "atlas_final.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "atlas_final.yaml").write_text(
        yaml.safe_dump(final, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    items = "".join(
        f"<article><h2>{html.escape(item['name'] or '')}</h2><p><strong>{html.escape(item['scope'] or '')}</strong> - {html.escape(item['theme'] or '')}</p><p>{html.escape(item['description'] or '')}</p></article>"
        for item in final
    )
    (output / "atlas_final.html").write_text(
        f"<!doctype html><meta charset='utf-8'><title>Atlante finale</title><h1>Atlante finale - {html.escape(project)}</h1>{items}",
        encoding="utf-8",
    )
    return {
        "imported": len(final),
        "output": str(output),
        "files": ["atlas_final.csv", "atlas_final.yaml", "atlas_final.json", "atlas_final.html"],
    }
