from __future__ import annotations

import re
from pathlib import Path

CATEGORIES = {
    "relazione_tecnica": ("relazione", "report", "via", "seveso"),
    "rapporto_di_prova": ("rapporto di prova", "rdp", "prova"),
    "analisi_laboratorio": ("analisi", "laboratorio", "campione"),
    "autorizzazione": ("autorizzazione", "aua", "aia"),
    "verbale": ("verbale", "udienza"),
    "planimetria": ("planimetria", "tavola", "layout"),
    "fattura": ("fattura", "invoice"),
    "offerta": ("offerta", "preventivo", "quotation"),
    "contratto": ("contratto", "contract"),
    "formulario_fir": ("formulario", "fir"),
    "mud": ("mud",),
    "visura": ("visura",),
    "protocollo_pec": ("daticert", "postacert", "smime", "pec"),
}


def classify_attachment(filename: str | None) -> tuple[str, list[str]]:
    stem = Path(filename or "").stem.lower()
    words = [word for word in re.findall(r"[a-zà-ÿ]{3,}", stem) if word not in {"doc", "file", "scan"}]
    normalized = " ".join(words)
    for category, markers in CATEGORIES.items():
        if any(marker in normalized for marker in markers):
            return category, words[:12]
    return "altro", words[:12]
