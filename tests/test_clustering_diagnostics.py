import numpy as np

from email_cluster.clustering.diagnostics import calculate_metrics, diagnostic_warnings
from email_cluster.clustering.labeling import BASE_STOPWORDS, extract_keywords, representative_email_ids


def test_metrics_and_dominant_cluster_warning() -> None:
    labels = np.array([0] * 8 + [1, 1])
    probabilities = np.full(10, 0.8)
    vectors = np.eye(10, dtype="float32")
    metrics = calculate_metrics(labels, probabilities, vectors, excluded_before=3)
    warnings = diagnostic_warnings(metrics, max_noise=0.6, max_largest=0.45, min_clusters=3)
    assert metrics["total_emails_considered"] == 10
    assert metrics["excluded_before_clustering"] == 3
    assert metrics["largest_cluster_ratio"] == 0.8
    assert any("Cluster dominante" in warning for warning in warnings)


def test_high_noise_warning() -> None:
    labels = np.array([-1] * 7 + [0, 0, 0])
    metrics = calculate_metrics(labels, np.ones(10), np.eye(10))
    warnings = diagnostic_warnings(metrics, max_noise=0.6, max_largest=0.45, min_clusters=1)
    assert metrics["noise_ratio"] == 0.7
    assert any("Rumore elevato" in warning for warning in warnings)


def test_representatives_belong_to_cluster_and_follow_centroid() -> None:
    vectors = np.array([[1.0, 0.0], [0.9, 0.1], [-1.0, 0.0]])
    representatives = representative_email_ids(vectors, [0, 1], [10, 11, 12])
    assert set(representatives) <= {10, 11}


def test_labeling_filters_generic_stopwords() -> None:
    keywords = extract_keywords(
        ["Buongiorno invio documento analisi emissioni camino", "Grazie allegato analisi emissioni camino"],
        BASE_STOPWORDS,
    )
    assert keywords
    assert keywords[0] not in {"buongiorno", "grazie", "allegato", "documento", "invio"}
