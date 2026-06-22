"""Compatibility facade for the modular Email Atlas services."""

from .conversations import build_conversations
from .discovery import discover
from .embeddings import embed_documents
from .entities import extract_entities
from .evaluation import evaluate
from .export import export_atlas
from .inventory import inventory
from .parsing import parse_and_clean
from .review import review_action
from .search import build_index, search
from .semantic_docs import build_semantic_docs
from .update import update_archive

__all__ = [
    "build_conversations",
    "build_index",
    "build_semantic_docs",
    "discover",
    "embed_documents",
    "evaluate",
    "export_atlas",
    "extract_entities",
    "inventory",
    "parse_and_clean",
    "review_action",
    "search",
    "update_archive",
]
