from __future__ import annotations

import re
from collections import Counter
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_STOPWORDS = {
    "a", "ad", "al", "alla", "anche", "che", "con", "da", "dei", "del", "della", "di", "e",
    "il", "in", "la", "le", "lo", "non", "o", "per", "si", "sono", "su", "un", "una",
    "and", "are", "for", "from", "is", "it", "of", "the", "this", "to", "you", "your",
    "buongiorno", "buonasera", "grazie", "cordiali", "saluti", "allegato", "allegata", "invio",
    "trasmetto", "riferimento", "comunicazione", "richiesta", "riscontro", "informazioni",
    "documento", "documenti", "mail", "email", "oggetto", "inviato", "gmail", "marcotorresendi",
    "ciao", "marco", "mailto", "com", "https", "http", "www", "tel", "dell", "alle", "avv",
}


def summarize_clusters(
    labels: np.ndarray, vectors: np.ndarray, texts: list[str], email_ids: list[int],
    subjects: list[str], senders: list[str], probabilities: np.ndarray,
    technical_stopwords: list[str] | None = None,
) -> list[dict[str, Any]]:
    stopwords = BASE_STOPWORDS | {word.lower() for word in technical_stopwords or []}
    summaries: list[dict[str, Any]] = []
    for cluster_id in sorted(set(labels.tolist())):
        indexes = np.where(labels == cluster_id)[0].tolist()
        keywords = extract_keywords([texts[i] for i in indexes], stopwords)
        recurring_subjects = extract_keywords([subjects[i] for i in indexes], stopwords, limit=5)
        domains = Counter(_sender_domain(senders[i]) for i in indexes if _sender_domain(senders[i]))
        recurring_domains = [name for name, _ in domains.most_common(5)]
        representatives = representative_email_ids(vectors, indexes, email_ids)
        candidates = _dedupe(recurring_subjects[:2] + keywords[:4])
        label = ", ".join(candidates[:3]) or f"Cluster {cluster_id}"
        confidence = min(1.0, len(indexes) / 10) * (1.0 if len(candidates) >= 2 else 0.5)
        summaries.append({
            "cluster_id": cluster_id,
            "label_auto": "Rumore / non classificati" if cluster_id == -1 else label,
            "keywords": keywords,
            "representative_email_ids": representatives,
            "size": len(indexes),
            "coherence_score": coherence_score(vectors, indexes),
            "recurring_subjects": recurring_subjects,
            "recurring_senders": recurring_domains,
            "mean_probability": float(np.mean(probabilities[indexes])) if indexes else 0.0,
            "confidence_label": round(confidence, 3),
        })
    return summaries


def extract_keywords(texts: list[str], stopwords: set[str], limit: int = 10) -> list[str]:
    joined = [text for text in texts if text.strip()]
    if not joined:
        return []
    vectorizer = TfidfVectorizer(
        max_features=max(40, limit * 8), ngram_range=(1, 3), stop_words=sorted(stopwords),
        token_pattern=r"(?u)\b[^\W\d_][^\W\d_]{2,}\b", sublinear_tf=True,
    )
    try:
        matrix = vectorizer.fit_transform(joined)
    except ValueError:
        return []
    scores = np.asarray(matrix.mean(axis=0)).ravel()
    names = np.asarray(vectorizer.get_feature_names_out())
    ordered = scores.argsort()[::-1]
    return [str(names[i]) for i in ordered if not _generic_phrase(str(names[i]), stopwords)][:limit]


def representative_email_ids(vectors: np.ndarray, indexes: list[int], email_ids: list[int], limit: int = 5) -> list[int]:
    if not indexes:
        return []
    cluster_vectors = vectors[indexes]
    centroid = cluster_vectors.mean(axis=0, keepdims=True)
    order = np.argsort(cosine_similarity(cluster_vectors, centroid).ravel())[::-1][:limit]
    return [email_ids[indexes[i]] for i in order]


def coherence_score(vectors: np.ndarray, indexes: list[int]) -> float | None:
    if len(indexes) < 2:
        return None
    similarities = cosine_similarity(vectors[indexes])
    values = similarities[np.triu_indices_from(similarities, k=1)]
    return float(np.mean(values)) if len(values) else None


def _sender_domain(sender: str) -> str:
    match = re.search(r"@([\w.-]+)", sender or "")
    return match.group(1).lower() if match else ""


def _generic_phrase(value: str, stopwords: set[str]) -> bool:
    return all(part in stopwords for part in value.split())


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and not any(value in existing or existing in value for existing in result):
            result.append(value)
    return result
