from __future__ import annotations

import csv
import json
import mailbox
from email.message import EmailMessage
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from email_cluster.atlas.workspace_study import (
    CLASSIFICATION_FIELDS,
    CONVERSATION_FIELDS,
    _describe_topic,
    build_atlas_from_workspace,
    export_orange_workspace,
    run_study,
)
from email_cluster.ingestion.scanner import scan_local_folder
from email_cluster.ui.app import create_app


def message(
    sender: str, recipient: str, subject: str, message_id: str, body: str, reply: str = ""
) -> EmailMessage:
    item = EmailMessage()
    item["From"] = sender
    item["To"] = recipient
    item["Subject"] = subject
    item["Message-ID"] = f"<{message_id}>"
    item["Date"] = "Mon, 10 Jun 2024 10:00:00 +0200"
    if reply:
        item["In-Reply-To"] = f"<{reply}>"
        item["References"] = f"<{reply}>"
    item.set_content(body)
    return item


def make_snapshot(root: Path) -> Path:
    snapshot = root / "thunderbird_snapshot"
    (snapshot / "Mail" / "Local Folders" / "Archivio.sbd").mkdir(parents=True)
    inbox = mailbox.mbox(snapshot / "Inbox")
    request = message(
        "cliente@azienda.it",
        "me@example.it",
        "Integrazione AUA",
        "m1@test",
        "Servono integrazioni ARPAV",
    )
    request.add_attachment(
        b"testo allegato ambientale", maintype="text", subtype="plain", filename="nota.txt"
    )
    request.add_attachment(
        b"%PDF-1.4 fittizio", maintype="application", subtype="pdf", filename="relazione.pdf"
    )
    inbox.add(request)
    inbox.add(
        message(
            "news@eventi.it",
            "me@example.it",
            "Newsletter webinar",
            "m3@test",
            "Unsubscribe webinar",
        )
    )
    inbox.add(message("a@example.it", "me@example.it", "Richiesta", "m4@test", "Pratica Alfa"))
    inbox.add(request)  # duplicate
    inbox.flush()
    inbox.close()
    sent = mailbox.mbox(snapshot / "Sent")
    reply = message(
        "me@example.it",
        "cliente@azienda.it",
        "Re: Integrazione AUA",
        "m2@test",
        "Invio integrazioni richieste",
        "m1@test",
    )
    reply.add_attachment(
        b"PK\x03\x04docx fittizio",
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="integrazione.docx",
    )
    sent.add(reply)
    sent.add(message("me@example.it", "b@example.it", "Richiesta", "m5@test", "Pratica Beta"))
    sent.flush()
    sent.close()
    local = mailbox.mbox(snapshot / "Mail" / "Local Folders" / "Archivio.sbd" / "Personale")
    local.add(
        message("amico@example.org", "me@example.it", "Cena sabato", "m6@test", "Ci vediamo sabato")
    )
    local.flush()
    local.close()
    (snapshot / "Inbox.msf").write_text("indice da ignorare", encoding="utf-8")
    return snapshot


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_scan_thunderbird_snapshot_ignores_msf(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    candidates = scan_local_folder(snapshot)
    assert {item.path.name for item in candidates} == {"Inbox", "Sent", "Personale"}
    assert all(item.file_type == "mbox" for item in candidates)


def test_study_pipeline_builds_mixed_conversations_attachments_and_workspace(
    tmp_path: Path,
) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"
    result = run_study(snapshot, workspace, attachments_text=True)
    required = {
        "input_inventory.csv",
        "messages.csv",
        "conversation_messages.csv",
        "conversations.csv",
        "attachments.csv",
        "attachment_texts.csv",
        "conversations_enriched.csv",
        "topics.csv",
        "clusters.csv",
        "entities.csv",
        "edges.csv",
        "classification_workspace.csv",
        "study_report.html",
        "workspace.json",
        "state.json",
    }
    assert required <= {path.name for path in workspace.iterdir()}
    messages = read_csv(workspace / "messages.csv")
    conversation_messages = read_csv(workspace / "conversation_messages.csv")
    assert [row["message_id"] for row in messages] == [
        row["message_id"] for row in conversation_messages
    ]
    conversations = read_csv(workspace / "conversations.csv")
    assert set(CONVERSATION_FIELDS) <= set(conversations[0])
    assert any(row["is_mixed_incoming_outgoing"] == "1" for row in conversations)
    assert any(row["scope_reason"] for row in conversations)
    assert all(row["scope_confidence"] for row in conversations)
    assert result["sent"] > 0 and result["received"] > 0
    generic = [row for row in conversations if row["subject_normalized"].lower() == "richiesta"]
    assert len(generic) == 2
    attachments = read_csv(workspace / "attachments.csv")
    assert {row["filename"] for row in attachments} >= {
        "nota.txt",
        "relazione.pdf",
        "integrazione.docx",
    }
    assert any(row["attachment_text_available"] == "1" for row in attachments)
    entities = read_csv(workspace / "entities.csv")
    assert any(
        row["entity_type"] == "domain" and row["entity"] == "example.it"
        for row in entities
    )
    classification = read_csv(workspace / "classification_workspace.csv")
    assert classification and set(CLASSIFICATION_FIELDS) <= set(classification[0])
    assert any(row["proposed_scope"] != "Da definire" for row in classification)
    assert any("Scope preliminare:" in row["why_it_exists"] for row in classification)
    assert "Risultato fragile" not in (workspace / "study_report.html").read_text(encoding="utf-8")
    assert (
        json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))["local_only"] is True
    )


def test_pipeline_rerun_empty_workspace_atlas_and_orange(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"
    run_study(snapshot, workspace, attachments_text=False)
    second = run_study(snapshot, workspace, attachments_text=False)
    assert second["conversations"] > 0
    report = (workspace / "study_report.html").read_text(encoding="utf-8")
    assert "3 file MBOX/EML." in report
    rows = read_csv(workspace / "classification_workspace.csv")
    rows[0]["human_decision"] = "approve"
    rows[0]["final_name"] = "Autorizzazioni ambientali"
    with (workspace / "classification_workspace.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=CLASSIFICATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    atlas = build_atlas_from_workspace(workspace)
    assert {"atlas_final.xlsx", "atlas_final.yaml", "atlas_final.html"} <= set(atlas["files"])
    export_orange_workspace(workspace)
    assert "orange_topics.csv" in {path.name for path in (workspace / "orange").iterdir()}
    workflows = (workspace / "orange" / "orange_workflow_suggestions.md").read_text(
        encoding="utf-8"
    )
    assert all(
        label in workflows
        for label in (
            "Workflow 1 - Mappa conversazioni",
            "Workflow 2 - Topic testuali",
            "Workflow 3 - Document Map",
            "Workflow 4 - Reti",
        )
    )


def test_study_stages_can_stop_resume_and_record_stage_state(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"
    first = run_study(snapshot, workspace, stages=["scan_input"], attachments_text=False)
    assert first["completed_stages"] == ["scan_input"]
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    assert state["selected_targets"] == ["scan_input"]
    assert state["stages"]["scan_input"] == "completed"
    assert "import_mbox" not in state["stages"] or state["stages"]["import_mbox"] != "completed"

    second = run_study(snapshot, workspace, stages=["build_semantic_text"], attachments_text=False)
    assert second["completed_stages"][-1] == "build_semantic_text"
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    assert state["selected_targets"] == ["build_semantic_text"]
    assert state["stage_details"]["scan_input"]["skipped_via_resume"] is True
    assert state["stage_details"]["build_semantic_text"]["status"] == "completed"
    assert "topic_discovery" not in state["stages"] or state["stages"]["topic_discovery"] != "completed"


def test_attachment_text_stage_can_resume_without_reimporting_messages(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"

    first = run_study(snapshot, workspace, attachments_text=False)
    assert "attachment_texts.csv" not in first["files"]
    attachments = read_csv(workspace / "attachments.csv")
    assert attachments
    assert all(row["extraction_status"] == "metadata_only" for row in attachments)
    assert all(row["attachment_text_available"] == "0" for row in attachments)

    second = run_study(snapshot, workspace, attachments_text=True)
    assert second["conversations"] > 0
    attachments = read_csv(workspace / "attachments.csv")
    assert any(row["attachment_text_available"] == "1" for row in attachments)
    assert (workspace / "attachment_texts.csv").exists()

    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    assert state["options"]["attachments_text"] is True
    assert state["stage_details"]["import_mbox"]["skipped_via_resume"] is True
    assert state["stage_details"]["extract_attachment_text_optional"]["skipped_via_resume"] is False
    assert state["stage_details"]["extract_attachment_text_optional"]["invalidated_reason"].startswith(
        "configurazione allegati cambiata:"
    )


def test_rebuild_stage_invalidates_downstream_without_opening_second_front(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"
    run_study(snapshot, workspace, attachments_text=False)

    rerun = run_study(
        snapshot,
        workspace,
        stages=["build_classification_workspace"],
        rebuild_stage="build_conversations",
        attachments_text=False,
    )
    assert rerun["completed_stages"][-1] == "build_classification_workspace"
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    assert state["stage_details"]["parse_messages"]["skipped_via_resume"] is True
    assert state["stage_details"]["build_conversations"]["skipped_via_resume"] is False
    assert state["stage_details"]["build_conversations"]["invalidated_reason"].startswith(
        "richiesto rebuild-stage="
    )
    assert state["stages"]["generate_report"] == "pending"
    assert (workspace / "classification_workspace.csv").exists()


def test_invalid_input_and_empty_workspace_are_readable(tmp_path: Path) -> None:
    try:
        run_study(tmp_path / "missing", tmp_path / "workspace")
    except ValueError as exc:
        assert "Input non valido" in str(exc)
    else:
        raise AssertionError("invalid input accepted")
    try:
        build_atlas_from_workspace(tmp_path / "empty")
    except (FileNotFoundError, ValueError):
        pass
    else:
        raise AssertionError("empty workspace accepted")


def test_minimal_gui_runs_the_workspace_pipeline(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "gui-workspace"
    db = tmp_path / "gui.sqlite"
    config = tmp_path / "config.yaml"
    config.write_text(yaml.safe_dump({"database": {"path": str(db)}}), encoding="utf-8")
    client = TestClient(create_app(db, "archivio_storico", config))
    home = client.get("/")
    assert home.status_code == 200
    assert "Studio snapshot Thunderbird / MBOX" in home.text
    assert "Crea o aggiorna studio" in home.text
    response = client.post(
        "/api/atlas/run/workspace_study",
        json={
            "input_path": str(snapshot),
            "workspace": str(workspace),
            "attachments_text": False,
            "max_attachment_mb": 10,
        },
    )
    assert response.status_code == 200
    assert response.json()["conversations"] > 0
    assert (workspace / "study_report.html").exists()


def test_topic_labels_exclude_email_stopwords_and_date_patterns(tmp_path: Path) -> None:
    snapshot = tmp_path / "topic-noise"
    snapshot.mkdir()
    inbox = mailbox.mbox(snapshot / "Inbox")
    inbox.add(
        message(
            "cliente@azienda.it",
            "me@example.it",
            "Subject AIA sent 03_2026 data",
            "noise-1@test",
            "Aggiornamento pratica AIA con emissioni convogliate.",
        )
    )
    inbox.add(
        message(
            "cliente@azienda.it",
            "me@example.it",
            "Re: Subject AIA sent 03_2026 data",
            "noise-2@test",
            "Ulteriore dettaglio tecnico su emissioni e autorizzazione.",
            "noise-1@test",
        )
    )
    inbox.flush()
    inbox.close()

    workspace = tmp_path / "workspace"
    run_study(snapshot, workspace, attachments_text=False)
    topics = read_csv(workspace / "topics.csv")
    assert topics
    labels = " ".join(row["label"].lower() for row in topics)
    for token in ("subject", "sent", "data", "03_2026"):
        assert token not in labels
    assert "pratiche ambientali / autorizzazioni" in labels


def test_scope_classification_populates_scope_confidence_and_reason(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"

    run_study(snapshot, workspace, attachments_text=False)

    conversations = read_csv(workspace / "conversations.csv")
    scopes = {row["subject_normalized"].lower(): row for row in conversations}
    assert scopes["newsletter webinar"]["probable_scope"] == "Newsletter / eventi"
    assert scopes["newsletter webinar"]["scope_reason"].startswith("Segnali:")
    assert float(scopes["newsletter webinar"]["scope_confidence"]) >= 0.9
    assert scopes["cena sabato"]["probable_scope"] == "Personale / relazioni"
    assert float(scopes["integrazione aua"]["scope_confidence"]) >= 0.8

    classification = read_csv(workspace / "classification_workspace.csv")
    assert classification
    assert all(row["proposed_scope"] != "Da definire" for row in classification)
    assert len({row["proposed_scope"] for row in classification}) >= 2
    assert any("Scope reason:" in row["notes"] for row in classification)


def test_describe_topic_maps_known_signals_to_revision_friendly_categories() -> None:
    account_topic = _describe_topic(
        [
            {
                "id": 1,
                "subject_normalized": "GitHub security alert",
                "semantic_text": "GitHub account login verification and password reset.",
                "probable_scope": "Account / notifiche tecniche",
                "scope_confidence": 0.9,
                "scope_reason": "Segnali: github, login",
                "domains": ["github.com"],
                "attachments": [],
            },
            {
                "id": 2,
                "subject_normalized": "Google account verification",
                "semantic_text": "Google account access code and security verification.",
                "probable_scope": "Account / notifiche tecniche",
                "scope_confidence": 0.88,
                "scope_reason": "Segnali: google, account",
                "domains": ["google.com"],
                "attachments": [],
            },
        ],
        main_terms=["github", "google", "account"],
        fallback_label="github / google / account",
    )
    assert account_topic["label"] == "Account / notifiche tecniche"
    assert "Segnali:" in account_topic["label_reason"]

    admin_topic = _describe_topic(
        [
            {
                "id": 3,
                "subject_normalized": "Fattura consulenza giugno",
                "semantic_text": "Invio fattura e coordinate per il pagamento del fornitore.",
                "probable_scope": "Amministrativo / fornitori",
                "scope_confidence": 0.87,
                "scope_reason": "Segnali: fattura, pagamento",
                "domains": ["fornitore.it"],
                "attachments": ["fattura-giugno.pdf"],
            }
        ],
        main_terms=["fattura", "pagamento", "fornitore"],
        fallback_label="fattura / pagamento / fornitore",
    )
    assert admin_topic["label"] == "Amministrazione / fatture e pagamenti"

    pec_topic = _describe_topic(
        [
            {
                "id": 4,
                "subject_normalized": "ACCETTAZIONE PEC Hiro",
                "semantic_text": "Ricevuta di accettazione postacert con protocollo Hiro.",
                "probable_scope": "Professionale generale",
                "scope_confidence": 0.5,
                "scope_reason": "Fallback prudente",
                "domains": ["postacert.it"],
                "attachments": ["daticert.xml", "ricevuta.eml"],
            }
        ],
        main_terms=["pec", "hiro", "accettazione"],
        fallback_label="pec / hiro / accettazione",
    )
    assert pec_topic["label"] == "PEC / Hiro e notifiche collegate"


def test_study_topics_csv_exposes_revision_friendly_labels_and_reasons(tmp_path: Path) -> None:
    snapshot = tmp_path / "topic-categories"
    snapshot.mkdir()
    inbox = mailbox.mbox(snapshot / "Inbox")
    inbox.add(
        message(
            "noreply@github.com",
            "me@example.it",
            "GitHub security alert",
            "cat-1@test",
            "GitHub account login verification and password reset.",
        )
    )
    inbox.add(
        message(
            "accounts@google.com",
            "me@example.it",
            "Google account verification",
            "cat-2@test",
            "Google account access code and security verification.",
        )
    )
    inbox.add(
        message(
            "fornitore@example.com",
            "me@example.it",
            "Fattura consulenza giugno",
            "cat-3@test",
            "Invio fattura e coordinate per il pagamento del fornitore.",
        )
    )
    inbox.add(
        message(
            "gestore@postacert.it",
            "me@example.it",
            "ACCETTAZIONE PEC Hiro",
            "cat-4@test",
            "Ricevuta di accettazione postacert con protocollo Hiro.",
        )
    )
    inbox.flush()
    inbox.close()

    workspace = tmp_path / "workspace"
    run_study(snapshot, workspace, attachments_text=False)

    topics = read_csv(workspace / "topics.csv")
    assert topics
    labels = {row["label"] for row in topics}
    assert "Account / notifiche tecniche" in labels
    assert "Amministrazione / fatture e pagamenti" in labels or "PEC / Hiro e notifiche collegate" in labels
    assert all(row["label_reason"] for row in topics)

    classification = read_csv(workspace / "classification_workspace.csv")
    assert classification
    assert any("Categoria proposta:" in row["why_it_exists"] for row in classification)
    assert all(row["proposed_activity"] != row["proposed_name"] for row in classification)
    assert all(row["proposed_theme"] != row["proposed_name"] for row in classification)
    assert all("Esempi:" in row["description"] for row in classification)
    assert {row["suggested_decision"] for row in classification} <= {"approve", "exclude", "unclear"}


def test_classification_suggestions_use_examples_and_non_copied_fields(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"

    run_study(snapshot, workspace, attachments_text=False)

    classification = read_csv(workspace / "classification_workspace.csv")
    assert classification
    assert all(row["proposed_scope"] != "Da definire" for row in classification)
    assert all(row["proposed_activity"] != row["proposed_name"] for row in classification)
    assert all(row["proposed_theme"] != row["proposed_name"] for row in classification)
    assert all("Esempi:" in row["description"] for row in classification)
    assert any("Suggested decision:" in row["notes"] for row in classification)


def test_study_report_declares_attachment_state_topic_method_and_fallback(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"

    run_study(snapshot, workspace, attachments_text=False)

    report = (workspace / "study_report.html").read_text(encoding="utf-8")
    assert "Stato allegati" in report
    assert "Metodo topic" in report
    assert "TF-IDF + SVD + KMeans" in report
    assert "Testo allegati non analizzato; sono disponibili solo i metadati." in report
    assert "Rumore/newsletter probabile:" in report
    assert "Personale probabile:" in report
    assert "classification_workspace.csv" in report
    assert "topics.csv" in report


def test_sample_size_limits_imported_messages_but_keeps_valid_workspace_outputs(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"

    result = run_study(snapshot, workspace, attachments_text=False, sample_size=3)

    messages = read_csv(workspace / "messages.csv")
    conversations = read_csv(workspace / "conversations.csv")
    manifest = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))

    assert len(messages) == 3
    assert 1 <= len(conversations) <= 3
    assert result["conversations"] == len(conversations)
    assert manifest["sample_size"] == 3
    assert state["options"]["sample_size"] == 3
    assert any("Campione limitato a 3 messaggi importati" in warning for warning in result["warnings"])
    assert (workspace / "study_report.html").exists()


def test_limit_conversations_trims_workspace_outputs_and_invalidates_resume(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"

    first = run_study(snapshot, workspace, attachments_text=False, limit_conversations=2)

    conversations = read_csv(workspace / "conversations.csv")
    messages = read_csv(workspace / "messages.csv")
    attachments = read_csv(workspace / "attachments.csv")
    manifest = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))

    assert len(conversations) == 2
    allowed_ids = {row["conversation_id"] for row in conversations}
    assert allowed_ids
    assert all(row["conversation_id"] in allowed_ids for row in messages)
    assert all(row["conversation_id"] in allowed_ids for row in attachments)
    nodes = read_csv(workspace / "nodes.csv")
    edges = read_csv(workspace / "edges.csv")
    conversation_node_ids = {
        row["node_id"] for row in nodes if row["node_type"] == "conversation"
    }
    assert conversation_node_ids == {f"conversation:{conversation_id}" for conversation_id in allowed_ids}
    assert all(
        edge["target"] in conversation_node_ids
        for edge in edges
        if edge["target_type"] == "conversation"
    )
    assert manifest["limit_conversations"] == 2
    assert state["options"]["limit_conversations"] == 2
    assert any(
        "Analisi limitata alle prime 2 conversazioni ricostruite" in warning
        for warning in first["warnings"]
    )

    second = run_study(snapshot, workspace, attachments_text=False, limit_conversations=4)
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))

    assert len(read_csv(workspace / "conversations.csv")) == 4
    assert state["stage_details"]["parse_messages"]["skipped_via_resume"] is True
    assert state["stage_details"]["build_conversations"]["skipped_via_resume"] is False
    assert state["stage_details"]["build_conversations"]["invalidated_reason"].startswith(
        "limite conversazioni cambiato:"
    )
    assert any(
        "Analisi limitata alle prime 4 conversazioni ricostruite" in warning
        for warning in second["warnings"]
    )


def test_limit_messages_trims_workspace_message_exports_and_invalidates_resume(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"

    first = run_study(snapshot, workspace, attachments_text=False, limit_messages=2)

    messages = read_csv(workspace / "messages.csv")
    conversation_messages = read_csv(workspace / "conversation_messages.csv")
    attachments = read_csv(workspace / "attachments.csv")
    manifest = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))

    assert len(messages) == 2
    assert len(conversation_messages) == 2
    allowed_message_ids = {row["message_id"] for row in messages}
    assert allowed_message_ids
    assert all(row["message_id"] in allowed_message_ids for row in conversation_messages)
    assert all(row["email_id"] in allowed_message_ids for row in attachments)
    assert manifest["limit_messages"] == 2
    assert state["options"]["limit_messages"] == 2
    assert any(
        "Export workspace limitato ai primi 2 messaggi" in warning
        for warning in first["warnings"]
    )

    second = run_study(snapshot, workspace, attachments_text=False, limit_messages=4)
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))

    assert len(read_csv(workspace / "messages.csv")) == 4
    assert state["stage_details"]["parse_messages"]["skipped_via_resume"] is True
    assert state["stage_details"]["build_conversations"]["skipped_via_resume"] is False
    assert state["stage_details"]["build_conversations"]["invalidated_reason"].startswith(
        "limite messaggi cambiato:"
    )
    assert any(
        "Export workspace limitato ai primi 4 messaggi" in warning
        for warning in second["warnings"]
    )


def test_date_and_source_folder_filters_are_persisted_and_invalidate_exports(tmp_path: Path) -> None:
    snapshot = make_snapshot(tmp_path)
    workspace = tmp_path / "workspace"

    run_study(
        snapshot,
        workspace,
        attachments_text=False,
        date_from="2024-06-01",
        date_to="2024-06-30",
        source_folders=("Inbox",),
    )

    first_conversations = read_csv(workspace / "conversations.csv")
    first_manifest = json.loads((workspace / "workspace.json").read_text(encoding="utf-8"))
    assert first_conversations
    assert all(row["date_start"].startswith("2024-06") for row in first_conversations)
    assert first_manifest["date_from"] == "2024-06-01"
    assert first_manifest["date_to"] == "2024-06-30"
    assert first_manifest["source_folders"] == ["Inbox"]

    run_study(
        snapshot,
        workspace,
        attachments_text=False,
        date_from="2024-06-01",
        date_to="2024-06-30",
        source_folders=("Personale",),
    )

    second_conversations = read_csv(workspace / "conversations.csv")
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    assert {row["subject_normalized"] for row in second_conversations} == {"Cena sabato"}
    assert state["options"]["source_folders"] == ["Personale"]
    assert state["stage_details"]["build_conversations"]["skipped_via_resume"] is False
    assert state["stage_details"]["build_conversations"]["invalidated_reason"].startswith(
        "filtri data o cartella cambiati:"
    )
