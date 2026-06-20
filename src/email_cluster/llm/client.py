from __future__ import annotations

import json
import time
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
            payload = json.dumps({"model": self.config.model, "prompt": prompt, "stream": False, "format": "json"}).encode()
            request = urllib.request.Request(self.config.ollama_url.rstrip("/") + "/api/generate", data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = json.loads(response.read().decode())["response"]
        elif self.config.backend == "llama_cpp":
            if not self.config.model_path or not Path(self.config.model_path).exists():
                raise RuntimeError("Modello GGUF locale non disponibile")
            from llama_cpp import Llama

            model = Llama(model_path=self.config.model_path, verbose=False)
            output = model.create_completion(prompt=prompt, max_tokens=self.config.max_output_tokens, temperature=self.config.temperature)
            raw = output["choices"][0]["text"]
        else:
            raise RuntimeError(f"Backend LLM non supportato: {self.config.backend}")
        start, end = raw.find("{"), raw.rfind("}")
        parsed = json.loads(raw[start:end + 1])
        return parsed, raw, int((time.perf_counter() - started) * 1000)
