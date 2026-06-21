from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from email_cluster.config import LocalLlmConfig


class LocalLlmClient:
    def __init__(self, config: LocalLlmConfig):
        self.config = config

    @property
    def model_name(self) -> str:
        return self.config.model or Path(self.config.model_path).name or "local-disabled"

    def generate_json(self, prompt: str) -> tuple[dict[str, Any], str, int]:
        started = time.perf_counter()
        if not self.config.enabled:
            raise RuntimeError("LLM locale disabilitato")
        if self.config.backend == "ollama":
            if not self.config.ollama_url.startswith(("http://localhost", "http://127.0.0.1")):
                raise RuntimeError("Ollama deve usare localhost")
            payload = json.dumps(
                {"model": self.config.model, "prompt": prompt, "stream": False, "format": "json"}
            ).encode()
            request = urllib.request.Request(
                self.config.ollama_url.rstrip("/") + "/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(
                    request, timeout=self.config.timeout_seconds
                ) as response:
                    raw = json.loads(response.read().decode())["response"]
            except (TimeoutError, socket.timeout) as exc:
                raise RuntimeError(
                    f"Il modello non ha risposto entro {self.config.timeout_seconds} secondi. "
                    "Riprova oppure scegli un modello più leggero."
                ) from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(
                    "Ollama non è raggiungibile. Verifica che sia avviato e riprova."
                ) from exc
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as exc:
                raise RuntimeError(
                    "Ollama ha restituito una risposta tecnica non leggibile."
                ) from exc
        elif self.config.backend == "llama_cpp":
            if not self.config.model_path or not Path(self.config.model_path).exists():
                raise RuntimeError("Modello GGUF locale non disponibile")
            from llama_cpp import Llama

            model = Llama(model_path=self.config.model_path, verbose=False)
            output = model.create_completion(
                prompt=prompt,
                max_tokens=self.config.max_output_tokens,
                temperature=self.config.temperature,
            )
            raw = output["choices"][0]["text"]
        else:
            raise RuntimeError(f"Backend LLM non supportato: {self.config.backend}")
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < start:
            raise RuntimeError(
                "Il modello ha risposto in testo libero invece del formato richiesto. Riprova."
            )
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Il modello ha prodotto una proposta incompleta o non valida. Riprova."
            ) from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("Il modello non ha restituito una proposta strutturata valida.")
        return parsed, raw, int((time.perf_counter() - started) * 1000)
