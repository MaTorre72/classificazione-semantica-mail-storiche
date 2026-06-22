from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def write_report(output: Path, title: str, data: dict[str, Any]) -> None:
    """Write JSON or an action-oriented HTML report for non-technical readers."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix == ".json":
        output.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        return
    warnings = data.get("warnings") or ([data["warning"]] if data.get("warning") else [])
    next_step = data.get("next_step") or "Controlla i risultati prima di avviare la fase seguente."
    scalar_rows = "".join(
        f"<tr><th>{html.escape(str(key).replace('_', ' ').title())}</th>"
        f"<td>{html.escape(str(value))}</td></tr>"
        for key, value in data.items()
        if not isinstance(value, (list, dict)) and key not in {"warning", "next_step"}
    )
    details = "".join(
        f"<section><h2>{html.escape(str(key).replace('_', ' ').title())}</h2>"
        f"<pre>{html.escape(json.dumps(value, ensure_ascii=False, indent=2, default=str))}</pre>"
        "</section>"
        for key, value in data.items()
        if isinstance(value, (list, dict)) and key != "warnings"
    )
    warning_html = "".join(f"<li>{html.escape(str(item))}</li>" for item in warnings)
    output.write_text(
        "<!doctype html><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>body{font:15px system-ui;max-width:1100px;margin:30px auto;color:#17212b}"
        "table{border-collapse:collapse;width:100%}th,td{padding:9px;border-bottom:1px solid #ddd;"
        "text-align:left}pre{white-space:pre-wrap;background:#f4f6f7;padding:12px}.summary{border-left:4px solid #087f75;padding:12px;background:#eef8f6}"
        ".warning{border-left:4px solid #b86b00;padding:12px;background:#fff7e8}</style>"
        f"<h1>{html.escape(title)}</h1>"
        "<section class='summary'><h2>In sintesi</h2>"
        "<p>Questo report mostra il risultato della fase appena completata. I valori automatici "
        "sono proposte da verificare, non decisioni definitive.</p></section>"
        f"<h2>Risultati principali</h2><table>{scalar_rows}</table>"
        f"<section class='warning'><h2>Warning e controlli consigliati</h2><ul>{warning_html or '<li>Nessun warning specifico.</li>'}</ul></section>"
        f"<section><h2>Passo successivo consigliato</h2><p>{html.escape(str(next_step))}</p></section>"
        f"{details}",
        encoding="utf-8",
    )
