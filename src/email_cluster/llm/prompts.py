PROMPT_VERSION = "review-v1"


def cluster_prompt(context: str) -> str:
    return """Sei un assistente locale di revisione email. Restituisci solo JSON con: cluster_label,
cluster_summary, main_topics, client_or_entity, technical_domain, suggested_taxonomy_labels,
is_mixed_cluster, split_suggestion, emails_to_inspect, confidence. Non inventare dati.\n\n""" + context


def email_prompt(context: str) -> str:
    return """Restituisci solo JSON con: message_type, professional_relevance, topic_label,
client_or_entity, technical_domain, action_required, suggested_taxonomy_labels, should_be_excluded,
exclusion_reason, confidence.\n\n""" + context
