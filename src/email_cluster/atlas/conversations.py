from __future__ import annotations

from array import array
from collections.abc import Iterator, Sequence
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from pathlib import Path
from typing import Any

from email_cluster.cleaning.normalizer import clean_subject
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, utcnow

from .reports import write_report
from .reset import reset_atlas_derived_data

GENERIC_SUBJECTS = {"documenti", "informazioni", "richiesta", "aggiornamento", "comunicazione"}
RELATION_ISOLATED = 0
RELATION_HEADERS = 1
RELATION_SUBJECT_PARTICIPANTS_DATE = 2
RELATION_METHODS = (
    "isolated",
    "headers",
    "subject_participants_date",
)


@dataclass(slots=True)
class ConversationSeedRow:
    id: int
    subject: str | None
    message_id: str
    has_attachments: int
    sent_at: str | None
    imported_at: str | None
    linked_ids: tuple[str, ...]
    participants: tuple[str, ...]
    is_incoming: bool
    relation_code: int = RELATION_ISOLATED
    conversation_root: int = -1


def normalize_message_id(value: str | None) -> str:
    """Return a comparable Message-ID without brackets or casing noise."""
    return (value or "").strip().strip("<>").lower()


def header_message_ids(value: Any) -> list[str]:
    """Extract normalized IDs from References or In-Reply-To."""
    return [normalize_message_id(item) for item in re.findall(r"<([^>]+)>", str(value or ""))]


def normalized_participants(sender: str | None, recipients_json: str | None) -> set[str]:
    recipients = json.loads(recipients_json or "[]")
    participants: set[str] = set()
    if sender:
        participants.add(str(sender).strip().lower())
    participants.update(str(value).strip().lower() for value in recipients if value)
    return participants


def _header_linked_ids(raw_headers_json: str | None) -> tuple[str, ...]:
    headers = json.loads(raw_headers_json or "{}")
    references = header_message_ids(headers.get("References"))
    if not references:
        return header_message_ids(headers.get("In-Reply-To"))
    in_reply_to = header_message_ids(headers.get("In-Reply-To"))
    if not in_reply_to:
        return references
    return references + in_reply_to


def _conversation_seed_row(row: Any, accounts: set[str]) -> ConversationSeedRow:
    sender = row["sender"] or ""
    sender_lower = sender.lower()
    return ConversationSeedRow(
        id=row["id"],
        subject=clean_subject(row["subject"] or ""),
        message_id=normalize_message_id(row["original_message_id"]),
        has_attachments=row["has_attachments"],
        sent_at=row["sent_at"],
        imported_at=row["imported_at"],
        linked_ids=_header_linked_ids(row["raw_headers_json"]),
        participants=tuple(normalized_participants(sender, row["recipients"])),
        is_incoming=(
            not any(account in sender_lower for account in accounts) if accounts else True
        ),
    )


def _conversation_selected_texts(con, email_ids: Sequence[int]) -> Iterator[tuple[int, str]]:
    """Yield selected text rows for the provided email ids in input order."""
    if not email_ids:
        return
    batch_size = 900
    for offset in range(0, len(email_ids), batch_size):
        batch = email_ids[offset : offset + batch_size]
        if not batch:
            continue
        values = ",".join("(?,?)" for _ in batch)
        query = (
            "WITH requested(id, ord) AS (VALUES "
            f"{values}"
            ") "
            "SELECT e.id,coalesce(c.current_message_text,e.body_extracted_text) selected_text "
            "FROM requested r "
            "JOIN emails e ON e.id=r.id "
            "LEFT JOIN clean_texts c ON c.id=("
            "    SELECT max(c2.id) FROM clean_texts c2 WHERE c2.email_id=e.id"
            ") "
            "ORDER BY r.ord"
        )
        params: list[int] = []
        for position, email_id in enumerate(batch):
            params.extend((int(email_id), position))
        for row in con.execute(query, tuple(params)):
            yield int(row["id"]), row["selected_text"]


def stable_conversation_key(members: list[dict[str, Any]]) -> str:
    """Build a key independent from internal email IDs whenever headers are available."""
    message_ids = sorted(
        value for row in members if (value := normalize_message_id(row["original_message_id"]))
    )
    if message_ids:
        material = "message-ids|" + "|".join(message_ids)
    else:
        subject = clean_subject(members[-1]["subject"] or "").lower()
        participants = sorted({item for row in members for item in row["_participants"]})
        first_date = (members[0]["sent_at"] or members[0]["imported_at"] or "")[:10]
        material = f"fallback|{subject}|{first_date}|{'|'.join(participants)}"
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()


def stable_conversation_key_from_parts(
    *,
    message_ids: list[str],
    fallback_subject: str,
    fallback_first_date: str,
    fallback_participants: list[str],
) -> str:
    """Build a stable key from already aggregated conversation fields."""
    normalized_ids = sorted(normalize_message_id(value) for value in message_ids if value)
    if normalized_ids:
        material = "message-ids|" + "|".join(normalized_ids)
    else:
        material = (
            f"fallback|{clean_subject(fallback_subject).lower()}|{fallback_first_date}|"
            f"{'|'.join(sorted(fallback_participants))}"
        )
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()


def _days_between(first: str | None, second: str | None) -> int:
    try:
        return abs((datetime.fromisoformat(first) - datetime.fromisoformat(second)).days)
    except (TypeError, ValueError):
        return 999


def _append_capped(items: list[dict[str, Any]], item: dict[str, Any], limit: int) -> None:
    if len(items) < limit:
        items.append(item)


def _insert_top_by_messages(
    items: list[dict[str, Any]], item: dict[str, Any], limit: int
) -> None:
    items.append(item)
    items.sort(key=lambda current: current["messages"], reverse=True)
    if len(items) > limit:
        del items[limit:]


def _relation_method_name(relation_code: int) -> str:
    return RELATION_METHODS[relation_code]


def build_conversations(
    db_path: Path,
    project: str,
    accounts: list[str] | None = None,
    reports: Path = Path("reports"),
    mode: str = "safe",
) -> dict[str, Any]:
    """Reconstruct conversations using headers first and a conservative fallback second."""
    init_db(db_path)
    if mode not in {"safe", "rebuild-derived"}:
        raise ValueError("Modalita conversazioni non valida: usa safe o rebuild-derived")
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        existing = con.execute(
            "SELECT count(*) FROM atlas_conversations WHERE project_id=?", (pid,)
        ).fetchone()[0]
        existing_emails = con.execute(
            "SELECT coalesce(sum(message_count),0) FROM atlas_conversations WHERE project_id=?",
            (pid,),
        ).fetchone()[0]
        current_emails = con.execute(
            "SELECT count(*) FROM emails WHERE project_id=?", (pid,)
        ).fetchone()[0]
    reset_report = None
    if existing and mode == "safe":
        if current_emails != existing_emails:
            raise ValueError(
                f"Sono presenti {max(0, current_emails - existing_emails)} email non collegate. "
                "Per proteggere revisioni e Atlante finale non ricostruisco automaticamente: "
                "usa la modalita rebuild-derived, che crea prima un backup."
            )
        result = {
            "project": project,
            "emails": current_emails,
            "conversations": existing,
            "reused": True,
            "mode": "safe",
            "new_unlinked_emails": 0,
            "warnings": [
                "Conversazioni esistenti riutilizzate per proteggere revisioni e dati collegati."
            ],
            "next_step": "Nessuna nuova email da collegare; proseguo con i dati esistenti.",
        }
        write_report(reports / "conversation_report.html", "Conversazioni riutilizzate", result)
        return result
    if existing and mode == "rebuild-derived":
        reset_report = reset_atlas_derived_data(db_path, project).to_dict()
    account_tokens = {value.lower() for value in (accounts or [])}
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        rows = [
            _conversation_seed_row(row, account_tokens)
            for row in con.execute(
                """SELECT e.id,e.sender,e.recipients,e.subject,e.original_message_id,
                          e.raw_headers_json,e.has_attachments,e.sent_at,e.imported_at
                   FROM emails e
                   WHERE e.project_id=?
                   ORDER BY coalesce(e.sent_at,e.imported_at),e.id""",
                (pid,),
            )
        ]
        # Keep the union-find buffer compact because it scales with the archive size.
        parent = array("I", range(len(rows)))

        def find(row_index: int) -> int:
            while parent[row_index] != row_index:
                parent[row_index] = parent[parent[row_index]]
                row_index = parent[row_index]
            return row_index

        def union(first_index: int, second_index: int) -> None:
            root_first, root_second = find(first_index), find(second_index)
            if root_first != root_second:
                parent[root_second] = root_first

        by_message_id = {
            row.message_id: index for index, row in enumerate(rows) if row.message_id
        }
        latest_by_subject: dict[str, int] = {}
        explicit_links = 0
        fallback_links = 0
        generic_subjects_skipped = 0

        for row_index, row in enumerate(rows):
            row.relation_code = RELATION_ISOLATED
            linked = False
            for linked_id in row.linked_ids:
                target = by_message_id.get(linked_id)
                if target is not None:
                    union(row_index, target)
                    linked = True
            row.linked_ids = ()
            if linked:
                row.relation_code = RELATION_HEADERS
                explicit_links += 1
            subject = row.subject.casefold() if row.subject else ""
            if not subject:
                continue
            if len(subject) < 8 or subject in GENERIC_SUBJECTS:
                generic_subjects_skipped += 1
                continue
            previous = latest_by_subject.get(subject)
            if previous is not None and row.relation_code != RELATION_HEADERS:
                previous_row = rows[previous]
                same_people = any(
                    item in previous_row.participants for item in row.participants
                )
                if _days_between(row.sent_at, previous_row.sent_at) <= 45 and same_people:
                    union(previous, row_index)
                    row.relation_code = RELATION_SUBJECT_PARTICIPANTS_DATE
                    fallback_links += 1
            latest_by_subject[subject] = row_index

        for row_index, row in enumerate(rows):
            row.conversation_root = find(row_index)
        del by_message_id
        del latest_by_subject
        parent = None
        emails_count = len(rows)

        low_confidence = isolated = header_conversations = fallback_conversations = 0
        conversations_count = 0
        long_examples: list[dict[str, Any]] = []
        possible_false_positives: list[dict[str, Any]] = []
        possible_broken_threads: list[dict[str, Any]] = []
        isolated_examples: list[dict[str, Any]] = []
        multi_message_examples: list[dict[str, Any]] = []
        fallback_examples: list[dict[str, Any]] = []

        rows.sort(
            key=lambda row: (
                row.conversation_root,
                row.sent_at or row.imported_at,
                row.id,
            )
        )
        current_row_index = 0
        for _, members_iter in groupby(rows, key=lambda row: row.conversation_root):
            conversations_count += 1
            explicit = 0
            fallback = 0
            incoming = 0
            outgoing = 0
            attachments_count = 0
            message_count = 0
            first_sent_at: str | None = None
            first_imported_at: str | None = None
            last_sent_at: str | None = None
            last_subject = ""
            participants_set: set[str] = set()
            # Keep the per-conversation insert payload compact until the batch write.
            conversation_email_ids = array("I")
            conversation_relation_codes = array("B")
            # Avoid allocating list objects for one-message / one-text conversations.
            first_message_id: str | None = None
            message_ids: list[str] | None = None

            for position, row in enumerate(members_iter):
                row_index = current_row_index + position
                conversation_email_ids.append(row.id)
                conversation_relation_codes.append(row.relation_code)
                message_count += 1
                explicit += int(row.relation_code == RELATION_HEADERS)
                fallback += int(row.relation_code == RELATION_SUBJECT_PARTICIPANTS_DATE)
                attachments_count += row.has_attachments or 0
                if first_sent_at is None:
                    first_sent_at = row.sent_at
                    first_imported_at = row.imported_at
                last_sent_at = row.sent_at
                last_subject = row.subject or ""
                participants_set.update(row.participants)
                message_id = row.message_id
                if message_id:
                    if first_message_id is None:
                        first_message_id = message_id
                    elif message_ids is None:
                        message_ids = [first_message_id, message_id]
                        first_message_id = None
                    else:
                        message_ids.append(message_id)
                incoming += int(row.is_incoming)
                outgoing += int(not row.is_incoming)
                row.participants = ()
                row.is_incoming = True
                row.has_attachments = 0
                row.relation_code = RELATION_ISOLATED
                row.subject = None
                row.message_id = ""
                row.sent_at = None
                row.imported_at = None
                row.conversation_root = -1
                rows[row_index] = None

            # Scorre i testi selezionati nell'ordine compatto per evitare un dizionario per-conversazione.
            first_text: str | None = None
            texts: list[str] | None = None
            seen: set[bytes] = set()
            for _email_id, selected_text in _conversation_selected_texts(
                con, conversation_email_ids
            ):
                text = (selected_text or "").strip()
                # Store the raw digest bytes so the de-dup set stays smaller.
                if text:
                    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).digest()
                    if digest not in seen:
                        seen.add(digest)
                        if first_text is None:
                            first_text = text
                        elif texts is None:
                            texts = [first_text, text]
                            first_text = None
                        else:
                            texts.append(text)

            method = (
                "headers" if explicit else "subject_participants_date" if fallback else "isolated"
            )
            confidence = 0.95 if explicit else 0.65 if fallback else 0.4
            header_conversations += int(method == "headers")
            fallback_conversations += int(method == "subject_participants_date")
            low_confidence += int(confidence < 0.6)
            isolated += int(message_count == 1)
            participants = sorted(participants_set)
            subject = last_subject
            if texts is None:
                unique_clean_text = first_text or ""
            else:
                unique_clean_text = "\n\n".join(texts)
            analysis = (subject + "\n\n" + unique_clean_text)[:50000]
            if message_ids is None:
                stable_message_ids = [first_message_id] if first_message_id else []
            else:
                stable_message_ids = message_ids
            del participants_set
            del seen
            del first_message_id
            del message_ids
            del first_text
            del texts
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
                    stable_conversation_key_from_parts(
                        message_ids=stable_message_ids,
                        fallback_subject=last_subject,
                        fallback_first_date=(first_sent_at or first_imported_at or "")[:10],
                        fallback_participants=participants,
                    ),
                    subject,
                    first_sent_at,
                    last_sent_at,
                    message_count,
                    incoming,
                    outgoing,
                    attachments_count,
                    json.dumps(participants, ensure_ascii=False),
                    unique_clean_text,
                    analysis,
                    confidence,
                    method,
                    json.dumps(warnings, ensure_ascii=False),
                    utcnow(),
                    utcnow(),
                ),
            )
            del stable_message_ids
            conversation_id = int(cursor.lastrowid)
            con.executemany(
                """INSERT INTO atlas_conversation_messages(
                       conversation_id,email_id,position,relation_method,relation_confidence
                   ) VALUES(?,?,?,?,?)""",
                (
                    (
                        conversation_id,
                        email_id,
                        position,
                        _relation_method_name(relation_code),
                        confidence,
                    )
                    for position, (email_id, relation_code) in enumerate(
                        zip(conversation_email_ids, conversation_relation_codes)
                    )
                ),
            )
            del conversation_email_ids
            del conversation_relation_codes
            example = {
                "id": conversation_id,
                "subject": subject,
                "messages": message_count,
                "method": method,
                "confidence": confidence,
                "reason": reason,
            }
            _insert_top_by_messages(long_examples, example, limit=10)
            if method == "subject_participants_date":
                _append_capped(fallback_examples, example, limit=20)
                if message_count >= 3:
                    _append_capped(possible_false_positives, example, limit=10)
            if method == "isolated":
                _append_capped(isolated_examples, example, limit=20)
                if len(subject) >= 8:
                    _append_capped(possible_broken_threads, example, limit=10)
            if message_count > 1:
                _append_capped(multi_message_examples, example, limit=20)
            current_row_index += message_count

        rows.clear()
        del rows

    result = {
        "project": project,
        "mode": mode,
        "reused": False,
        "reset": reset_report,
        "emails": emails_count,
        "conversations": conversations_count,
        "reduction_ratio": round(1 - conversations_count / max(emails_count, 1), 3),
        "from_explicit_headers": header_conversations,
        "from_fallback": fallback_conversations,
        "isolated": isolated,
        "low_confidence": low_confidence,
        "explicit_links": explicit_links,
        "fallback_links": fallback_links,
        "generic_subject_messages_excluded_from_fallback": generic_subjects_skipped,
        "mean_messages": round(emails_count / max(conversations_count, 1), 2),
        "reconstruction_quality": {
            "multi_message": conversations_count - isolated,
            "isolated_percent": round(isolated * 100 / max(conversations_count, 1), 1),
            "header_based": header_conversations,
            "fallback_based": fallback_conversations,
            "low_confidence": low_confidence,
        },
        "isolated_conversations": isolated_examples,
        "multi_message_conversations": multi_message_examples,
        "fallback_conversations": fallback_examples,
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
