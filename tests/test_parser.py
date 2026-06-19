from email.message import EmailMessage

from email_cluster.parsing.email_parser import parse_eml


def test_parse_eml_extracts_body_and_attachment_metadata(tmp_path) -> None:
    msg = EmailMessage()
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    msg["Subject"] = "Prova RENTRI"
    msg["Message-ID"] = "<test@example.com>"
    msg.set_content("Buongiorno, invio documento.")
    msg.add_attachment(b"abc", maintype="application", subtype="pdf", filename="doc.pdf")

    path = tmp_path / "message.eml"
    path.write_bytes(msg.as_bytes())

    parsed = parse_eml(path)

    assert parsed.subject == "Prova RENTRI"
    assert parsed.recipients == ["bob@example.com"]
    assert "invio documento" in parsed.body_extracted_text
    assert parsed.attachments[0].filename == "doc.pdf"

