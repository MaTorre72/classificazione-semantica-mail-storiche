from pathlib import Path

from typer.testing import CliRunner

from email_cluster.cli.app import app
from email_cluster.operational.builder import build_operational_contexts
from email_cluster.operational.export import export_context_report
from email_cluster.operational.macro import classify_macro
from email_cluster.operational.service import move_email, update_context
from email_cluster.storage.database import connect
from email_cluster.storage.repository import utcnow
from tests.test_review_v3 import make_review_db


def add_nonprofessional_email(db: Path) -> None:
    with connect(db) as con:
        con.execute("""INSERT INTO emails(id,project_id,message_hash,subject,sender,imported_at,parse_status) VALUES(3,1,'h3','Il tuo ordine Amazon è stato spedito','store@amazon.it',?,'ok')""", (utcnow(),))
        con.execute("""INSERT INTO semantic_contexts(id,email_id,context_version,message_type,message_type_confidence,context_strategy,semantic_text_for_embedding,quality_score,excluded_from_main_clustering,created_at) VALUES(3,3,'v3','personal_or_commercial_notification',0.9,'exclude_from_main_clustering','Ordine Amazon',0.8,1,?)""", (utcnow(),))


def test_macro_separation_prevents_professional_contamination(tmp_path) -> None:
    db = tmp_path / "contexts.sqlite"
    make_review_db(db)
    add_nonprofessional_email(db)
    with connect(db) as con:
        result = build_operational_contexts(con, 1, 1)
        macros = {row["macro_category"] for row in con.execute("SELECT * FROM operational_contexts")}
        mixed = con.execute("""
            SELECT count(*) FROM operational_contexts oc JOIN email_context_assignments eca ON eca.operational_context_id=oc.id
            WHERE oc.macro_category LIKE 'professionale%' AND eca.macro_category='ecommerce_spedizioni'
        """).fetchone()[0]
    assert result["assignments"] == 3
    assert "ecommerce_spedizioni" in macros
    assert mixed == 0


def test_context_actions_and_export(tmp_path) -> None:
    db = tmp_path / "actions.sqlite"
    make_review_db(db)
    with connect(db) as con:
        build_operational_contexts(con, 1, 1)
        contexts = list(con.execute("SELECT id FROM operational_contexts ORDER BY id"))
        first = int(contexts[0]["id"])
        update_context(con, first, "rename", name="Cliente — pratica emissioni", source="human", review_status="approved")
        move_email(con, 2, first)
        output = tmp_path / "report.html"
        count = export_context_report(con, 1, output, "html")
        row = con.execute("SELECT * FROM operational_contexts WHERE id=?", (first,)).fetchone()
        events = con.execute("SELECT count(*) FROM context_review_events").fetchone()[0]
    assert row["name"] == "Cliente — pratica emissioni"
    assert row["review_status"] == "approved"
    assert events >= 2
    assert count == 2
    assert "Contesti operativi" in output.read_text(encoding="utf-8")


def test_macro_classifier_examples() -> None:
    assert classify_macro("Bollo auto", "x@unipol.it", "operational_email", False)[0] == "personale"
    assert classify_macro("Ordine spedito", "x@amazon.it", "personal_or_commercial_notification", False)[0] == "ecommerce_spedizioni"
    assert classify_macro("Analisi camini", "a@tenax.it", "operational_email", True)[0] == "professionale_operativo"
    assert classify_macro("I tuoi dati di Google sono pronti", "x@google.com", "operational_email", False)[0] == "automatico_account"
    assert classify_macro("50% di sconto Evernote Personal", "x@evernote.com", "operational_email", False)[0] == "newsletter_eventi"


def test_workbench_cli_guides_one_next_action(tmp_path) -> None:
    db = tmp_path / "workbench.sqlite"
    make_review_db(db)
    result = CliRunner().invoke(app, ["workbench", "--project", "studio", "--db", str(db)])
    assert result.exit_code == 0
    assert "STATO ARCHIVIO" in result.stdout
    assert "PROSSIMA AZIONE CONSIGLIATA" in result.stdout
