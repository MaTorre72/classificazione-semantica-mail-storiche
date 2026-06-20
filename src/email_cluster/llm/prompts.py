PROMPT_VERSION = "review-v1"


def cluster_prompt(context: str) -> str:
    return """Sei un assistente locale di revisione email. Restituisci solo JSON con: cluster_label,
cluster_summary, main_topics, client_or_entity, technical_domain, suggested_taxonomy_labels,
is_mixed_cluster, split_suggestion, emails_to_inspect, confidence. Non inventare dati.\n\n""" + context


def email_prompt(context: str) -> str:
    return """Restituisci solo JSON con: message_type, professional_relevance, topic_label,
client_or_entity, technical_domain, action_required, suggested_taxonomy_labels, should_be_excluded,
exclusion_reason, confidence.\n\n""" + context


def operational_context_prompt(context: str) -> str:
    return """Ricostruisci il contesto operativo, non descrivere il clustering. Restituisci solo JSON:
context_name, context_type, client_or_entity, technical_domain, practice_or_topic, summary,
why_grouped, emails_that_do_not_fit, suggested_user_action, suggested_label, confidence.\n\n""" + context
