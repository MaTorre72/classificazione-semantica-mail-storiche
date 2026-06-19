from email_cluster.cleaning.normalizer import build_clean_text


def test_cleaning_removes_quoted_reply_and_disclaimer() -> None:
    text = """Buongiorno,
serve la documentazione RENTRI.

Da: Mario <mario@example.com>
vecchio messaggio

Questo messaggio e i suoi allegati sono riservati."""
    cleaned = build_clean_text(1, text)

    assert "documentazione RENTRI" in cleaned.clean_text
    assert "vecchio messaggio" not in cleaned.clean_text
    assert cleaned.cleaning_flags["quoted_reply_removed"]

