from __future__ import annotations

import numpy as np


def chunk_text(text: str, size: int = 2000, overlap: int = 200) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


class EmbeddingEngine:
    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers non e' installato. Usa: pip install -e .[ml]"
            ) from exc
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())

    def embed_email(self, text: str, chunk_size: int, overlap: int) -> np.ndarray:
        chunks = chunk_text(text, chunk_size, overlap)
        if not chunks:
            return np.zeros(self.dimension, dtype="float32")
        vectors = self.model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)
        weights = np.array([max(len(chunk), 1) for chunk in chunks], dtype="float32")
        return np.average(np.asarray(vectors, dtype="float32"), axis=0, weights=weights)

