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
    conversations = read_csv(workspace / "conversations.csv")
    assert set(CONVERSATION_FIELDS) <= set(conversations[0])
    assert any(row["is_mixed_incoming_outgoing"] == "1" for row in conversations)
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
    classification = read_csv(workspace / "classification_workspace.csv")
    assert classification and set(CLASSIFICATION_FIELDS) <= set(classification[0])
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
