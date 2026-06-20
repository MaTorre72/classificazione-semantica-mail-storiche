from __future__ import annotations

from pydantic import BaseModel, Field


class EmailReviewSuggestion(BaseModel):
    message_type: str = ""
    professional_relevance: str = "medium"
    topic_label: str = ""
    client_or_entity: str = ""
    technical_domain: str = ""
    action_required: str = ""
    suggested_taxonomy_labels: list[str] = Field(default_factory=list)
    should_be_excluded: bool = False
    exclusion_reason: str = ""
    confidence: float = 0.0


class SplitSuggestion(BaseModel):
    label: str
    rationale: str = ""
    representative_email_ids: list[int] = Field(default_factory=list)


class ClusterReviewSuggestion(BaseModel):
    cluster_label: str = ""
    cluster_summary: str = ""
    main_topics: list[str] = Field(default_factory=list)
    client_or_entity: str = ""
    technical_domain: str = ""
    suggested_taxonomy_labels: list[str] = Field(default_factory=list)
    is_mixed_cluster: bool = False
    split_suggestion: list[SplitSuggestion] = Field(default_factory=list)
    emails_to_inspect: list[int] = Field(default_factory=list)
    confidence: float = 0.0


class ClusterActionSuggestion(BaseModel):
    suggested_action: str = "inspect"
    reason: str = ""
    proposed_human_label: str = ""
    merge_candidates: list[int] = Field(default_factory=list)
    split_candidates: list[str] = Field(default_factory=list)
    confidence: float = 0.0
