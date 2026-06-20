from __future__ import annotations

import sqlite3
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from email_cluster.config import LocalLlmConfig
from email_cluster.llm.cache import get_cached, save_cached
from email_cluster.llm.client import LocalLlmClient
from email_cluster.llm.prompts import PROMPT_VERSION

T = TypeVar("T", bound=BaseModel)


def validated_suggestion(con: sqlite3.Connection, prompt: str, schema: type[T], config: LocalLlmConfig, client: LocalLlmClient | None = None) -> T:
    client = client or LocalLlmClient(config)
    if config.cache_enabled:
        cached = get_cached(con, prompt, client.model_name, PROMPT_VERSION)
        if cached:
            return schema.model_validate(cached)
    last_error = ""
    for _ in range(2):
        try:
            parsed, raw, elapsed = client.generate_json(prompt)
            result = schema.model_validate(parsed)
            if config.cache_enabled:
                save_cached(con, prompt, client.model_name, PROMPT_VERSION, raw, result.model_dump(), "ok", None, elapsed)
            return result
        except (RuntimeError, ValueError, ValidationError) as exc:
            last_error = str(exc)
    save_cached(con, prompt, client.model_name, PROMPT_VERSION, "", None, "error", last_error, 0)
    raise RuntimeError(last_error)
