from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from email_cluster.storage.repository import utcnow


def cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def get_cached(con: sqlite3.Connection, text: str, model: str, prompt_version: str) -> dict[str, Any] | None:
    row = con.execute("SELECT parsed_output_json FROM llm_cache WHERE input_hash=? AND model=? AND prompt_version=? AND status='ok'", (cache_key(text), model, prompt_version)).fetchone()
    return json.loads(row["parsed_output_json"]) if row else None


def save_cached(con: sqlite3.Connection, text: str, model: str, prompt_version: str, raw: str, parsed: dict[str, Any] | None, status: str, error: str | None, elapsed_ms: int) -> None:
    con.execute("""
        INSERT OR REPLACE INTO llm_cache (input_hash, model, prompt_version, input_excerpt, raw_output,
            parsed_output_json, status, error, elapsed_ms, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cache_key(text), model, prompt_version, text[:500], raw, json.dumps(parsed, ensure_ascii=False) if parsed else None, status, error, elapsed_ms, utcnow()))
