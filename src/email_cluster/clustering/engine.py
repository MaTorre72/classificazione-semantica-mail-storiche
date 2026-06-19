from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.preprocessing import normalize

from .labeling import summarize_clusters

__all__ = ["run_clustering", "summarize_clusters"]


def run_clustering(
    vectors: np.ndarray, umap_params: dict[str, Any], hdbscan_params: dict[str, Any], *,
    normalize_embeddings: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    try:
        import hdbscan
        import umap
    except ImportError as exc:
        raise RuntimeError("umap-learn e hdbscan non sono installati. Usa: pip install -e .[ml]") from exc
    if len(vectors) < 2:
        return np.full(len(vectors), -1), np.zeros(len(vectors), dtype="float32")
    prepared = normalize(vectors) if normalize_embeddings else vectors
    reduced = umap.UMAP(**umap_params).fit_transform(prepared)
    clusterer = hdbscan.HDBSCAN(**hdbscan_params)
    labels = clusterer.fit_predict(reduced)
    probabilities = getattr(clusterer, "probabilities_", np.zeros(len(labels)))
    return labels.astype(int), np.asarray(probabilities, dtype="float32")
