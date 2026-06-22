from __future__ import annotations

from pathlib import Path

from email_cluster.atlas.service import (
    build_conversations,
    build_index,
    build_semantic_docs,
    discover,
    evaluate,
    export_atlas,
    extract_entities,
    inventory,
    parse_and_clean,
    review_action,
)
from email_cluster.cli.app import import_emails
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository


def _message(
    sender: str, recipient: str, subject: str, message_id: str, body: str, *, reply_to: str = ""
) -> str:
    headers = [
        f"From: {sender}",
        f"To: {recipient}",
        f"Subject: {subject}",
        f"Message-ID: <{message_id}>",
        "Date: Mon, 10 Jun 2024 10:00:00 +0200",
        "Content-Type: text/plain; charset=utf-8",
    ]
    if reply_to:
        headers.extend([f"In-Reply-To: <{reply_to}>", f"References: <{reply_to}>"])
    return "\n".join(headers) + "\n\n" + body


def create_fixture(root: Path) -> Path:
    mail = root / "email_archive_small"
    mail.mkdir(parents=True, exist_ok=True)
    messages = {
        "01_request.eml": _message(
            "cliente@tenax.it",
            "studio@example.it",
            "Registri rifiuti sede TPM",
            "m1@test",
            "Serve attivare i registri rifiuti per la sede TPM.",
        ),
        "02_reply.eml": _message(
            "studio@example.it",
            "cliente@tenax.it",
            "Re: Registri rifiuti sede TPM",
            "m2@test",
            "Procediamo con la documentazione richiesta.\n> Serve attivare i registri",
            reply_to="m1@test",
        ),
        "03_admin.eml": _message(
            "fornitore@example.com",
            "studio@example.it",
            "Fattura consulenza giugno",
            "m3@test",
            "In allegato la fattura per il pagamento.",
        ),
        "04_newsletter.eml": _message(
            "news@eventi.it",
            "studio@example.it",
            "Webinar ambientale",
            "m4@test",
            "Iscriviti al webinar. Unsubscribe",
        ),
        "05_personal.eml": _message(
            "amico@example.org",
            "studio@example.it",
            "Cena sabato",
            "m5@test",
            "Ci vediamo sabato sera?",
        ),
        "06_forward.eml": _message(
            "studio@example.it",
            "collega@example.it",
            "Fwd: Analisi emissioni",
            "m6@test",
            "Ti inoltro la relazione.\n-----Original Message-----\nVecchio testo",
        ),
    }
    for name, content in messages.items():
        (mail / name).write_text(content, encoding="utf-8")
    (mail / "07_duplicate.eml").write_text(messages["01_request.eml"], encoding="utf-8")
    return mail


def run_smoke_test(root: Path) -> dict[str, object]:
    mail = create_fixture(root)
    db = root / "atlas.sqlite"
    reports = root / "reports"
    output = root / "atlas-output"
    project = "smoke"
    inv = inventory(mail, db, project, reports)
    init_db(db)
    import_emails(source=mail, project=project, db=db, config=Path("config/default.yaml"))
    parsed = parse_and_clean(db, project, reports=reports)
    conversations = build_conversations(db, project, ["studio@example.it"], reports)
    indexed = build_index(db, project)
    entities = extract_entities(db, project, reports=reports)
    docs = build_semantic_docs(db, project)
    candidates = discover(db, project, min_conversations=1, max_categories=8, reports=reports)
    with connect(db) as con:
        pid = Repository(con).project_id(project)
        row = con.execute(
            "SELECT id FROM atlas_candidate_categories WHERE project_id=? ORDER BY conversation_count DESC LIMIT 1",
            (pid,),
        ).fetchone()
    if row:
        review_action(db, project, int(row[0]), "approve", notes="Smoke test")
    exported = export_atlas(db, project, output, public_safe=True)
    quality = evaluate(db, project, reports)
    result = {
        "inventory": inv,
        "parse": parsed,
        "conversations": conversations,
        "index": indexed,
        "entities": entities,
        "semantic_docs": docs,
        "discovery": candidates,
        "export": exported,
        "evaluation": quality,
        "reports": str(reports),
    }
    (reports / "smoke_test_report.json").write_text(
        __import__("json").dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return result
