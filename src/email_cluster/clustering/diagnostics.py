from __future__ import annotations

from collections import Counter
from statistics import mean, median
from typing import Any

import numpy as np
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score


def calculate_metrics(
    labels: np.ndarray, probabilities: np.ndarray, vectors: np.ndarray, *,
    excluded_before: int = 0, small_size: int = 4, low_confidence: float = 0.5,
) -> dict[str, Any]:
    total = len(labels)
    noise = int(np.sum(labels == -1))
    sizes = [count for label, count in Counter(labels.tolist()).items() if label != -1]
    clustered_mask = labels != -1
    distinct = set(labels[clustered_mask].tolist())
    scores: dict[str, float | None] = {"silhouette_score": None, "davies_bouldin_score": None, "calinski_harabasz_score": None}
    if len(distinct) >= 2 and int(clustered_mask.sum()) > len(distinct):
        x, y = vectors[clustered_mask], labels[clustered_mask]
        try:
            scores = {
                "silhouette_score": float(silhouette_score(x, y, metric="cosine")),
                "davies_bouldin_score": float(davies_bouldin_score(x, y)),
                "calinski_harabasz_score": float(calinski_harabasz_score(x, y)),
            }
        except ValueError:
            pass
    assigned_probabilities = probabilities[clustered_mask]
    return {
        "total_emails_considered": total,
        "excluded_before_clustering": excluded_before,
        "total_clusters": len(sizes),
        "total_noise": noise,
        "noise_ratio": noise / total if total else 0.0,
        "largest_cluster_size": max(sizes, default=0),
        "largest_cluster_ratio": max(sizes, default=0) / total if total else 0.0,
        "median_cluster_size": float(median(sizes)) if sizes else 0.0,
        "mean_cluster_size": float(mean(sizes)) if sizes else 0.0,
        "min_cluster_size": min(sizes, default=0),
        "max_cluster_size": max(sizes, default=0),
        "number_of_small_clusters": sum(size < small_size for size in sizes),
        "number_of_large_clusters": sum(size > total * 0.25 for size in sizes),
        "mean_cluster_probability": float(np.mean(assigned_probabilities)) if len(assigned_probabilities) else 0.0,
        "low_confidence_assignments": int(np.sum(assigned_probabilities < low_confidence)),
        **scores,
    }


def diagnostic_warnings(metrics: dict[str, Any], *, max_noise: float, max_largest: float, min_clusters: int) -> list[str]:
    warnings: list[str] = []
    if metrics["largest_cluster_ratio"] > max_largest:
        warnings.append(f"Cluster dominante: il cluster piu grande contiene {metrics['largest_cluster_ratio']:.0%} delle email considerate.")
    if metrics["noise_ratio"] > max_noise:
        warnings.append(f"Rumore elevato: HDBSCAN ha marcato come rumore {metrics['noise_ratio']:.0%} delle email considerate.")
    if metrics["total_clusters"] < min_clusters:
        warnings.append(f"Pochi cluster: prodotti {metrics['total_clusters']} cluster.")
    if metrics["number_of_small_clusters"] > metrics["total_clusters"] / 2 and metrics["total_clusters"]:
        warnings.append("Molti cluster piccoli: oltre meta dei cluster e sotto la soglia minima consigliata.")
    if metrics["mean_cluster_probability"] < 0.5:
        warnings.append("Probabilita media bassa: molte assegnazioni sono poco stabili.")
    if metrics["total_emails_considered"] < 20:
        warnings.append("Campione ridotto: le metriche del clustering sono poco affidabili.")
    return warnings
