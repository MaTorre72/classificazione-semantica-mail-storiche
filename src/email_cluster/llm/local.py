from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any

from email_cluster.config import LocalLlmConfig


def enrich_locally(text: str, config: LocalLlmConfig) -> tuple[dict[str, Any], bool, str | None]:
    if not config.enabled:
        return {}, False, None
    model_path = Path(config.model_path) if config.model_path else None
    if not model_path or not model_path.exists():
        return {}, False, "modello locale non disponibile"
    try:
        from llama_cpp import Llama
    except ImportError:
        return {}, False, "llama-cpp-python non installato"
    prompt = (
        "Analizza localmente questa email e restituisci solo JSON con chiavi tipo_email, "
        "tema_operativo, azione_richiesta, cliente_o_ente, contesto_utile, "
        "etichette_candidate, riassunto_semantico.\n\n" + text[: config.max_input_chars]
    )
    try:
        model = Llama(model_path=str(model_path), verbose=False)
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            model.create_completion, prompt=prompt, max_tokens=config.max_output_tokens,
            temperature=config.temperature,
        )
        try:
            result = future.result(timeout=config.timeout_seconds)
        except TimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            return {}, False, f"timeout LLM dopo {config.timeout_seconds}s"
        executor.shutdown(wait=False)
        raw = result["choices"][0]["text"].strip()
        start, end = raw.find("{"), raw.rfind("}")
        return json.loads(raw[start:end + 1]), True, None
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        return {}, False, f"output LLM non valido: {exc}"
