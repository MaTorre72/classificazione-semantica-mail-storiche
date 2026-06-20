from email_cluster.attachments.classifier import classify_attachment
from email_cluster.attachments.extractor import extract_attachment_text
from email_cluster.config import LocalLlmConfig, SemanticPreparationConfig
from email_cluster.context.builder import build_context
from email_cluster.llm.local import enrich_locally


CFG = SemanticPreparationConfig(min_semantic_chars=40, min_unique_words=5)


def test_context_uses_current_message() -> None:
    context = build_context(
        1, "Analisi emissioni", "Invio i risultati aggiornati delle analisi al camino principale.",
        "", "operational_email", "", CFG,
    )
    assert context.context_strategy == "current_plus_subject"
    assert "risultati aggiornati" in context.semantic_text_for_embedding
    assert not context.excluded_from_main_clustering


def test_context_recovers_short_reply_from_thread() -> None:
    context = build_context(
        1, "Autorizzazione impianto", "Ok grazie", "La provincia richiede integrazioni tecniche per autorizzare il nuovo impianto produttivo.",
        "short_ack", "", CFG,
    )
    assert context.context_strategy == "thread_dominant"
    assert "provincia" in context.semantic_text_for_embedding.lower()


def test_context_uses_attachment_when_email_is_poor() -> None:
    context = build_context(
        1, "Aggiornamento VIA", "In allegato aggiornamento odierno", "", "attachment_only",
        "Allegato relazione_tecnica: report_VIA_SEVESO_Tenax_2024.pdf", CFG,
    )
    assert context.context_strategy == "attachment_dominant"
    assert "VIA_SEVESO" in context.semantic_text_for_embedding


def test_context_excludes_newsletter() -> None:
    context = build_context(1, "Offerte", "Scopri le offerte del mese", "", "newsletter", "", CFG)
    assert context.excluded_from_main_clustering
    assert context.context_strategy == "exclude_from_main_clustering"


def test_attachment_classification_and_txt_extraction() -> None:
    kind, keywords = classify_attachment("relazione_VIA_SEVESO_2024.txt")
    text, status, error = extract_attachment_text(b"Relazione tecnica impianto", "relazione.txt", "text/plain")
    assert kind == "relazione_tecnica"
    assert "relazione" in keywords
    assert text == "Relazione tecnica impianto"
    assert status == "extracted"
    assert error is None


def test_local_llm_disabled_and_missing_model_fall_back() -> None:
    result, used, error = enrich_locally("test", LocalLlmConfig(enabled=False))
    assert result == {} and not used and error is None
    result, used, error = enrich_locally("test", LocalLlmConfig(enabled=True, model_path="missing.gguf"))
    assert result == {} and not used and "non disponibile" in error
