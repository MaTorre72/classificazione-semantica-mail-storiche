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


def test_cleaning_removes_low_signal_links_and_mailto_lines() -> None:
    text = """Ciao Marco,
trovi l'analisi in allegato.
https://example.com/tracking
mailto:qualcuno@example.com
"""
    cleaned = build_clean_text(1, text)

    assert "analisi in allegato" in cleaned.clean_text
    assert "https://example.com/tracking" not in cleaned.clean_text
    assert "mailto:" not in cleaned.clean_text


def test_cleaning_removes_professional_signature_and_inline_tracking_links() -> None:
    text = """Buonasera a tutti,
in allegato le trascrizioni dell'ultima udienza.
Cordialmente,

Avv. Martina Fusato
Associate
Curriculum Vitae<https://www.example.com/cv.pdf>
[cid:image001.png@01DA5479]<https://www.linkedin.com/company/example/>
"""
    cleaned = build_clean_text(1, text)

    assert "trascrizioni dell'ultima udienza" in cleaned.clean_text
    assert "Martina Fusato" not in cleaned.clean_text
    assert "Curriculum Vitae" not in cleaned.clean_text
    assert "cid:" not in cleaned.clean_text


def test_cleaning_removes_disclaimer_and_contact_footer() -> None:
    text = """Test aspirazione reparto mastici.

This email is intended only for the person to whom it is addressed and/or otherwise authorized personnel.
The information contained herein and attached is confidential.
Via I Maggio, 226/263 - 37020 Volargne (VR) - Italy
C.F. e P.IVA 00214680233
Tel. +39 045 686 0222 - Fax: +39 045 686 2456
"""
    cleaned = build_clean_text(1, text)

    assert cleaned.clean_text == "Test aspirazione reparto mastici."


def test_cleaning_removes_teams_and_newsletter_boilerplate_lines() -> None:
    text = """Allineamento VIA / SEVESO
Riunione di Microsoft Teams
Partecipa da computer, app per dispositivi mobili o dispositivo della stanza
Fai clic qui per partecipare alla riunione
Scarica Teams | Partecipa sul web
Non visualizzi questa email? Leggi la versione web.
"""
    cleaned = build_clean_text(1, text)

    assert cleaned.clean_text == "Allineamento VIA / SEVESO"


def test_cleaning_removes_standalone_greetings_and_names() -> None:
    text = """Richiesta analisi emissioni
Ciao Marco,
ti mando in allegato la relazione aggiornata.
Grazie,
Andrea Peretti
"""
    cleaned = build_clean_text(1, text)

    assert cleaned.clean_text == "Richiesta analisi emissioni\nti mando in allegato la relazione aggiornata."


def test_cleaning_removes_original_message_and_automatic_access_noise() -> None:
    text = """Registrazione ingresso
CUBESuite
Spett.le Torresendi Marco,sei stato registrato presso Tenax SedePer
registrare l'uscita mostra questo qrcode al dispositivo
CUBESuite - © Life3 S.r.l.
-----Messaggio originale-----
testo vecchio
"""
    cleaned = build_clean_text(1, text)

    assert cleaned.clean_text == "Registrazione ingresso"
