from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    path: Path = Path("data/email_cluster.sqlite")
    backup_before_migration: bool = True


class ProjectConfig(BaseModel):
    name: str = "mail-storiche"


class InputConfig(BaseModel):
    path: Path = Path("data/input")
    recursive: bool = True


class EmbeddingConfig(BaseModel):
    mode: str = "semantic"
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
    version: str = "v2.0.2"
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


class SemanticPreparationConfig(BaseModel):
    version: str = "v2.0.2"
    min_semantic_chars: int = 120
    min_unique_words: int = 12
    max_thread_context_chars: int = 1500
    max_attachment_summary_chars: int = 1500
    exclude_message_types: list[str] = Field(default_factory=lambda: [
        "auto_generated", "pec_receipt", "delivery_notification", "calendar_message",
        "newsletter", "personal_or_commercial_notification",
        "low_information",
    ])
    short_reply_patterns: list[str] = ["ok", "grazie", "perfetto", "ricevuto", "procedi pure"]
    technical_stopwords: list[str] = Field(default_factory=list)


class AttachmentsConfig(BaseModel):
    enabled: bool = True
    extract_text: bool = True
    max_file_size_mb: int = 20
    enable_pdf: bool = True
    enable_docx: bool = True
    enable_xlsx: bool = True
    enable_ocr: bool = False


class LocalLlmConfig(BaseModel):
    enabled: bool = False
    backend: str = "llama_cpp"
    ollama_url: str = "http://localhost:11434"
    model: str = ""
    model_path: str = ""
    max_input_chars: int = 4000
    max_output_tokens: int = 256
    temperature: float = 0.1
    timeout_seconds: int = 60
    use_for_thread_summary: bool = True
    use_for_attachment_summary: bool = True
    use_for_semantic_enrichment: bool = True
    require_json: bool = True
    cache_enabled: bool = True
    cache_version: str = "v1"
    use_for_email_triage: bool = True
    use_for_cluster_labeling: bool = True
    use_for_cluster_summary: bool = True
    use_for_taxonomy_suggestion: bool = True
    use_for_split_suggestion: bool = True


class AppConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    input: InputConfig = Field(default_factory=InputConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    umap: UmapConfig = Field(default_factory=UmapConfig)
    hdbscan: HdbscanConfig = Field(default_factory=HdbscanConfig)
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    cleaning: CleaningConfig = Field(default_factory=CleaningConfig)
    semantic_preparation: SemanticPreparationConfig = Field(default_factory=SemanticPreparationConfig)
    attachments: AttachmentsConfig = Field(default_factory=AttachmentsConfig)
    local_llm: LocalLlmConfig = Field(default_factory=LocalLlmConfig)


def load_config(path: Path | None = None) -> AppConfig:
    if path is None or not path.exists():
        return AppConfig()
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)
