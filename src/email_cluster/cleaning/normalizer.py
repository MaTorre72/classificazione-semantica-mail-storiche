from __future__ import annotations

import re

from email_cluster.models import CleanedText


QUOTE_PATTERNS = [
    r"(?ims)^-----Original Message-----.*\Z",
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
]

SIGNATURE_PATTERNS = [
    r"(?im)^--\s*$.*\Z",
    r"(?im)^Cordiali saluti[,.\s]*\n.{0,800}\Z",
    r"(?im)^Distinti saluti[,.\s]*\n.{0,800}\Z",
    r"(?im)^Best regards[,.\s]*\n.{0,800}\Z",
]


def build_clean_text(email_id: int, text: str, version: str = "v0.1.0") -> CleanedText:
    normalized = normalize_whitespace(remove_html_artifacts(text or ""))
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
    text = re.sub(r"&nbsp;", " ", text, flags=re.I)
    text = re.sub(r"&amp;", "&", text, flags=re.I)
    text = re.sub(r"&lt;", "<", text, flags=re.I)
    text = re.sub(r"&gt;", ">", text, flags=re.I)
    return text


def remove_low_signal_lines(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if _is_low_signal_line(stripped):
            continue
        lines.append(line)
    return "\n".join(lines)


def _is_low_signal_line(line: str) -> bool:
    lowered = line.lower()
    if not line:
        return False
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
    if len(line) > 120 and len(re.findall(r"https?://|%[0-9a-f]{2}|[A-Za-z0-9]{24,}", line)) >= 2:
        return True
    return False


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
