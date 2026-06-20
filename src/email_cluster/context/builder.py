from __future__ import annotations

import re
from dataclasses import dataclass

from email_cluster.config import SemanticPreparationConfig
from email_cluster.context.strategy import choose_strategy
from email_cluster.context.thread_summary import summarize_thread


@dataclass(slots=True)
class SemanticContext:
    email_id: int
    context_version: str
    message_type: str
    message_type_confidence: float
    context_strategy: str
    thread_context_summary: str
    attachment_summary: str
    semantic_summary: str
    semantic_text_for_embedding: str
    quality_score: float
    excluded_from_main_clustering: bool
    exclusion_reason: str | None
    llm_used: bool = False
    llm_model: str | None = None
    llm_parameters: dict[str, object] | None = None
    action_required: str = ""
    topic_label: str = ""
    candidate_tags: list[str] | None = None


def build_context(
    email_id: int, subject: str, current: str, quoted_thread: str, message_type: str,
    attachment_summary: str, config: SemanticPreparationConfig,
    semantic_enrichment: dict[str, object] | None = None,
) -> SemanticContext:
    normalized_type = "short_reply" if message_type == "short_ack" else message_type
    thread_summary = summarize_thread(quoted_thread, config.max_thread_context_chars)
    strategy, excluded, reason = choose_strategy(
        normalized_type, current, quoted_thread, attachment_summary,
        config.exclude_message_types, config.min_semantic_chars,
    )
    enrichment = semantic_enrichment or {}
    parts = [subject.strip()]
    if strategy not in {"thread_dominant", "exclude_from_main_clustering"}:
        parts.append(current.strip())
    if strategy == "thread_dominant":
        parts.extend([current.strip(), thread_summary])
    if strategy == "attachment_dominant":
        parts.append(attachment_summary[: config.max_attachment_summary_chars])
    semantic_summary = str(enrichment.get("riassunto_semantico") or "")
    if semantic_summary:
        parts.append(semantic_summary)
    semantic_text = "\n\n".join(part for part in parts if part).strip()
    unique = set(re.findall(r"\b[^\W\d_]{3,}\b", semantic_text.lower()))
    if not excluded and (len(semantic_text) < config.min_semantic_chars or len(unique) < config.min_unique_words):
        excluded = True
        strategy = "exclude_from_main_clustering"
        reason = "contesto semantico sotto soglia"
    quality = min(1.0, len(semantic_text) / 500) * min(1.0, len(unique) / 30)
    return SemanticContext(
        email_id=email_id, context_version=config.version, message_type=normalized_type,
        message_type_confidence=0.9, context_strategy=strategy,
        thread_context_summary=thread_summary, attachment_summary=attachment_summary,
        semantic_summary=semantic_summary, semantic_text_for_embedding=semantic_text,
        quality_score=round(quality, 3), excluded_from_main_clustering=excluded,
        exclusion_reason=reason, action_required=str(enrichment.get("azione_richiesta") or ""),
        topic_label=str(enrichment.get("tema_operativo") or ""),
        candidate_tags=list(enrichment.get("etichette_candidate") or []),
    )
