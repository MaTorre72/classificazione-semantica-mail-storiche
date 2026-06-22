from __future__ import annotations

import sqlite3

from email_cluster.storage.repository import Repository

ATLAS_VERSION = "atlas-v1"
STOPWORDS = {
    "della",
    "delle",
    "degli",
    "alla",
    "alle",
    "come",
    "email",
    "mail",
    "allegato",
    "documento",
    "richiesta",
    "risposta",
    "buongiorno",
    "grazie",
    "inoltro",
    "re",
    "fw",
    "fwd",
}


def _project(con: sqlite3.Connection, name: str) -> int:
    return Repository(con).get_or_create_project(name)
