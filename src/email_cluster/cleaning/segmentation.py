from __future__ import annotations

import re
from dataclasses import dataclass, field

from .patterns import DISCLAIMER_STARTS, NEWSLETTER_MARKERS, QUOTE_STARTS, SIGNATURE_STARTS, TECHNICAL_HEADER


@dataclass(slots=True)
class Segments:
    current_message: list[str] = field(default_factory=list)
    quoted_reply: list[str] = field(default_factory=list)
    forwarded_message: list[str] = field(default_factory=list)
    signature: list[str] = field(default_factory=list)
    disclaimer: list[str] = field(default_factory=list)
    automatic_footer: list[str] = field(default_factory=list)
    newsletter_footer: list[str] = field(default_factory=list)
    technical_headers: list[str] = field(default_factory=list)


def segment_body(text: str, custom_quote_patterns: list[str] | None = None) -> Segments:
    result = Segments()
    destination = result.current_message
    quote_patterns = QUOTE_STARTS + (custom_quote_patterns or [])
    for raw_line in text.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if line.startswith(">"):
            destination = result.quoted_reply
        elif any(re.search(pattern, lowered, re.I) for pattern in quote_patterns):
            forwarded = "forward" in lowered or "inoltrato" in lowered
            destination = result.forwarded_message if forwarded else result.quoted_reply
        elif any(lowered.startswith(marker) for marker in DISCLAIMER_STARTS):
            destination = result.disclaimer
        elif any(lowered.startswith(marker) for marker in SIGNATURE_STARTS) or line == "--":
            destination = result.signature
        elif any(marker in lowered for marker in NEWSLETTER_MARKERS):
            destination = result.newsletter_footer
        elif re.match(TECHNICAL_HEADER, line, re.I) and destination is not result.current_message:
            destination = result.technical_headers
        destination.append(raw_line)
    return result
