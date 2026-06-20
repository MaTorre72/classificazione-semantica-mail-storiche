from pathlib import Path

import numpy as np

from email_cluster.context.builder import SemanticContext
from email_cluster.models import ParsedEmail
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository


def test_v2_context_and_semantic_embedding_are_incremental(tmp_path) -> None:
    db = tmp_path / "repository.sqlite"
    init_db(db)
    with connect(db) as con:
        repo = Repository(con)
        project_id = repo.get_or_create_project("mail")
        source_id = repo.upsert_source_file(project_id, "inbox.mbox", "mbox", "hash", "ok")
        email_id = repo.insert_email(project_id, source_id, ParsedEmail(
            source_file=Path("inbox.mbox"), source_type="mbox", message_id="<1@test>",
            message_hash="message-hash", subject="Relazione VIA", sender="a@example.com",
            recipients=["b@example.com"], cc=[], bcc=[], sent_at=None, body_plain="Testo operativo",
            body_html=None, body_extracted_text="Testo operativo", raw_headers={},
        ))
        assert email_id is not None
        context_id = repo.insert_semantic_context(SemanticContext(
            email_id=email_id, context_version="v2", message_type="operational_email",
            message_type_confidence=0.9, context_strategy="current_plus_subject",
            thread_context_summary="", attachment_summary="", semantic_summary="",
            semantic_text_for_embedding="Relazione VIA\n\nTesto operativo sufficientemente dettagliato",
            quality_score=0.8, excluded_from_main_clustering=False, exclusion_reason=None,
        ))
        model_id = repo.get_or_create_embedding_model("test", None, 3, {})
        assert len(repo.semantic_contexts_without_embedding(project_id, model_id)) == 1
        repo.insert_semantic_embedding(email_id, context_id, model_id, np.array([1, 2, 3]))
        assert repo.semantic_contexts_without_embedding(project_id, model_id) == []
        rows = repo.semantic_embeddings_for_project(project_id)
    assert rows[0]["semantic_text"].startswith("Relazione VIA")
