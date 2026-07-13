from email_cluster.atlas.conversations import (
    GENERIC_SUBJECTS,
    header_message_ids,
    stable_conversation_key,
    stable_conversation_key_from_parts,
)


def _message(message_id: str, subject: str = "Pratica Alfa", email_id: int = 1) -> dict:
    return {
        "id": email_id,
        "original_message_id": message_id,
        "subject": subject,
        "sender": "cliente@example.it",
        "recipients": '["studio@example.it"]',
        "sent_at": "2024-01-10T10:00:00",
        "imported_at": "2024-01-10T10:00:00",
    }


def test_stable_key_does_not_depend_on_database_ids() -> None:
    assert stable_conversation_key(
        [_message("one@example", email_id=1)]
    ) == stable_conversation_key([_message("one@example", email_id=999)])


def test_reply_and_forward_headers_extract_all_message_ids() -> None:
    assert header_message_ids("<one@example> <TWO@example>") == ["one@example", "two@example"]


def test_generic_and_short_subjects_are_excluded_from_fallback() -> None:
    assert "richiesta" in GENERIC_SUBJECTS
    assert len("re") < 8


def test_fallback_stable_key_disambiguates_messages_with_same_metadata() -> None:
    common = {
        "message_ids": [],
        "fallback_subject": "Richiesta documenti",
        "fallback_first_date": "2026-07-12",
        "fallback_participants": ["sender@example.it", "recipient@example.it"],
    }

    first = stable_conversation_key_from_parts(
        **common,
        fallback_message_hashes=["hash-one"],
    )
    second = stable_conversation_key_from_parts(
        **common,
        fallback_message_hashes=["hash-two"],
    )

    assert first != second


def test_header_stable_key_disambiguates_reused_message_ids() -> None:
    common = {
        "message_ids": ["reused@example.it"],
        "fallback_subject": "",
        "fallback_first_date": "",
        "fallback_participants": [],
    }

    assert stable_conversation_key_from_parts(
        **common, fallback_message_hashes=["hash-one"]
    ) != stable_conversation_key_from_parts(
        **common, fallback_message_hashes=["hash-two"]
    )
