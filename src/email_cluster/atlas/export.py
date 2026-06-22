from __future__ import annotations

# Extracted mechanically from the original facade. Keep imports explicit at module boundaries.
# ruff: noqa: E701, E702

import csv
import json
from pathlib import Path
from typing import Any

import yaml

from email_cluster.storage.database import connect
from email_cluster.storage.repository import Repository

from .reports import write_report
from .privacy import public_safe_category


def export_atlas(
    db_path: Path, project: str, output: Path, public_safe: bool = False
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        rows = [
            dict(r)
            for r in con.execute(
                "SELECT * FROM atlas_categories WHERE project_id=? AND status!='deprecated' ORDER BY scope,operational_theme",
                (pid,),
            )
        ]
    data = []
    for row in rows:
        item = {
            "id": row["id"],
            "ambito": row["scope"],
            "soggetto_tipo": row["subject_type"],
            "soggetto_nome": None if public_safe else row["subject_name"],
            "contesto_tipo": row["context_type"],
            "contesto_nome": None if public_safe else row["context_name"],
            "tema_operativo": row["operational_theme"],
            "descrizione": row["description"],
            "segnali_lessicali": json.loads(row["lexical_signals_json"] or "[]"),
            "mittenti_ricorrenti": []
            if public_safe
            else json.loads(row["recurring_senders_json"] or "[]"),
            "domini_ricorrenti": []
            if public_safe
            else json.loads(row["recurring_domains_json"] or "[]"),
            "allegati_tipici": json.loads(row["typical_attachments_json"] or "[]"),
            "casi_da_escludere": json.loads(row["exclusions_json"] or "[]"),
            "categorie_vicine": json.loads(row["near_categories_json"] or "[]"),
            "criterio_assegnazione": row["assignment_criterion"],
            "stato": row["status"],
            "affidabilita": row["confidence"],
            "fonte": row["source"],
            "ultima_revisione": row["last_reviewed_at"],
            "note": row["notes"],
        }
        data.append(public_safe_category(item) if public_safe else item)
    (output / "atlas.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "atlas.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    fields = list(data[0]) if data else ["id", "ambito", "tema_operativo"]
    with (output / "atlas.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v
                for k, v in x.items()
            }
            for x in data
        )
    try:
        from openpyxl import Workbook

        book = Workbook()
        sheet = book.active
        sheet.title = "Atlante"
        sheet.append(fields)
        for item in data:
            sheet.append(
                [
                    json.dumps(item.get(k), ensure_ascii=False)
                    if isinstance(item.get(k), list)
                    else item.get(k)
                    for k in fields
                ]
            )
        book.save(output / "atlas.xlsx")
    except ImportError:
        pass
    md = ["# Atlante semantico", ""] + [
        f"## {x['ambito']} — {x['tema_operativo']}\n\n{x['descrizione'] or ''}\n\n- Stato: {x['stato']}\n- Affidabilità: {x['affidabilita']}"
        for x in data
    ]
    (output / "atlas.md").write_text("\n\n".join(md), encoding="utf-8")
    write_report(
        output / "atlas.html",
        "Atlante semantico",
        {"project": project, "categories": len(data), "public_safe": public_safe, "atlas": data},
    )
    return {"categories": len(data), "output": str(output), "public_safe": public_safe}
