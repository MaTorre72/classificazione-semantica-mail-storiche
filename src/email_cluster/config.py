from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    path: Path = Path("data/email_cluster.sqlite")


class EmbeddingConfig(BaseModel):
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    chunk_size_chars: int = 2000
    chunk_overlap_chars: int = 200
    batch_size: int = 32


class UmapConfig(BaseModel):
    n_neighbors: int = 15
    n_components: int = 5
    min_dist: float = 0.0
    metric: str = "cosine"
    random_state: int = 42


class HdbscanConfig(BaseModel):
    min_cluster_size: int = 10
    min_samples: int = 5
    metric: str = "euclidean"
    cluster_selection_method: str = "eom"


class ClusteringProfile(BaseModel):
    umap: UmapConfig = Field(default_factory=UmapConfig)
    hdbscan: HdbscanConfig = Field(default_factory=HdbscanConfig)


class SweepConfig(BaseModel):
    n_neighbors: list[int] = [5, 8, 10, 12, 15]
    n_components: list[int] = [3, 5, 8]
    min_cluster_size: list[int] = [4, 5, 6, 8, 10]
    min_samples: list[int] = [2, 3, 5]
    max_combinations: int = 12


class ClusteringConfig(BaseModel):
    active_profile: str = "balanced"
    profiles: dict[str, ClusteringProfile] = Field(default_factory=lambda: {
        "balanced": ClusteringProfile(
            umap=UmapConfig(n_neighbors=10),
            hdbscan=HdbscanConfig(min_cluster_size=6, min_samples=3),
        )
    })
    normalize_embeddings: bool = True
    min_cluster_size_absolute: int = 4
    max_noise_ratio_warning: float = 0.60
    max_largest_cluster_ratio_warning: float = 0.45
    min_clusters_warning: int = 3
    low_confidence_threshold: float = 0.5
    allowed_message_types: list[str] = ["operational_email"]
    technical_stopwords: list[str] = Field(default_factory=list)
    sweep: SweepConfig = Field(default_factory=SweepConfig)


class CleaningConfig(BaseModel):
    version: str = "v1.0.1"
    min_semantic_chars: int = 80
    min_unique_words: int = 8
    max_semantic_chars: int = 12000
    exclude_message_types: list[str] = Field(default_factory=lambda: [
        "short_ack", "auto_generated", "pec_receipt", "delivery_notification",
        "calendar_message", "newsletter", "attachment_only", "forward_only", "low_information",
    ])
    signature_patterns: list[str] = Field(default_factory=list)
    disclaimer_patterns: list[str] = Field(default_factory=list)
    quote_patterns: list[str] = Field(default_factory=list)
    automatic_patterns: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    umap: UmapConfig = Field(default_factory=UmapConfig)
    hdbscan: HdbscanConfig = Field(default_factory=HdbscanConfig)
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)


def load_config(path: Path | None = None) -> AppConfig:
    if path is None or not path.exists():
        return AppConfig()
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)
