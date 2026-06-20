from __future__ import annotations

import re
import sqlite3
import zlib
from collections import Counter, defaultdict

from email_cluster.operational.macro import classify_macro
from email_cluster.storage.repository import utcnow

NON_PROFESSIONAL = {
    "personale", "automatico_account", "newsletter_eventi", "ecommerce_spedizioni",
    "notifiche_tecniche", "rumore_non_classificabile",
}


def build_operational_contexts(con: sqlite3.Connection, project_id: int, run_id: int) -> dict[str, int]:
    rows = list(con.execute("""
        SELECT e.id email_id,e.subject,e.sender,e.has_attachments,sc.message_type,
               ec.cluster_id,ec.probability,ec.is_noise,c.label_auto,c.keywords_json,
               c.mean_probability cluster_probability
        FROM emails e
        JOIN semantic_contexts sc ON sc.id=(SELECT max(sc2.id) FROM semantic_contexts sc2 WHERE sc2.email_id=e.id)
        LEFT JOIN email_clusters ec ON ec.email_id=e.id AND ec.clustering_run_id=?
        LEFT JOIN clusters c ON c.clustering_run_id=? AND c.cluster_id=ec.cluster_id
        WHERE e.project_id=?
    """, (run_id, run_id, project_id)))
    grouped: dict[tuple[str, int], list[sqlite3.Row]] = defaultdict(list)
    reasons: dict[int, str] = {}
    for row in rows:
        macro, reason = classify_macro(row["subject"] or "", row["sender"] or "", row["message_type"], bool(row["has_attachments"]))
        technical_cluster = int(row["cluster_id"]) if row["cluster_id"] is not None else -999
        if macro in NON_PROFESSIONAL:
            key_cluster = _macro_synthetic_id(macro)
        elif technical_cluster in {-1, -999}:
            key_cluster = _noise_context_id(row)
        elif float(row["cluster_probability"] or 0) < 0.60:
            key_cluster = _mixed_context_id(technical_cluster, row)
        else:
            key_cluster = technical_cluster
        grouped[(macro, key_cluster)].append(row)
        reasons[int(row["email_id"])] = reason
    created = assigned = suspicious = 0
    for (macro, cluster_id), members in grouped.items():
        name, entity, domain, topic = _context_identity(macro, members)
        context_type = _context_type(macro, topic)
        confidence = _context_confidence(members)
        is_professional = macro.startswith("professionale")
        impact = min(len(members), 30) * (1.5 if is_professional else 0.4)
        priority = round((1 - confidence) * 40 + impact + (20 if is_professional else 5), 2)
        description = _summary(name, macro, members)
        why = _why_grouped(macro, members)
        con.execute("""
            INSERT INTO operational_contexts (
                project_id,source_clustering_run_id,source_cluster_id,name,description,context_type,
                macro_category,client_or_entity,technical_domain,practice_or_topic,why_grouped,
                suggested_user_action,source,confidence,review_status,review_priority,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'pending',?,?,?)
            ON CONFLICT(project_id,source_clustering_run_id,source_cluster_id,macro_category) DO UPDATE SET
                name=CASE WHEN operational_contexts.source='human' THEN operational_contexts.name ELSE excluded.name END,
                description=excluded.description,why_grouped=excluded.why_grouped,confidence=excluded.confidence,
                review_priority=excluded.review_priority,updated_at=excluded.updated_at
        """, (project_id,run_id,cluster_id,name,description,context_type,macro,entity,domain,topic,why,
              "approva" if confidence >= 0.7 else "controlla_email_sospette","auto",confidence,priority,utcnow(),utcnow()))
        context = con.execute("SELECT id FROM operational_contexts WHERE project_id=? AND source_clustering_run_id=? AND source_cluster_id=? AND macro_category=?", (project_id,run_id,cluster_id,macro)).fetchone()
        context_id = int(context["id"])
        created += 1
        for member in members:
            member_suspicious = is_professional and (bool(member["is_noise"]) or float(member["probability"] or 0) < 0.45)
            con.execute("""
                UPDATE email_context_assignments SET review_status='moved',updated_at=?
                WHERE email_id=? AND operational_context_id!=? AND assignment_source='auto'
                  AND review_status IN ('pending','moved')
            """, (utcnow(), member["email_id"], context_id))
            con.execute("""
                INSERT INTO email_context_assignments (
                    email_id,operational_context_id,macro_category,assignment_source,confidence,
                    review_status,reason,is_suspicious,created_at,updated_at
                ) VALUES (?,?,?,'auto',?,'pending',?,?,?,?)
                ON CONFLICT(email_id,operational_context_id) DO UPDATE SET confidence=excluded.confidence,
                    reason=excluded.reason,is_suspicious=excluded.is_suspicious,review_status='pending',updated_at=excluded.updated_at
            """, (member["email_id"],context_id,macro,float(member["probability"] or confidence),
                  reasons[int(member["email_id"])],int(member_suspicious),utcnow(),utcnow()))
            assigned += 1
            suspicious += int(member_suspicious)
    con.execute("""
        UPDATE operational_contexts SET review_status='archived',updated_at=?
        WHERE project_id=? AND source='auto' AND review_status='pending'
          AND NOT EXISTS (
            SELECT 1 FROM email_context_assignments eca
            WHERE eca.operational_context_id=operational_contexts.id
              AND eca.review_status NOT IN ('moved','excluded')
          )
    """, (utcnow(), project_id))
    return {"contexts": created, "assignments": assigned, "suspicious": suspicious}


def _context_identity(macro: str, members: list[sqlite3.Row]) -> tuple[str, str, str, str]:
    if macro in NON_PROFESSIONAL:
        display = macro.replace("_", " ").title()
        return display, "", macro.replace("_", " "), display
    subjects = " ".join(row["subject"] or "" for row in members)
    words = [word for word in re.findall(r"[A-Za-zÀ-ÿ]{4,}", subjects.lower()) if word not in STOPWORDS]
    topic_words = [word for word, _ in Counter(words).most_common(3)]
    domains = [match.group(1).lower() for row in members if (match := re.search(r"@([\w.-]+)", row["sender"] or ""))]
    domain = Counter(domains).most_common(1)[0][0] if domains else ""
    entity = _entity_from_domain(domain)
    topic = " / ".join(topic_words) or "comunicazioni operative"
    name = f"{entity} — {topic}" if entity else topic.title()
    return name, entity, domain, topic


def _context_type(macro: str, topic: str) -> str:
    if macro == "professionale_amministrativo":
        return "amministrativo"
    if any(word in topic for word in ("mud", "rifiuti", "autorizzazione", "registro")):
        return "adempimento"
    if any(word in topic for word in ("relazione", "documenti", "planimetria")):
        return "documentazione"
    return "tema_tecnico" if macro == "professionale_operativo" else macro.replace("_eventi", "")


def _context_confidence(members: list[sqlite3.Row]) -> float:
    probabilities = [float(row["probability"]) for row in members if row["probability"] is not None and not row["is_noise"]]
    return round(sum(probabilities) / len(probabilities), 3) if probabilities else 0.35


def _summary(name: str, macro: str, members: list[sqlite3.Row]) -> str:
    return f"{len(members)} comunicazioni nel contesto {name}. Macro categoria: {macro.replace('_', ' ')}."


def _why_grouped(macro: str, members: list[sqlite3.Row]) -> str:
    if macro in NON_PROFESSIONAL:
        return "Raggruppate prima del contesto professionale perché condividono la stessa macro categoria."
    return "Stessa macro categoria professionale, vicinanza semantica e ricorrenza di oggetti/interlocutori."


def _entity_from_domain(domain: str) -> str:
    root = domain.split(".")[0] if domain else ""
    return root.replace("-", " ").title() if root not in {"gmail", "outlook", "hotmail", "yahoo"} else ""


def _macro_synthetic_id(macro: str) -> int:
    return -1000 - sorted(NON_PROFESSIONAL).index(macro)


def _noise_context_id(row: sqlite3.Row) -> int:
    sender = row["sender"] or ""
    match = re.search(r"@([\w.-]+)", sender)
    domain = match.group(1).lower() if match else ""
    words = [word for word in re.findall(r"[A-Za-zÀ-ÿ]{4,}", row["subject"] or "") if word.lower() not in STOPWORDS]
    topic = " ".join(words[:2]).lower() or "senza tema"
    key = f"{domain}:{topic}"
    return -2_000_000 - (zlib.crc32(key.encode("utf-8")) % 1_000_000)


def _mixed_context_id(cluster_id: int, row: sqlite3.Row) -> int:
    words = [word.lower() for word in re.findall(r"[A-Za-zÀ-ÿ]{4,}", row["subject"] or "") if word.lower() not in STOPWORDS]
    topic = " ".join(words[:2]) or f"cluster {cluster_id}"
    key = f"{cluster_id}:{topic}"
    return -4_000_000 - (zlib.crc32(key.encode("utf-8")) % 1_000_000)


STOPWORDS = {"della","delle","degli","alla","alle","come","email","mail","allegato","documento","richiesta","risposta","buongiorno","grazie","inviato","inoltro","segue","tenax"}
