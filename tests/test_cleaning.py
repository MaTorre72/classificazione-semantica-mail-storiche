import pytest

from email_cluster.cleaning.normalizer import build_clean_text, clean_subject
from email_cluster.config import CleaningConfig


CFG = CleaningConfig(min_semantic_chars=20, min_unique_words=3)


def clean(subject: str, body: str, attachments: bool = False):
    return build_clean_text(1, subject=subject, body=body, has_attachments=attachments, config=CFG)


@pytest.mark.parametrize(
    ("subject", "body", "language"),
    [
        ("Relazione emissioni", "Invio la relazione aggiornata per la verifica finale.", "it"),
        ("Updated report", "Please review the updated report for our next meeting.", "en"),
    ],
)
def test_normal_operational_email(subject, body, language) -> None:
    result = clean(subject, body)
    assert result.message_type == "operational_email"
    assert result.language == language
    assert result.semantic_text.startswith(subject)
    assert not result.excluded_from_main_clustering


def test_signature_is_removed() -> None:
    result = clean("Analisi", "In allegato trovi tutti i risultati delle analisi.\nCordiali saluti\nMario Rossi\nTel. 012345")
    assert "Mario Rossi" not in result.semantic_text
    assert result.cleaning_flags["signature_removed"]


def test_disclaimer_is_removed() -> None:
    result = clean("Pratica", "La pratica e pronta per essere inviata domani.\nQuesto messaggio e i suoi allegati sono riservati.")
    assert "riservati" not in result.semantic_text
    assert result.cleaning_flags["disclaimer_removed"]


@pytest.mark.parametrize("separator", ["On Monday Mario wrote:", "Il giorno lunedi Mario ha scritto:"])
def test_reply_chain_is_removed(separator) -> None:
    result = clean("Re: Preventivo", f"Confermo il preventivo aggiornato per il nuovo impianto.\n{separator}\nVecchio testo da eliminare")
    assert "Vecchio testo" not in result.semantic_text
    assert result.cleaning_flags["quoted_reply_removed"]


def test_quoted_lines_are_removed() -> None:
    result = clean("Aggiornamento", "Procediamo con la versione aggiornata del documento.\n> precedente risposta\n> altro testo")
    assert "precedente" not in result.semantic_text


@pytest.mark.parametrize("separator", ["Inizio messaggio inoltrato:", "-----Original Message-----"])
def test_forwarded_mail_is_removed(separator) -> None:
    result = clean("Fwd: Progetto", f"Ti inoltro i documenti richiesti per completare la pratica.\n{separator}\nFrom: old@example.com\nTesto vecchio")
    assert "Testo vecchio" not in result.semantic_text


def test_newsletter_is_excluded() -> None:
    result = clean("Le offerte Amazon di oggi", "Scopri tutte le offerte selezionate per te.\nUnsubscribe")
    assert result.message_type == "newsletter"
    assert result.excluded_from_main_clustering


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("ACCETTAZIONE", "Ricevuta di accettazione del gestore di posta certificata", "pec_receipt"),
        ("Delivery Status Notification", "Mail delivery subsystem: delivery has failed", "delivery_notification"),
        ("Invito riunione", "Riunione di Microsoft Teams. Fai clic qui per partecipare", "calendar_message"),
        ("Re: conferma", "ok grazie", "short_ack"),
    ],
)
def test_non_operational_types_are_excluded(subject, body, expected) -> None:
    result = clean(subject, body)
    assert result.message_type == expected
    assert result.excluded_from_main_clustering


def test_attachment_only_is_excluded() -> None:
    result = clean("Documento", "", attachments=True)
    assert result.message_type == "attachment_only"
    assert result.excluded_from_main_clustering


def test_email_header_noise_and_date_patterns_are_removed() -> None:
    result = clean(
        "Subject: AIA data 03_2026",
        "Your reference\nSent\nCome\nAggiornamento pratica emissioni AIA.\nData 10/06/2024",
    )
    lowered = result.semantic_text.lower()
    for token in ("your", "come", "data", "sent", "subject", "03_2026", "10/06/2024"):
        assert token not in lowered
    assert "aia" in lowered
    assert "emissioni" in lowered


def test_subject_clean_removes_email_noise_tokens_and_keeps_signal() -> None:
    assert clean_subject("Re: Subject AIA sent 03_2026 data") == "AIA"


def test_cleaning_version_is_bumped_for_historical_email_rules() -> None:
    result = clean("Analisi", "Testo operativo utile per classificazione.")
    assert result.cleaning_version == "v2.1.0"
