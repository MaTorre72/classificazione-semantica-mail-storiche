from __future__ import annotations

# ruff: noqa: E701, E702

import csv
import hashlib
import html
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from email_cluster.cleaning.normalizer import clean_subject
from email_cluster.ingestion.scanner import scan_local_folder
from email_cluster.parsing.email_parser import parse_eml, parse_mbox
from email_cluster.storage.database import connect, init_db
from email_cluster.storage.repository import Repository, utcnow

ATLAS_VERSION = "atlas-v1"
STOPWORDS = {"della", "delle", "degli", "alla", "alle", "come", "email", "mail", "allegato", "documento", "richiesta", "risposta", "buongiorno", "grazie", "inoltro", "re", "fw", "fwd"}


def _project(con: sqlite3.Connection, name: str) -> int:
    return Repository(con).get_or_create_project(name)


def _write_report(output: Path, title: str, data: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix == ".json":
        output.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return
    rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in data.items() if not isinstance(v, (list, dict)))
    details = "".join(f"<h2>{html.escape(str(k))}</h2><pre>{html.escape(json.dumps(v, ensure_ascii=False, indent=2, default=str))}</pre>" for k, v in data.items() if isinstance(v, (list, dict)))
    output.write_text(f"<!doctype html><meta charset='utf-8'><title>{html.escape(title)}</title><style>body{{font:15px system-ui;max-width:1100px;margin:30px auto;color:#17212b}}table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;border-bottom:1px solid #ddd;text-align:left}}pre{{white-space:pre-wrap;background:#f4f6f7;padding:12px}}</style><h1>{html.escape(title)}</h1><table>{rows}</table>{details}", encoding="utf-8")


def inventory(input_path: Path, db_path: Path, project: str, reports: Path = Path("reports")) -> dict[str, Any]:
    if not input_path.exists():
        raise ValueError(f"Percorso non valido: {input_path}")
    init_db(db_path)
    candidates = scan_local_folder(input_path)
    hashes: Counter[str] = Counter()
    years: list[int] = []
    detected = parseable = attachments = errors = incoming = outgoing = 0
    source_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        found = ok = bad = files_attachments = 0
        try:
            messages = [parse_eml(candidate.path, extract_attachments=False)] if candidate.file_type == "eml" else parse_mbox(candidate.path, extract_attachments=False)
            for message in messages:
                found += 1; detected += 1; ok += 1; parseable += 1
                hashes[message.message_hash] += 1
                attachments += len(message.attachments); files_attachments += len(message.attachments)
                if message.sent_at: years.append(message.sent_at.year)
                if message.sender and "sent" in str(candidate.path).lower(): outgoing += 1
                else: incoming += 1
        except Exception as exc:  # noqa: BLE001
            bad += 1; errors += 1
            source_rows.append({"path": str(candidate.path), "type": candidate.file_type, "error": str(exc)})
        else:
            source_rows.append({"path": str(candidate.path), "type": candidate.file_type, "messages": found, "parseable": ok, "errors": bad, "attachments": files_attachments})
    result = {"project": project, "input": str(input_path), "sources": len(candidates), "files": len(candidates),
              "emails_detected": detected, "emails_parseable": parseable, "probable_duplicates": sum(n - 1 for n in hashes.values() if n > 1),
              "year_start": min(years) if years else None, "year_end": max(years) if years else None,
              "incoming_estimate": incoming, "outgoing_estimate": outgoing, "attachments": attachments,
              "errors": errors, "warnings": (["La direzione ricevuta/inviata è stimata dal percorso della sorgente."] if candidates else ["Nessuna sorgente email trovata."]), "source_details": source_rows}
    _write_report(reports / "inventory_report.json", "Inventario archivio", result)
    _write_report(reports / "inventory_report.html", "Inventario archivio", result)
    return result


def parse_and_clean(db_path: Path, project: str, config_path: Path = Path("config/default.yaml"), reports: Path = Path("reports"), force: bool = False) -> dict[str, Any]:
    from email_cluster.cli.app import clean, prepare_context

    init_db(db_path)
    if force:
        raise ValueError("La rigenerazione invasiva richiede il comando update con conferma e backup.")
    clean(project=project, db=db_path, config=config_path)
    prepare_context(project=project, db=db_path, config=config_path)
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        total = con.execute("SELECT count(*) FROM emails WHERE project_id=?", (pid,)).fetchone()[0]
        cleaned = con.execute("SELECT count(DISTINCT c.email_id) FROM clean_texts c JOIN emails e ON e.id=c.email_id WHERE e.project_id=?", (pid,)).fetchone()[0]
        segmented = con.execute("SELECT count(DISTINCT c.email_id) FROM clean_texts c JOIN emails e ON e.id=c.email_id WHERE e.project_id=? AND (c.quoted_thread_text!='' OR c.forwarded_text!='' OR c.signature_text!='' OR c.disclaimer_text!='')", (pid,)).fetchone()[0]
        poor = con.execute("SELECT count(DISTINCT c.email_id) FROM clean_texts c JOIN emails e ON e.id=c.email_id WHERE e.project_id=? AND c.quality_score<0.4", (pid,)).fetchone()[0]
    result = {"project": project, "emails": total, "cleaned": cleaned, "segmented": segmented, "low_quality": poor, "version": ATLAS_VERSION}
    _write_report(reports / "parsing_report.html", "Parsing archivio", result)
    _write_report(reports / "cleaning_report.html", "Pulizia testi", result)
    return result


def _normalize_mid(value: str | None) -> str:
    return (value or "").strip().strip("<>").lower()


def _header_ids(value: Any) -> list[str]:
    return [_normalize_mid(item) for item in re.findall(r"<([^>]+)>", str(value or "")) if item]


def build_conversations(db_path: Path, project: str, accounts: list[str] | None = None, reports: Path = Path("reports")) -> dict[str, Any]:
    init_db(db_path); accounts = [x.lower() for x in (accounts or [])]
    with connect(db_path) as con:
        pid = Repository(con).project_id(project)
        rows = [dict(r) for r in con.execute("""SELECT e.*,c.subject_clean,c.current_message_text,c.quoted_thread_text,c.forwarded_text
            FROM emails e LEFT JOIN clean_texts c ON c.id=(SELECT max(c2.id) FROM clean_texts c2 WHERE c2.email_id=e.id)
            WHERE e.project_id=? ORDER BY coalesce(e.sent_at,e.imported_at),e.id""", (pid,))]
        parent = {r["id"]: r["id"] for r in rows}
        def find(x: int) -> int:
            while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
            return x
        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb: parent[rb] = ra
        by_mid = {_normalize_mid(r["original_message_id"]): r["id"] for r in rows if _normalize_mid(r["original_message_id"])}
        methods: dict[int, str] = {r["id"]: "isolated" for r in rows}
        subjects: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            headers = json.loads(row["raw_headers_json"] or "{}")
            linked = _header_ids(headers.get("References")) + _header_ids(headers.get("In-Reply-To"))
            matched = [by_mid[x] for x in linked if x in by_mid]
            if matched:
                for target in matched: union(row["id"], target)
                methods[row["id"]] = "headers"
            subject = clean_subject(row["subject"] or "").lower()
            if subject: subjects[subject].append(row)
        for subject, items in subjects.items():
            if len(subject) < 8 or subject in {"documenti", "informazioni", "richiesta", "aggiornamento"}: continue
            for previous, current in zip(items, items[1:]):
                if methods[current["id"]] == "headers": continue
                try:
                    delta = abs((datetime.fromisoformat(current["sent_at"]) - datetime.fromisoformat(previous["sent_at"])).days)
                except (TypeError, ValueError): delta = 999
                participants_a = set(json.loads(previous["recipients"] or "[]")) | {previous["sender"] or ""}
                participants_b = set(json.loads(current["recipients"] or "[]")) | {current["sender"] or ""}
                if delta <= 45 and participants_a & participants_b:
                    union(previous["id"], current["id"]); methods[current["id"]] = "subject_participants_date"
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows: groups[find(row["id"])].append(row)
        con.execute("DELETE FROM atlas_conversation_messages WHERE conversation_id IN (SELECT id FROM atlas_conversations WHERE project_id=?)", (pid,))
        con.execute("DELETE FROM atlas_conversations WHERE project_id=?", (pid,))
        low = isolated = 0
        for members in groups.values():
            members.sort(key=lambda x: (x["sent_at"] or x["imported_at"], x["id"]))
            explicit = sum(methods[x["id"]] == "headers" for x in members); fallback = sum(methods[x["id"]] == "subject_participants_date" for x in members)
            method = "headers" if explicit else "subject_participants_date" if fallback else "isolated"
            confidence = 0.95 if explicit else 0.65 if fallback else 0.4
            if confidence < 0.6: low += 1
            if len(members) == 1: isolated += 1
            participants = sorted({p.lower() for x in members for p in ([x["sender"]] + json.loads(x["recipients"] or "[]")) if p})
            texts=[]; seen=set()
            for x in members:
                text=(x["current_message_text"] or x["body_extracted_text"] or "").strip()
                key=hashlib.sha256(text.encode("utf-8",errors="replace")).hexdigest()
                if text and key not in seen: texts.append(text); seen.add(key)
            analysis=(clean_subject(members[-1]["subject"] or "")+"\n\n"+"\n\n".join(texts))[:50000]
            stable=hashlib.sha256("|".join(str(x["id"]) for x in members).encode()).hexdigest()
            incoming=sum(not any(a in (x["sender"] or "").lower() for a in accounts) for x in members) if accounts else len(members)
            outgoing=len(members)-incoming
            warnings=[] if method=="headers" else ["Relazione ricostruita senza catena completa di header."]
            cur=con.execute("""INSERT INTO atlas_conversations(project_id,stable_key,subject_normalized,date_start,date_end,message_count,
                incoming_count,outgoing_count,attachments_count,participants_json,unique_clean_text,analysis_text,confidence,reconstruction_method,
                warnings_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(pid,stable,clean_subject(members[-1]["subject"] or ""),members[0]["sent_at"],members[-1]["sent_at"],len(members),incoming,outgoing,sum(x["has_attachments"] or 0 for x in members),json.dumps(participants,ensure_ascii=False),"\n\n".join(texts),analysis,confidence,method,json.dumps(warnings,ensure_ascii=False),utcnow(),utcnow()))
            cid=int(cur.lastrowid)
            con.executemany("INSERT INTO atlas_conversation_messages(conversation_id,email_id,position,relation_method,relation_confidence) VALUES(?,?,?,?,?)",[(cid,x["id"],i,methods[x["id"]],confidence) for i,x in enumerate(members)])
    result={"project":project,"emails":len(rows),"conversations":len(groups),"reduction_ratio":round(1-len(groups)/max(len(rows),1),3),"isolated":isolated,"low_confidence":low,"mean_messages":round(len(rows)/max(len(groups),1),2)}
    _write_report(reports/"conversation_report.html","Conversazioni ricostruite",result); return result


def build_index(db_path: Path, project: str) -> dict[str, Any]:
    init_db(db_path)
    with connect(db_path) as con:
        pid=Repository(con).project_id(project)
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS atlas_search USING fts5(document_type UNINDEXED,source_id UNINDEXED,project_id UNINDEXED,subject,content,participants,attachments,entities,tokenize='unicode61 remove_diacritics 2')")
        con.execute("DELETE FROM atlas_search WHERE project_id=?",(pid,))
        conversations=list(con.execute("""SELECT ac.*,group_concat(a.filename,' ') attachment_names FROM atlas_conversations ac
            LEFT JOIN atlas_conversation_messages cm ON cm.conversation_id=ac.id LEFT JOIN attachments a ON a.email_id=cm.email_id
            WHERE ac.project_id=? GROUP BY ac.id""",(pid,)))
        con.executemany("INSERT INTO atlas_search(document_type,source_id,project_id,subject,content,participants,attachments,entities) VALUES('conversation',?,?,?,?,?,?,?)",[(r["id"],pid,r["subject_normalized"],r["analysis_text"],r["participants_json"],r["attachment_names"] or "","") for r in conversations])
    return {"indexed_conversations":len(conversations)}


def search(db_path: Path, query: str, project: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    with connect(db_path) as con:
        pid=Repository(con).project_id(project) if project else None
        clauses="atlas_search MATCH ?"+(" AND project_id=?" if pid else "")
        params=[query]+([pid] if pid else [])+[limit]
        rows=con.execute(f"""SELECT document_type,source_id,subject,snippet(atlas_search,4,'[',']',' … ',18) evidence,bm25(atlas_search) score
            FROM atlas_search WHERE {clauses} ORDER BY score LIMIT ?""",params)
        return [dict(r) for r in rows]


def extract_entities(db_path: Path, project: str, config_dir: Path = Path("config/entities"), reports: Path = Path("reports")) -> dict[str, Any]:
    init_db(db_path); dictionaries={}
    for name in ("clients","sites","public_bodies","suppliers","technical_terms","exclusion_terms"):
        path=config_dir/f"{name}.yaml"; dictionaries[name]=yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else []
    with connect(db_path) as con:
        pid=Repository(con).project_id(project); con.execute("DELETE FROM atlas_entity_mentions WHERE entity_id IN(SELECT id FROM atlas_entities WHERE project_id=?)",(pid,)); con.execute("DELETE FROM atlas_entities WHERE project_id=?",(pid,))
        rows=list(con.execute("SELECT id,sender,subject,body_extracted_text FROM emails WHERE project_id=?",(pid,)))
        found:dict[tuple[str,str],dict[str,Any]]={}
        for row in rows:
            sender=row["sender"] or ""
            match=re.search(r"@([\w.-]+)",sender)
            candidates=[]
            if match: candidates.append(("domain",match.group(1).lower(),match.group(1).lower(),sender))
            text=f"{row['subject'] or ''}\n{row['body_extracted_text'] or ''}"
            for kind, entries in dictionaries.items():
                for entry in entries or []:
                    value=entry if isinstance(entry,str) else entry.get("name","")
                    aliases=[value]+([] if isinstance(entry,str) else entry.get("aliases",[]))
                    if value and any(re.search(rf"\b{re.escape(a)}\b",text,re.I) for a in aliases): candidates.append((kind.rstrip("s"),value.lower(),value,value))
            for kind,key,display,evidence in candidates:
                item=found.setdefault((kind,key),{"display":display,"mentions":[]}); item["mentions"].append((row["id"],evidence))
        for (kind,key),item in found.items():
            cur=con.execute("INSERT INTO atlas_entities(project_id,entity_type,normalized_name,display_name,frequency,confidence,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,0.8,'{}',?,?)",(pid,kind,key,item["display"],len(item["mentions"]),utcnow(),utcnow())); eid=int(cur.lastrowid)
            con.executemany("INSERT OR IGNORE INTO atlas_entity_mentions(entity_id,email_id,evidence,created_at) VALUES(?,?,?,?)",[(eid,email,evidence,utcnow()) for email,evidence in item["mentions"]])
    result={"entities":len(found),"by_type":dict(Counter(k[0] for k in found))}; _write_report(reports/"entity_report.html","Entità ricorrenti",result); return result


def build_semantic_docs(db_path: Path, project: str) -> dict[str, Any]:
    init_db(db_path)
    with connect(db_path) as con:
        pid=Repository(con).project_id(project); rows=list(con.execute("SELECT * FROM atlas_conversations WHERE project_id=?",(pid,)))
        created=0
        for row in rows:
            entities=[x[0] for x in con.execute("""SELECT DISTINCT ae.display_name FROM atlas_entities ae JOIN atlas_entity_mentions em ON em.entity_id=ae.id
                JOIN atlas_conversation_messages cm ON cm.email_id=em.email_id WHERE cm.conversation_id=? ORDER BY ae.frequency DESC LIMIT 20""",(row["id"],))]
            attachments=[x[0] for x in con.execute("""SELECT DISTINCT a.filename FROM attachments a JOIN atlas_conversation_messages cm ON cm.email_id=a.email_id WHERE cm.conversation_id=? AND a.filename IS NOT NULL LIMIT 20""",(row["id"],))]
            content=(f"Oggetto: {row['subject_normalized']}\nPartecipanti: {', '.join(json.loads(row['participants_json'] or '[]'))}\nEntità: {', '.join(entities)}\nAllegati: {', '.join(attachments)}\n\n{row['analysis_text'] or ''}")[:60000]
            digest=hashlib.sha256(content.encode()).hexdigest()
            con.execute("""INSERT INTO atlas_semantic_documents(project_id,document_level,source_id,version,content_hash,content,metadata_json,created_at)
                VALUES(?,'conversation',?,?,?,?,?,?) ON CONFLICT(document_level,source_id,version) DO UPDATE SET content_hash=excluded.content_hash,content=excluded.content,metadata_json=excluded.metadata_json,created_at=excluded.created_at""",(pid,row["id"],ATLAS_VERSION,digest,content,json.dumps({"entities":entities,"attachments":attachments},ensure_ascii=False),utcnow())); created+=1
    return {"conversation_documents":created,"version":ATLAS_VERSION}


def embed_documents(db_path: Path, project: str, model_name: str, batch_size: int = 16, low_power: bool = False) -> dict[str, Any]:
    from email_cluster.embeddings.engine import EmbeddingEngine
    from email_cluster.storage.repository import embedding_to_blob
    import time

    init_db(db_path); engine=EmbeddingEngine(model_name)
    with connect(db_path) as con:
        pid=Repository(con).project_id(project)
        con.execute("""CREATE TABLE IF NOT EXISTS atlas_embedding_cache(id INTEGER PRIMARY KEY AUTOINCREMENT,semantic_document_id INTEGER NOT NULL,
            model_name TEXT NOT NULL,content_hash TEXT NOT NULL,embedding BLOB NOT NULL,created_at TEXT NOT NULL,UNIQUE(semantic_document_id,model_name,content_hash))""")
        docs=list(con.execute("""SELECT d.* FROM atlas_semantic_documents d WHERE d.project_id=? AND d.document_level='conversation'
            AND NOT EXISTS(SELECT 1 FROM atlas_embedding_cache e WHERE e.semantic_document_id=d.id AND e.model_name=? AND e.content_hash=d.content_hash)""",(pid,model_name)))
        done=0
        for start in range(0,len(docs),batch_size):
            for doc in docs[start:start+batch_size]:
                vector=engine.embed_email(doc["content"],2000,200); con.execute("INSERT OR IGNORE INTO atlas_embedding_cache(semantic_document_id,model_name,content_hash,embedding,created_at) VALUES(?,?,?,?,?)",(doc["id"],model_name,doc["content_hash"],embedding_to_blob(vector),utcnow())); done+=1
            con.commit()
            if low_power: time.sleep(1)
    return {"embedded":done,"cached":max(len(docs)-done,0),"model":model_name}


def _scope_for_text(text: str) -> str:
    value=text.lower()
    if any(x in value for x in ("newsletter","unsubscribe","evento","webinar")): return "Newsletter / eventi"
    if any(x in value for x in ("ordine","spedizione","amazon","acquisto")): return "Acquisti / spedizioni"
    if any(x in value for x in ("fattura","pagamento","preventivo")): return "Amministrativo / fornitori"
    if any(x in value for x in ("rifiuti","emissioni","autorizz","via","aia","seveso","reach")): return "Professionale operativo"
    return "Professionale generale"


def discover(db_path: Path, project: str, min_conversations: int = 3, max_categories: int = 30, reports: Path = Path("reports")) -> dict[str, Any]:
    init_db(db_path)
    with connect(db_path) as con:
        pid=Repository(con).project_id(project); con.execute("DELETE FROM atlas_candidate_conversations WHERE candidate_id IN(SELECT id FROM atlas_candidate_categories WHERE project_id=?)",(pid,)); con.execute("DELETE FROM atlas_candidate_categories WHERE project_id=? AND status='candidate'",(pid,))
        docs=list(con.execute("""SELECT d.source_id conversation_id,d.content,ac.subject_normalized,ac.participants_json FROM atlas_semantic_documents d
            JOIN atlas_conversations ac ON ac.id=d.source_id WHERE d.project_id=? AND d.document_level='conversation'""",(pid,)))
        buckets:dict[tuple[str,str],list[sqlite3.Row]]=defaultdict(list)
        for row in docs:
            words=[w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{4,}",row["subject_normalized"] or "") if w.lower() not in STOPWORDS]
            signal=words[0] if words else "altro"; buckets[(_scope_for_text(row["content"]),signal)].append(row)
        ordered=sorted(buckets.items(),key=lambda x:len(x[1]),reverse=True)[:max_categories]
        small=0
        for (scope,signal),members in ordered:
            fragmented=len(members)<min_conversations; small+=int(fragmented)
            domains=Counter(re.findall(r"@([\w.-]+)"," ".join(r["participants_json"] or "" for r in members))).most_common(8)
            cur=con.execute("""INSERT INTO atlas_candidate_categories(project_id,name,scope,description,lexical_signals_json,recurring_domains_json,
                rationale,confidence,conversation_count,is_fragmented,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,'candidate',?,?)""",(pid,signal.title(),scope,f"Conversazioni relative a {signal}.",json.dumps([signal]),json.dumps([x[0] for x in domains]),"Ricorrenza nell'oggetto delle Conversazioni",min(0.9,0.45+len(members)/20),len(members),int(fragmented),utcnow(),utcnow())); cid=int(cur.lastrowid)
            con.executemany("INSERT INTO atlas_candidate_conversations(candidate_id,conversation_id,relevance,representative) VALUES(?,?,?,?)",[(cid,r["conversation_id"],1.0,int(i<3)) for i,r in enumerate(members)])
        total=len(ordered); warning="Troppe Categorie rispetto alle Conversazioni." if total>max(len(docs)//5,10) else None
    result={"conversations":len(docs),"candidate_categories":total,"small_categories":small,"ratio":round(total/max(len(docs),1),3),"warning":warning}
    _write_report(reports/"discovery_report.html","Categorie candidate",result); return result


def review_action(db_path: Path, project: str, candidate_id: int, action: str, name: str | None = None, notes: str = "") -> dict[str, Any]:
    allowed={"approve","rename","exclude","deprecate","ambiguous","merge"}
    if action not in allowed: raise ValueError("Azione di revisione non supportata")
    with connect(db_path) as con:
        pid=Repository(con).project_id(project); row=con.execute("SELECT * FROM atlas_candidate_categories WHERE id=? AND project_id=?",(candidate_id,pid)).fetchone()
        if not row: raise ValueError("Categoria candidata non trovata")
        before=dict(row); status={"approve":"approved","rename":"candidate","exclude":"excluded","deprecate":"deprecated","ambiguous":"ambiguous","merge":"to_merge"}[action]
        con.execute("UPDATE atlas_candidate_categories SET name=coalesce(?,name),status=?,updated_at=? WHERE id=?",(name,status,utcnow(),candidate_id))
        if action=="approve":
            con.execute("""INSERT INTO atlas_categories(project_id,candidate_id,scope,operational_theme,description,lexical_signals_json,
                recurring_domains_json,assignment_criterion,status,confidence,source,last_reviewed_at,notes,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,'human',?,?,?,?)""",(pid,candidate_id,row["scope"],name or row["name"],row["description"],row["lexical_signals_json"],row["recurring_domains_json"],row["rationale"],"approved",row["confidence"],utcnow(),notes,utcnow(),utcnow()))
        after=dict(con.execute("SELECT * FROM atlas_candidate_categories WHERE id=?",(candidate_id,)).fetchone()); con.execute("INSERT INTO atlas_review_decisions(project_id,target_type,target_id,action,before_json,after_json,notes,created_at) VALUES(?,'candidate',?,?,?,?,?,?)",(pid,candidate_id,action,json.dumps(before,default=str),json.dumps(after,default=str),notes,utcnow()))
    return after


def export_atlas(db_path: Path, project: str, output: Path, public_safe: bool = False) -> dict[str, Any]:
    output.mkdir(parents=True,exist_ok=True)
    with connect(db_path) as con:
        pid=Repository(con).project_id(project); rows=[dict(r) for r in con.execute("SELECT * FROM atlas_categories WHERE project_id=? AND status!='deprecated' ORDER BY scope,operational_theme",(pid,))]
    data=[]
    for row in rows:
        item={"id":row["id"],"ambito":row["scope"],"soggetto_tipo":row["subject_type"],"soggetto_nome":None if public_safe else row["subject_name"],"contesto_tipo":row["context_type"],"contesto_nome":None if public_safe else row["context_name"],"tema_operativo":row["operational_theme"],"descrizione":row["description"],"segnali_lessicali":json.loads(row["lexical_signals_json"] or "[]"),"mittenti_ricorrenti":[] if public_safe else json.loads(row["recurring_senders_json"] or "[]"),"domini_ricorrenti":[] if public_safe else json.loads(row["recurring_domains_json"] or "[]"),"allegati_tipici":json.loads(row["typical_attachments_json"] or "[]"),"casi_da_escludere":json.loads(row["exclusions_json"] or "[]"),"categorie_vicine":json.loads(row["near_categories_json"] or "[]"),"criterio_assegnazione":row["assignment_criterion"],"stato":row["status"],"affidabilita":row["confidence"],"fonte":row["source"],"ultima_revisione":row["last_reviewed_at"],"note":row["notes"]}; data.append(item)
    (output/"atlas.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8"); (output/"atlas.yaml").write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding="utf-8")
    fields=list(data[0]) if data else ["id","ambito","tema_operativo"]
    with (output/"atlas.csv").open("w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields); writer.writeheader(); writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,list) else v for k,v in x.items()} for x in data)
    try:
        from openpyxl import Workbook
        book=Workbook(); sheet=book.active; sheet.title="Atlante"; sheet.append(fields)
        for item in data: sheet.append([json.dumps(item.get(k),ensure_ascii=False) if isinstance(item.get(k),list) else item.get(k) for k in fields])
        book.save(output/"atlas.xlsx")
    except ImportError:
        pass
    md=["# Atlante semantico",""]+[f"## {x['ambito']} — {x['tema_operativo']}\n\n{x['descrizione'] or ''}\n\n- Stato: {x['stato']}\n- Affidabilità: {x['affidabilita']}" for x in data]; (output/"atlas.md").write_text("\n\n".join(md),encoding="utf-8")
    _write_report(output/"atlas.html","Atlante semantico",{"project":project,"categories":len(data),"public_safe":public_safe,"atlas":data})
    return {"categories":len(data),"output":str(output),"public_safe":public_safe}


def evaluate(db_path: Path, project: str, reports: Path = Path("reports")) -> dict[str, Any]:
    with connect(db_path) as con:
        pid=Repository(con).project_id(project); emails=con.execute("SELECT count(*) FROM emails WHERE project_id=?",(pid,)).fetchone()[0]; conversations=con.execute("SELECT count(*) FROM atlas_conversations WHERE project_id=?",(pid,)).fetchone()[0]; candidates=con.execute("SELECT count(*) FROM atlas_candidate_categories WHERE project_id=?",(pid,)).fetchone()[0]; approved=con.execute("SELECT count(*) FROM atlas_categories WHERE project_id=? AND status='approved'",(pid,)).fetchone()[0]; small=con.execute("SELECT count(*) FROM atlas_candidate_categories WHERE project_id=? AND is_fragmented=1",(pid,)).fetchone()[0]; ambiguous=con.execute("SELECT count(*) FROM atlas_candidate_categories WHERE project_id=? AND status='ambiguous'",(pid,)).fetchone()[0]
    ratio=candidates/max(conversations,1); judgement="fragile" if not conversations or not candidates else "troppo frammentato" if ratio>0.25 else "accettabile" if not approved else "buono"
    result={"emails":emails,"conversations":conversations,"email_to_conversation_reduction":round(1-conversations/max(emails,1),3),"candidate_categories":candidates,"approved_categories":approved,"categories_per_conversation":round(ratio,3),"small_categories":small,"ambiguous":ambiguous,"judgement":judgement}
    _write_report(reports/"evaluation_report.html","Valutazione Atlante",result); return result


def update_archive(input_path: Path, db_path: Path, project: str, config_path: Path = Path("config/default.yaml")) -> dict[str, Any]:
    from email_cluster.cli.app import import_emails
    init_db(db_path); import_emails(source=input_path,project=project,db=db_path,config=config_path); parsed=parse_and_clean(db_path,project,config_path); conversations=build_conversations(db_path,project); indexed=build_index(db_path,project); entities=extract_entities(db_path,project); docs=build_semantic_docs(db_path,project); discovery=discover(db_path,project)
    result={"parse":parsed,"conversations":conversations,"index":indexed,"entities":entities,"semantic_docs":docs,"discovery":discovery}; _write_report(Path("reports/update_report.html"),"Aggiornamento Atlante",result); return result
