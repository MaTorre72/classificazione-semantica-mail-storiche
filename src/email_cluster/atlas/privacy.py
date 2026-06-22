from __future__ import annotations

from typing import Any


def public_safe_category(row: dict[str, Any]) -> dict[str, Any]:
    """Remove identity-bearing fields from an Atlas export record."""
    safe = dict(row)
    safe["soggetto_nome"] = None
    safe["contesto_nome"] = None
    safe["mittenti_ricorrenti"] = []
    safe["domini_ricorrenti"] = []
    return safe
