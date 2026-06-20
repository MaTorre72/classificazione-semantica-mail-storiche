from __future__ import annotations

import sqlite3

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

from email_cluster.storage.repository import blob_to_embedding


def suggest_cluster_splits(con: sqlite3.Connection, run_id: int) -> list[dict[str, object]]:
    suggestions: list[dict[str, object]] = []
    clusters = con.execute("SELECT cluster_id, size, coherence_score FROM clusters WHERE clustering_run_id=? AND cluster_id!=-1 AND size>=10", (run_id,))
    for cluster in clusters:
        rows = list(con.execute("""
            SELECT ec.email_id, se.embedding, e.subject FROM email_clusters ec
            JOIN semantic_embeddings se ON se.email_id=ec.email_id
            JOIN emails e ON e.id=ec.email_id
            WHERE ec.clustering_run_id=? AND ec.cluster_id=?
              AND se.id=(SELECT max(se2.id) FROM semantic_embeddings se2 WHERE se2.email_id=se.email_id)
        """, (run_id, cluster["cluster_id"])))
        if len(rows) < 10 or float(cluster["coherence_score"] or 1.0) > 0.75:
            continue
        vectors = np.vstack([blob_to_embedding(row["embedding"]) for row in rows])
        labels = KMeans(n_clusters=2, random_state=42, n_init=10).fit_predict(vectors)
        groups = []
        for label in (0, 1):
            indexes = np.where(labels == label)[0].tolist()
            groups.append({"label": f"Sottogruppo {label + 1}", "email_ids": [int(rows[i]["email_id"]) for i in indexes], "subjects": [rows[i]["subject"] for i in indexes[:5]]})
        suggestions.append({"cluster_id": int(cluster["cluster_id"]), "strategy": "kmeans-2", "groups": groups})
    return suggestions


def suggest_cluster_merges(con: sqlite3.Connection, run_id: int, threshold: float = 0.86) -> list[dict[str, object]]:
    centroids: dict[int, np.ndarray] = {}
    labels: dict[int, str] = {}
    for cluster in con.execute("SELECT cluster_id, label_auto FROM clusters WHERE clustering_run_id=? AND cluster_id!=-1", (run_id,)):
        vectors = [blob_to_embedding(row[0]) for row in con.execute("""
            SELECT se.embedding FROM email_clusters ec JOIN semantic_embeddings se ON se.email_id=ec.email_id
            WHERE ec.clustering_run_id=? AND ec.cluster_id=?
              AND se.id=(SELECT max(se2.id) FROM semantic_embeddings se2 WHERE se2.email_id=se.email_id)
        """, (run_id, cluster["cluster_id"]))]
        if vectors:
            centroids[int(cluster["cluster_id"])] = np.mean(vectors, axis=0)
            labels[int(cluster["cluster_id"])] = cluster["label_auto"] or ""
    ids = sorted(centroids)
    suggestions = []
    for pos, left in enumerate(ids):
        for right in ids[pos + 1:]:
            similarity = float(cosine_similarity([centroids[left]], [centroids[right]])[0, 0])
            if similarity >= threshold:
                suggestions.append({"clusters": [left, right], "labels": [labels[left], labels[right]], "similarity": round(similarity, 3)})
    return suggestions
