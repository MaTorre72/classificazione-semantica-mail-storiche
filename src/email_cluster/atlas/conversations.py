from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from email_cluster.cleaning.normalizer import clean_subject
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, utcnow

from .reports import write_report

GENERIC_SUBJECTS = {"documenti", "informazioni", "richiesta", "aggiornamento", "comunicazione"}


def normalize_message_id(value: str | None) -> str:
    """Return a comparable Message-ID without brackets or casing noise."""
    return (value or "").strip().strip("<>").lower()


def header_message_ids(value: Any) -> list[str]:
    """Extract normalized IDs from References or In-Reply-To."""
    return [normalize_message_id(item) for item in re.findall(r"<([^>]+)>", str(value or ""))]


def normalized_participants(row: dict[str, Any]) -> set[str]:
    recipients = json.loads(row["recipients"] or "[]")
    return {str(value).strip().lower() for value in [row["sender"], *recipients] if value}


def stable_conversation_key(members: list[dict[str, Any]]) -> str:
    """Build a key independent from internal email IDs whenever headers are available."""
    message_ids = sorted(
        value for row in members if (value := normalize_message_id(row["original_message_id"]))
    )
    if message_ids:
        material = "message-ids|" + "|".join(message_ids)
    else:
        subject = clean_subject(members[-1]["subject"] or "").lower()
        participants = sorted({item for row in members for item in normalized_participants(row)})
        first_date = (members[0]["sent_at"] or members[0]["imported_at"] or "")[:10]
        material = f"fallback|{subject}|{first_date}|{'|'.join(participants)}"
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()


def _days_between(first: str | None, second: str | None) -> int:
    try:
        return abs((datetime.fromisoformat(first) - datetime.fromisoformat(second)).days)
    except (TypeError, ValueError):
        return 999


def build_conversations(
    db_path: Path,
    project: str,
    accounts: list[str] | None = None,
    reports: Path = Path("reports"),
) -> dict[str, Any]:
    """Reconstruct conversations using headers first and a conservative fallback second."""
    init_db(db_path)
    accounts = [value.lower() for value in (accounts or [])]
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        rows = [
            dict(row)
            for row in con.execute(
                """SELECT e.*,c.subject_clean,c.current_message_text,c.quoted_thread_text,
                       c.forwarded_text
                   FROM emails e
                   LEFT JOIN clean_texts c ON c.id=(
                       SELECT max(c2.id) FROM clean_texts c2 WHERE c2.email_id=e.id
                   )
                   WHERE e.project_id=?
                   ORDER BY coalesce(e.sent_at,e.imported_at),e.id""",
                (pid,),
            )
        ]
        parent = {row["id"]: row["id"] for row in rows}

        def find(email_id: int) -> int:
            while parent[email_id] != email_id:
                parent[email_id] = parent[parent[email_id]]
                email_id = parent[email_id]
            return email_id

        def union(first: int, second: int) -> None:
            root_first, root_second = find(first), find(second)
            if root_first != root_second:
                parent[root_second] = root_first

        by_message_id = {
            normalize_message_id(row["original_message_id"]): row["id"]
            for row in rows
            if normalize_message_id(row["original_message_id"])
        }
        relation_method = {row["id"]: "isolated" for row in rows}
        subjects: dict[str, list[dict[str, Any]]] = defaultdict(list)
        explicit_links = 0
        generic_subjects_skipped = 0

        for row in rows:
            headers = json.loads(row["raw_headers_json"] or "{}")
            linked_ids = header_message_ids(headers.get("References"))
            linked_ids += header_message_ids(headers.get("In-Reply-To"))
            targets = [by_message_id[value] for value in linked_ids if value in by_message_id]
            if targets:
                for target in targets:
                    union(row["id"], target)
                relation_method[row["id"]] = "headers"
                explicit_links += 1
            subject = clean_subject(row["subject"] or "").lower()
            if subject:
                subjects[subject].append(row)

        fallback_links = 0
        for subject, items in subjects.items():
            if len(subject) < 8 or subject in GENERIC_SUBJECTS:
                generic_subjects_skipped += len(items)
                continue
            for previous, current in zip(items, items[1:]):
                if relation_method[current["id"]] == "headers":
                    continue
                same_people = normalized_participants(previous) & normalized_participants(current)
                if _days_between(current["sent_at"], previous["sent_at"]) <= 45 and same_people:
                    union(previous["id"], current["id"])
                    relation_method[current["id"]] = "subject_participants_date"
                    fallback_links += 1

        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[find(row["id"])].append(row)

        con.execute(
            "DELETE FROM atlas_conversation_messages WHERE conversation_id IN "
            "(SELECT id FROM atlas_conversations WHERE project_id=?)",
            (pid,),
        )
        con.execute("DELETE FROM atlas_conversations WHERE project_id=?", (pid,))
        low_confidence = isolated = header_conversations = fallback_conversations = 0
        conversation_examples: list[dict[str, Any]] = []

        for members in groups.values():
            members.sort(key=lambda row: (row["sent_at"] or row["imported_at"], row["id"]))
            explicit = sum(relation_method[row["id"]] == "headers" for row in members)
            fallback = sum(
                relation_method[row["id"]] == "subject_participants_date" for row in members
            )
            method = (
                "headers" if explicit else "subject_participants_date" if fallback else "isolated"
            )
            confidence = 0.95 if explicit else 0.65 if fallback else 0.4
            header_conversations += int(method == "headers")
            fallback_conversations += int(method == "subject_participants_date")
            low_confidence += int(confidence < 0.6)
            isolated += int(len(members) == 1)
            participants = sorted(
                {person for row in members for person in normalized_participants(row)}
            )
            texts: list[str] = []
            seen: set[str] = set()
            for row in members:
                text = (row["current_message_text"] or row["body_extracted_text"] or "").strip()
                digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
                if text and digest not in seen:
                    texts.append(text)
                    seen.add(digest)
            subject = clean_subject(members[-1]["subject"] or "")
            analysis = (subject + "\n\n" + "\n\n".join(texts))[:50000]
            incoming = (
                sum(
                    not any(account in (row["sender"] or "").lower() for account in accounts)
                    for row in members
                )
                if accounts
                else len(members)
            )
            outgoing = len(members) - incoming
            reason = {
                "headers": "Catena esplicita Message-ID / References / In-Reply-To.",
                "subject_participants_date": (
                    "Fallback: stesso oggetto normalizzato, partecipanti comuni e massimo 45 giorni."
                ),
                "isolated": "Nessuna relazione sufficientemente affidabile trovata.",
            }[method]
            warnings = [] if method == "headers" else [reason]
            cursor = con.execute(
                """INSERT INTO atlas_conversations(
                       project_id,stable_key,subject_normalized,date_start,date_end,message_count,
                       incoming_count,outgoing_count,attachments_count,participants_json,
                       unique_clean_text,analysis_text,confidence,reconstruction_method,warnings_json,
                       created_at,updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pid,
                    stable_conversation_key(members),
                    subject,
                    members[0]["sent_at"],
                    members[-1]["sent_at"],
                    len(members),
                    incoming,
                    outgoing,
                    sum(row["has_attachments"] or 0 for row in members),
                    json.dumps(participants, ensure_ascii=False),
                    "\n\n".join(texts),
                    analysis,
                    confidence,
                    method,
                    json.dumps(warnings, ensure_ascii=False),
                    utcnow(),
                    utcnow(),
                ),
            )
            conversation_id = int(cursor.lastrowid)
            con.executemany(
                """INSERT INTO atlas_conversation_messages(
                       conversation_id,email_id,position,relation_method,relation_confidence
                   ) VALUES(?,?,?,?,?)""",
                [
                    (conversation_id, row["id"], position, relation_method[row["id"]], confidence)
                    for position, row in enumerate(members)
                ],
            )
            conversation_examples.append(
                {
                    "id": conversation_id,
                    "subject": subject,
                    "messages": len(members),
                    "method": method,
                    "confidence": confidence,
                    "reason": reason,
                }
            )

    long_examples = sorted(conversation_examples, key=lambda item: item["messages"], reverse=True)[
        :10
    ]
    possible_false_positives = [
        item
        for item in conversation_examples
        if item["method"] == "subject_participants_date" and item["messages"] >= 3
    ][:10]
    possible_broken_threads = [
        item
        for item in conversation_examples
        if item["method"] == "isolated" and len(item["subject"]) >= 8
    ][:10]
    isolated_examples = [item for item in conversation_examples if item["method"] == "isolated"][
        :20
    ]
    multi_message_examples = [item for item in conversation_examples if item["messages"] > 1][:20]
    result = {
        "project": project,
        "emails": len(rows),
        "conversations": len(groups),
        "reduction_ratio": round(1 - len(groups) / max(len(rows), 1), 3),
        "from_explicit_headers": header_conversations,
        "from_fallback": fallback_conversations,
        "isolated": isolated,
        "low_confidence": low_confidence,
        "explicit_links": explicit_links,
        "fallback_links": fallback_links,
        "generic_subject_messages_excluded_from_fallback": generic_subjects_skipped,
        "mean_messages": round(len(rows) / max(len(groups), 1), 2),
        "reconstruction_quality": {
            "multi_message": len(groups) - isolated,
            "isolated_percent": round(isolated * 100 / max(len(groups), 1), 1),
            "header_based": header_conversations,
            "fallback_based": fallback_conversations,
            "low_confidence": low_confidence,
        },
        "isolated_conversations": isolated_examples,
        "multi_message_conversations": multi_message_examples,
        "fallback_conversations": [
            item for item in conversation_examples if item["method"] == "subject_participants_date"
        ][:20],
        "examples_to_verify": possible_false_positives + possible_broken_threads,
        "possible_fragility_causes": [
            "Posta inviata non importata.",
            "Header References o In-Reply-To mancanti.",
            "Raggruppamento prudente per evitare falsi positivi.",
        ],
        "long_conversation_examples": long_examples,
        "possible_false_positives": possible_false_positives,
        "possible_broken_threads": possible_broken_threads,
        "warnings": [
            "Controlla prima le Conversazioni a bassa Affidabilità e quelle costruite per fallback."
        ],
        "next_step": "Verifica il report, poi indicizza l'Archivio con email-atlas index.",
    }
    write_report(reports / "conversation_report.html", "Conversazioni ricostruite", result)
    return result
