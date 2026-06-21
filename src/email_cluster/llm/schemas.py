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


class OperationalContextSuggestion(BaseModel):
    context_name: str
    context_type: str = "tema_tecnico"
    client_or_entity: str = ""
    technical_domain: str = ""
    practice_or_topic: str = ""
    summary: str = ""
    why_grouped: str = ""
    emails_that_do_not_fit: list[int] = Field(default_factory=list)
    suggested_user_action: str = "approva"
    suggested_label: str = ""
    confidence: float = 0.0


class AreaProposal(BaseModel):
    name: str
    description: str = ""
    operational: bool = True
    reason: str = ""


class AreasSuggestion(BaseModel):
    areas: list[AreaProposal] = Field(default_factory=list)
    areas_to_merge: list[list[str]] = Field(default_factory=list)
    areas_to_rename: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    email_reclassification_proposal: list[dict[str, object]] = Field(default_factory=list)


class ClassProposal(BaseModel):
    name: str
    description: str = ""
    reason: str = ""


class ClassesSuggestion(BaseModel):
    classes: list[ClassProposal] = Field(default_factory=list)
    sets_to_move: list[dict[str, object]] = Field(default_factory=list)
    emails_to_reclassify: list[int] = Field(default_factory=list)


class SetImprovementSuggestion(BaseModel):
    better_name: str = ""
    area: str = ""
    classification_class: str = Field("", alias="class")
    summary: str = ""
    why_grouped: str = ""
    emails_out_of_place: list[int] = Field(default_factory=list)
    should_split: bool = False
    split_proposal: list[dict[str, object]] = Field(default_factory=list)
    merge_candidates: list[int] = Field(default_factory=list)
    confidence: float = 0.0


class EmailClassificationSuggestion(BaseModel):
    area: str = ""
    classification_class: str = Field("", alias="class")
    set_name: str = Field("", alias="set")
    new_set_needed: bool = False
    new_set_name: str = ""
    summary: str = ""
    reason: str = ""
    confidence: float = 0.0
