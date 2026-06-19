from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize


def run_clustering(
    vectors: np.ndarray, umap_params: dict[str, Any], hdbscan_params: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray]:
    try:
        import hdbscan
        import umap
    except ImportError as exc:
        raise RuntimeError("umap-learn e hdbscan non sono installati. Usa: pip install -e .[ml]") from exc

    if len(vectors) < 2:
        return np.array([-1] * len(vectors)), np.array([0.0] * len(vectors))

    normalized = normalize(vectors)
    reducer = umap.UMAP(**umap_params)
    reduced = reducer.fit_transform(normalized)
    clusterer = hdbscan.HDBSCAN(**hdbscan_params)
    labels = clusterer.fit_predict(reduced)
    probabilities = getattr(clusterer, "probabilities_", np.zeros(len(labels)))
    return labels.astype(int), np.asarray(probabilities, dtype="float32")


def summarize_clusters(
    labels: np.ndarray, vectors: np.ndarray, texts: list[str], email_ids: list[int]
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    by_cluster: dict[int, list[int]] = defaultdict(list)
    for idx, label in enumerate(labels):
        by_cluster[int(label)].append(idx)

    for cluster_id, indexes in sorted(by_cluster.items()):
        cluster_texts = [texts[i] for i in indexes]
        keywords = extract_keywords(cluster_texts)
        representative_ids = representative_email_ids(vectors, indexes, email_ids)
        label_auto = ", ".join(keywords[:3]) if keywords else f"Cluster {cluster_id}"
        summaries.append(
            {
                "cluster_id": cluster_id,
                "label_auto": "Rumore / non classificati" if cluster_id == -1 else label_auto,
                "keywords": keywords,
                "representative_email_ids": representative_ids,
                "size": len(indexes),
                "coherence_score": coherence_score(vectors, indexes),
            }
        )
    return summaries


def extract_keywords(texts: list[str], limit: int = 10) -> list[str]:
    joined = [text for text in texts if text.strip()]
    if not joined:
        return []
    max_features = max(20, limit * 4)
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        ngram_range=(1, 2),
        stop_words=list(ITALIAN_STOPWORDS),
        min_df=1,
    )
    try:
        matrix = vectorizer.fit_transform(joined)
    except ValueError:
        words = Counter(" ".join(joined).lower().split())
        return [word for word, _ in words.most_common(limit)]
    scores = np.asarray(matrix.sum(axis=0)).ravel()
    names = np.asarray(vectorizer.get_feature_names_out())
    order = scores.argsort()[::-1]
    return [str(names[i]) for i in order[:limit]]


def representative_email_ids(vectors: np.ndarray, indexes: list[int], email_ids: list[int], limit: int = 5) -> list[int]:
    if not indexes:
        return []
    cluster_vectors = vectors[indexes]
    centroid = cluster_vectors.mean(axis=0, keepdims=True)
    similarities = cosine_similarity(cluster_vectors, centroid).ravel()
    ordered = np.argsort(similarities)[::-1][:limit]
    return [email_ids[indexes[i]] for i in ordered]


def coherence_score(vectors: np.ndarray, indexes: list[int]) -> float | None:
    if len(indexes) < 2:
        return None
    sims = cosine_similarity(vectors[indexes])
    upper = sims[np.triu_indices_from(sims, k=1)]
    return float(np.mean(upper)) if len(upper) else None


ITALIAN_STOPWORDS = {
    "a", "ad", "al", "alla", "alle", "anche", "che", "con", "da", "dei", "del", "della",
    "di", "e", "il", "in", "la", "le", "lo", "mi", "non", "o", "per", "si", "sono", "su",
    "un", "una", "vi", "vs", "buongiorno", "grazie", "saluti", "cordiali",
}

