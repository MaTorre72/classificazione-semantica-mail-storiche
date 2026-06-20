from __future__ import annotations


def classify_macro(subject: str, sender: str, message_type: str, has_attachments: bool) -> tuple[str, str]:
    text = f"{subject} {sender}".lower()
    if any(token in text for token in ("amazon", "spedizione", "in consegna", "ordine", "paypal")):
        return "ecommerce_spedizioni", "acquisto, pagamento o spedizione"
    if message_type in {"newsletter"} or any(token in text for token in ("newsletter", "webinar", "evento", "corso online", "sconto", "offerta speciale", "evernote personal", "consigli per un rinnovo")):
        return "newsletter_eventi", "newsletter o comunicazione evento"
    if message_type in {"auto_generated"} or any(token in text for token in (
        "microsoft account", "google account", "password", "codice sicurezza", "concorsonline",
        "codice di verifica", "verification code", "dati di google", "applets have been",
        "sito è aggiornato", "sito e aggiornato", "wordpress", "accordo per gli utenti",
        "richiesta di condivisione", "è ora disponibile", "e ora disponibile",
    )):
        return "automatico_account", "notifica automatica o account"
    if message_type in {"delivery_notification", "pec_receipt"}:
        return "notifiche_tecniche", "ricevuta o notifica tecnica"
    if message_type == "personal_or_commercial_notification":
        return "personale", "notifica personale o commerciale"
    if any(token in text for token in ("unipolsai", "bollo auto", "inarcassa", "assicurazione")):
        return "personale", "amministrazione personale"
    if message_type in {"low_information", "short_reply"}:
        return "rumore_non_classificabile", "contenuto insufficiente"
    if any(token in text for token in ("fattura", "pagamento", "contratto", "preventivo", "amministrazione")):
        return "professionale_amministrativo", "contenuto amministrativo professionale"
    if message_type == "operational_email" or has_attachments:
        return "professionale_operativo", "contenuto operativo professionale"
    return "rumore_non_classificabile", "classificazione non affidabile"
