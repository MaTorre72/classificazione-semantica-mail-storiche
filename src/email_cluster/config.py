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


class CleaningConfig(BaseModel):
    version: str = "v0.1.0"


class AppConfig(BaseModel):
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    umap: UmapConfig = Field(default_factory=UmapConfig)
    hdbscan: HdbscanConfig = Field(default_factory=HdbscanConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)


def load_config(path: Path | None = None) -> AppConfig:
    if path is None or not path.exists():
        return AppConfig()
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)

