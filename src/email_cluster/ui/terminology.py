from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    display: str
    description: str
    tooltip: str
    style: str = ""


TERMS = {
    "macro_category": Term(
        "Area", "Categoria generale delle email", "Categoria generale delle email"
    ),
    "operational_context": Term(
        "Insieme",
        "Gruppo di email sullo stesso tema",
        "Gruppo di email che parlano dello stesso argomento o pratica",
    ),
    "taxonomy": Term(
        "Classificazione",
        "Organizzazione di Aree, Insiemi ed Etichette",
        "Struttura modificabile della classificazione",
    ),
    "label": Term(
        "Etichetta",
        "Parola applicata a email o Insiemi",
        "Parola o categoria applicata a una o più email",
    ),
    "technical_domain": Term("Argomento", "Tema principale trattato", "Tema principale trattato"),
    "context_type": Term("Tipo di insieme", "Natura dell'Insieme", "Tipo di gruppo creato"),
    "client_or_entity": Term(
        "Cliente / Ente", "Soggetto collegato", "Cliente, ente o organizzazione coinvolta"
    ),
    "review_status": Term(
        "Stato",
        "Stato del controllo umano",
        "Indica se la classificazione è da controllare o confermata",
    ),
    "confidence": Term(
        "Affidabilità",
        "Solidità della proposta",
        "Quanto il sistema considera affidabile la proposta",
    ),
    "suggested_action": Term(
        "Azione consigliata", "Prossimo controllo utile", "Prossimo intervento consigliato"
    ),
}

STATUS_NAMES = {
    "pending": "Da controllare",
    "approved": "Confermato",
    "human_corrected": "Corretto e confermato",
    "export_ready": "Pronto per esportazione",
    "needs_attention": "Da correggere",
    "mixed": "Misto",
    "non_professional": "Non operativo",
    "noise": "Non classificato",
    "llm_suggested": "Proposta LLM da controllare",
}

AREA_NAMES = {
    "professionale_operativo": "Professionale operativo",
    "professionale_amministrativo": "Professionale amministrativo",
    "personale": "Personale",
    "automatico_account": "Automatiche / account",
    "newsletter_eventi": "Newsletter / eventi",
    "ecommerce_spedizioni": "Acquisti / spedizioni",
    "notifica_tecnica": "Notifiche tecniche",
    "non_classificato": "Non classificato",
}


def status_name(value: str | None) -> str:
    return STATUS_NAMES.get(value or "", (value or "Non definito").replace("_", " ").title())


def area_name(value: str | None) -> str:
    return AREA_NAMES.get(value or "", (value or "Non classificato").replace("_", " ").title())
