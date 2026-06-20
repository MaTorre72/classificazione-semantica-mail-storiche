from pathlib import Path

import numpy as np
from typer.testing import CliRunner

from email_cluster.active_learning.engine import apply_rules, suggest_from_examples
from email_cluster.cli.app import app
from email_cluster.llm.review_assistant import validated_suggestion
from email_cluster.llm.schemas import ClusterReviewSuggestion
from email_cluster.config import LocalLlmConfig
from email_cluster.review.repository import ReviewRepository
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import embedding_to_blob, utcnow


def make_review_db(path: Path) -> None:
    init_db(path)
    with connect(path) as con:
        con.execute("INSERT INTO projects(id,name,created_at) VALUES(1,'studio',?)", (utcnow(),))
        con.execute("INSERT INTO embedding_models(id,model_name,embedding_dimension,parameters_json,created_at) VALUES(1,'test',3,'{}',?)", (utcnow(),))
        con.execute("""INSERT INTO clustering_runs(id,project_id,embedding_model_id,umap_parameters_json,hdbscan_parameters_json,started_at,status,total_emails_considered,total_clusters) VALUES(1,1,1,'{}','{}',?,'completed',2,1)""", (utcnow(),))
        con.execute("""INSERT INTO clusters(clustering_run_id,cluster_id,label_auto,keywords_json,representative_email_ids_json,size,coherence_score,mean_probability,recurring_senders_json,created_at) VALUES(1,0,'Analisi camini','[\"camini\"]','[1]',2,0.5,0.7,'[\"tenax.it\"]',?)""", (utcnow(),))
        for email_id, sender, subject, vector in (
            (1, "a@tenax.it", "Analisi camino", [1.0, 0.0, 0.0]),
            (2, "b@example.com", "Fattura", [0.9, 0.1, 0.0]),
        ):
            con.execute("""INSERT INTO emails(id,project_id,message_hash,subject,sender,imported_at,parse_status) VALUES(?,?,?,?,?,?,'ok')""", (email_id,1,f'h{email_id}',subject,sender,utcnow()))
            con.execute("""INSERT INTO semantic_contexts(id,email_id,context_version,message_type,message_type_confidence,context_strategy,semantic_text_for_embedding,quality_score,created_at) VALUES(?,?,?,?,?,'current_plus_subject',?,0.8,?)""", (email_id,email_id,'v3','operational_email',0.9,subject,utcnow()))
            con.execute("INSERT INTO semantic_embeddings(email_id,semantic_context_id,model_id,embedding,created_at) VALUES(?,?,?,?,?)", (email_id,email_id,1,embedding_to_blob(np.array(vector)),utcnow()))
            con.execute("INSERT INTO email_clusters(clustering_run_id,email_id,cluster_id,probability,is_noise) VALUES(1,?,?,0.7,0)", (email_id,0))


def test_review_session_actions_and_taxonomy(tmp_path) -> None:
    db = tmp_path / "review.sqlite"
    make_review_db(db)
    with connect(db) as con:
        repo = ReviewRepository(con)
        session = repo.start_session(1, 1, "Test")
        repo.update_cluster(session, 0, "renamed", label="Emissioni camini")
        repo.update_cluster(session, 0, "mixed", notes="Temi eterogenei", action="inspect_emails")
        repo.update_email(session, 2, "moved", cluster_id=0, label="Amministrazione")
        label_id = repo.add_taxonomy_label(1, "Emissioni", "tema_tecnico")
        repo.add_example(label_id, 1, "positive")
        repo.add_example(label_id, 2, "negative")
        repo.add_rule(1, label_id, "sender_domain", "tenax.it")
        cluster = con.execute("SELECT * FROM cluster_reviews WHERE review_session_id=?", (session,)).fetchone()
        email = con.execute("SELECT * FROM email_reviews WHERE review_session_id=? AND email_id=2", (session,)).fetchone()
        rules = apply_rules(con, 1)
    assert cluster["final_label"] == "Emissioni camini"
    assert email["review_status"] == "moved"
    assert rules[0]["email_id"] == 1


def test_active_learning_uses_positive_and_negative_examples(tmp_path) -> None:
    db = tmp_path / "learning.sqlite"
    make_review_db(db)
    with connect(db) as con:
        repo = ReviewRepository(con)
        label_id = repo.add_taxonomy_label(1, "Emissioni", "tema_tecnico")
        repo.add_example(label_id, 1, "positive")
        suggestions = suggest_from_examples(con, 1, threshold=0.5)
    assert any(item["label"] == "Emissioni" for item in suggestions)


class FakeClient:
    model_name = "fake"

    def generate_json(self, prompt):
        return {"cluster_label": "Emissioni", "cluster_summary": "Analisi tecniche", "confidence": 0.9}, '{"ok":true}', 5


class InvalidClient:
    model_name = "invalid"

    def generate_json(self, prompt):
        return {"confidence": "non-un-numero"}, "invalid", 5


def test_llm_validation_and_cache_with_fake(tmp_path) -> None:
    db = tmp_path / "llm.sqlite"
    init_db(db)
    cfg = LocalLlmConfig(enabled=True, cache_enabled=True)
    with connect(db) as con:
        result = validated_suggestion(con, "prompt", ClusterReviewSuggestion, cfg, FakeClient())
        cached = con.execute("SELECT status FROM llm_cache").fetchone()
    assert result.cluster_label == "Emissioni"
    assert cached["status"] == "ok"


def test_llm_invalid_output_is_cached_as_error(tmp_path) -> None:
    db = tmp_path / "invalid-llm.sqlite"
    init_db(db)
    cfg = LocalLlmConfig(enabled=True, cache_enabled=True)
    with connect(db) as con:
        try:
            validated_suggestion(con, "bad prompt", ClusterReviewSuggestion, cfg, InvalidClient())
        except RuntimeError:
            pass
        cached = con.execute("SELECT status FROM llm_cache").fetchone()
    assert cached["status"] == "error"


def test_review_cli_start_dashboard_and_export(tmp_path) -> None:
    db = tmp_path / "cli.sqlite"
    make_review_db(db)
    runner = CliRunner()
    started = runner.invoke(app, ["review-start", "--project", "studio", "--run", "latest", "--db", str(db)])
    assert started.exit_code == 0
    dashboard = runner.invoke(app, ["review-dashboard", "--session", "1", "--db", str(db)])
    assert dashboard.exit_code == 0
    assert "pending" in dashboard.stdout
    output = tmp_path / "final.csv"
    exported = runner.invoke(app, ["export-final-dataset", "--session", "1", "--output", str(output), "--db", str(db)])
    assert exported.exit_code == 0
    assert output.exists()
