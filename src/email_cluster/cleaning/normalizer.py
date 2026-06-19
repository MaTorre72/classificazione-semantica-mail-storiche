from __future__ import annotations

import re

from email_cluster.models import CleanedText


QUOTE_PATTERNS = [
    r"(?ims)^-----Original Message-----.*\Z",
    r"(?ims)^-----Messaggio originale-----.*\Z",
    r"(?ims)^Da:\s.+\Z",
    r"(?ims)^From:\s.+\Z",
    r"(?ims)^Inviato:\s.+\Z",
    r"(?ims)^Sent:\s.+\Z",
    r"(?ims)^Il giorno .+ ha scritto:.*\Z",
    r"(?ims)^On .+ wrote:.*\Z",
]

DISCLAIMER_PATTERNS = [
    r"(?is)Questo messaggio e i suoi allegati.*\Z",
    r"(?is)Le informazioni contenute nella presente.*\Z",
    r"(?is)This message and any attachments.*\Z",
    r"(?is)The information contained in this message.*\Z",
    r"(?is)This email is intended only for the person.*\Z",
    r"(?is)Ai sensi del regolamento.*\Z",
    r"(?is)Se non desideri ricevere.*\Z",
]

SIGNATURE_PATTERNS = [
    r"(?im)^--\s*$.*\Z",
    r"(?im)^Cordiali saluti[,.\s]*\n.{0,800}\Z",
    r"(?im)^Distinti saluti[,.\s]*\n.{0,800}\Z",
    r"(?im)^Cordialmente[,.\s]*\n.{0,1200}\Z",
    r"(?im)^Best regards[,.\s]*\n.{0,800}\Z",
    r"(?im)^Avv\.\s+.+\n.{0,1200}\Z",
    r"(?im)^Andrea Peretti\s*$.*\Z",
    r"(?im)^Marco Torresendi\s*$.*\Z",
    r"(?im)^Studio Giovanni Cadeddu\s*$.*\Z",
]


def build_clean_text(email_id: int, text: str, version: str = "v0.1.0") -> CleanedText:
    normalized = normalize_whitespace(remove_html_artifacts(text or ""))
    normalized = normalize_inline_links(normalized)
    cleaned, flags = _remove_patterns(normalized)
    cleaned = remove_low_signal_lines(cleaned)
    cleaned = normalize_whitespace(cleaned)
    return CleanedText(
        email_id=email_id,
        language=detect_language(cleaned),
        clean_text=cleaned,
        cleaning_version=version,
        cleaning_flags=flags,
    )


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def remove_html_artifacts(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"&nbsp;", " ", text, flags=re.I)
    text = re.sub(r"&amp;", "&", text, flags=re.I)
    text = re.sub(r"&lt;", "<", text, flags=re.I)
    text = re.sub(r"&gt;", ">", text, flags=re.I)
    return text


def normalize_inline_links(text: str) -> str:
    text = re.sub(r"\[cid:[^\]]+\]\s*<https?://[^>]+>", "", text, flags=re.I)
    text = re.sub(r"\[cid:[^\]]+\]", "", text, flags=re.I)
    text = re.sub(r"([^\n<>]{2,80})<https?://[^>]+>", r"\1", text)
    text = re.sub(r"<https?://[^>]+>", "", text)
    return text


def remove_low_signal_lines(text: str) -> str:
    lines: list[str] = []
    drop_rest = False
    for line in text.splitlines():
        stripped = line.strip()
        if _starts_boilerplate_block(stripped):
            drop_rest = True
        if drop_rest:
            continue
        if _is_low_signal_line(stripped):
            continue
        lines.append(line)
    return "\n".join(lines)


def _is_low_signal_line(line: str) -> bool:
    lowered = line.lower()
    if not line:
        return False
    if lowered in {">", ">>", ">>>", "--", "."}:
        return True
    if re.fullmatch(r"[_\-=–—*]{6,}", line):
        return True
    if re.fullmatch(r"https?://\S+", lowered):
        return True
    if lowered.startswith(("http://", "https://", "www.")) and len(line.split()) <= 3:
        return True
    if re.fullmatch(r"[\w.\-+]+@[\w.\-]+\.\w+", lowered):
        return True
    if lowered.startswith(("cid:", "image", "[image", "mailto:", "unsubscribe", "annulla iscrizione")):
        return True
    if "mailto:" in lowered and len(line.split()) <= 8:
        return True
    if lowered.startswith(("tel.", "tel:", "fax:", "fax ", "c.f.", "p.iva", "pec:")):
        return True
    if re.search(r"\b(tel|fax)\.?\s*\+?\d", lowered):
        return True
    if re.search(r"\b(c\.f\.|p\.iva|partita iva|codice fiscale)\b", lowered):
        return True
    if re.search(r"\b(via|viale|piazza|corso)\b.+\b\d{5}\b", lowered):
        return True
    if lowered in {
        "amazon.it",
        "altre informazioni | opzioni riunione",
        "andrea peretti",
        "associate",
        "buona giornata",
        "buongiorno",
        "buongiorno,",
        "ciao",
        "ciao,",
        "ciao marco",
        "ciao marco,",
        "consulenze tecniche ambientali",
        "cordiali saluti.",
        "cordiali saluti",
        "cubesuite",
        "cubesuite - © life3 s.r.l.",
        "fai clic qui per partecipare alla riunione",
        "grazie",
        "grazie,",
        "leggi tutto",
        "marco torresendi",
        "production manager",
        "scarica teams | partecipa sul web",
        "studio giovanni cadeddu",
    }:
        return True
    if lowered.startswith("gentile ") and len(line.split()) <= 4:
        return True
    if lowered.startswith("il team degli account"):
        return True
    if lowered.startswith("registrare l'uscita mostra questo qrcode"):
        return True
    if lowered.startswith("se non leggi correttamente questo messaggio"):
        return True
    if lowered.startswith("spett.le ") and "sei stato registrato" in lowered:
        return True
    if lowered.startswith("[immagine che contiene"):
        return True
    if lowered.startswith("non visualizzi questa email"):
        return True
    if lowered.startswith("partecipa da computer"):
        return True
    if lowered.startswith("riunione di microsoft teams"):
        return True
    if lowered.startswith("traccia il tuo pacco"):
        return True
    if re.fullmatch(r"\d+[,.]?\d*\s*(mg/kg|€|eur)?", lowered):
        return True
    if len(line) > 120 and len(re.findall(r"https?://|%[0-9a-f]{2}|[A-Za-z0-9]{24,}", line)) >= 2:
        return True
    return False


def _starts_boilerplate_block(line: str) -> bool:
    lowered = line.lower()
    starters = [
        "ai sensi del regolamento",
        "avv. ",
        "curriculum vitae",
        "if you are not the intended recipient",
        "informativa privacy",
        "le informazioni contenute nella presente",
        "per informazioni e assistenza",
        "questo messaggio e i suoi allegati",
        "se non desideri ricevere",
        "the information contained herein",
        "this email is intended only for the person",
        "vogliate prendere nota del nostro codice sdi",
    ]
    return any(lowered.startswith(starter) for starter in starters)


def _remove_patterns(text: str) -> tuple[str, dict[str, bool]]:
    flags = {
        "signature_removed": False,
        "disclaimer_removed": False,
        "quoted_reply_removed": False,
        "html_converted": False,
    }
    for pattern in QUOTE_PATTERNS:
        new = re.sub(pattern, "", text)
        flags["quoted_reply_removed"] |= new != text
        text = new
    for pattern in DISCLAIMER_PATTERNS:
        new = re.sub(pattern, "", text)
        flags["disclaimer_removed"] |= new != text
        text = new
    for pattern in SIGNATURE_PATTERNS:
        new = re.sub(pattern, "", text)
        flags["signature_removed"] |= new != text
        text = new
    return text, flags


def detect_language(text: str) -> str | None:
    lowered = f" {text[:2000].lower()} "
    italian_hits = sum(token in lowered for token in [" il ", " la ", " che ", " per ", " buongiorno "])
    english_hits = sum(token in lowered for token in [" the ", " and ", " for ", " hello ", " regards "])
    if italian_hits == english_hits == 0:
        return None
    return "it" if italian_hits >= english_hits else "en"
