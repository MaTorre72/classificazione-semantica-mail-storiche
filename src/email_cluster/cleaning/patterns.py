from __future__ import annotations

QUOTE_STARTS = [
    r"^-----\s*(?:original message|messaggio originale)\s*-----",
    r"^inizio messaggio inoltrato",
    r"^begin forwarded message",
    r"^il giorno .+ ha scritto:?$",
    r"^on .+ wrote:?$",
]

TECHNICAL_HEADER = r"^(?:da|from|inviato|sent|a|to|cc|oggetto|subject):\s*.+$"

DISCLAIMER_STARTS = [
    "questo messaggio e i suoi allegati", "le informazioni contenute nella presente",
    "ai sensi del regolamento", "informativa privacy", "this message and any attachments",
    "the information contained in this message", "this email is intended only",
    "if you are not the intended recipient",
]

SIGNATURE_STARTS = [
    "cordiali saluti", "distinti saluti", "cordialmente", "best regards", "kind regards",
]

NEWSLETTER_MARKERS = [
    "annulla iscrizione", "unsubscribe", "non visualizzi questa email", "view this email in your browser",
    "se non desideri ricevere", "preferenze email",
]

CALENDAR_MARKERS = [
    "riunione di microsoft teams", "fai clic qui per partecipare", "google calendar",
    "invito:", "invitation:", "when:", "quando:", "ics attachment",
]

PEC_MARKERS = [
    "ricevuta di accettazione", "ricevuta di avvenuta consegna", "posta certificata",
    "gestore di posta certificata", "daticert.xml", "smime.p7s",
]

DELIVERY_MARKERS = [
    "delivery status notification", "undeliverable", "mail delivery subsystem",
    "mailer-daemon", "mancata consegna", "delivery has failed", "failure notice",
]

AUTOMATIC_MARKERS = [
    "messaggio generato automaticamente", "do not reply", "non rispondere a questa email",
    "cubesuite", "registrazione ingresso", "notifica automatica", "il tuo ordine amazon",
    "amazon.it di", "risposta automatica:",
]
