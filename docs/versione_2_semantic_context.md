# Versione 2: contesto semantico operativo

## Stato attuale

La pipeline locale importa EML/MBOX, deduplica le email tramite hash, conserva corpo e metadati,
produce cleaning versionati, embedding Sentence Transformers e clustering UMAP/HDBSCAN. La fase 1
del cleaning separa il messaggio corrente e classifica i tipi non operativi; la fase 2 del clustering
salva profili, metriche, warning e rappresentanti.

## Limiti rilevati

- I file sorgente invariati vengono riletti: la deduplica evita duplicati ma non il costo del parsing.
- Quote, inoltri, firme e disclaimer sono riconosciuti ma non persistiti come blocchi consultabili.
- L'embedding usa `semantic_text`, senza un livello autonomo che ricostruisca thread e allegati.
- Gli allegati conservano solo metadati; non esiste estrazione selettiva o classificazione del nome.
- Non esistono doctor, context report, explain email/cluster e reset controllato degli stadi.
- LLM locale e fallback euristico non hanno ancora un contratto comune.

## Obiettivi V2

Ricostruire il significato operativo prima dell'embedding, mantenere ogni trasformazione verificabile,
rendere la pipeline realmente incrementale per file e stadio e offrire un solo comando operativo.

## Architettura proposta

```text
scan/import incrementale -> parsing -> segmentazione persistente
-> allegati selettivi -> context builder -> arricchimento locale opzionale
-> semantic_text_for_embedding -> embedding incrementali -> clustering/report
```

I nuovi moduli sono `context` (strategie e sintesi thread), `attachments` (classificazione ed
estrazione opzionale) e `llm` (backend locale, cache e fallback). Il cleaning resta responsabile della
normalizzazione e segmentazione; `semantic_contexts` diventa il contratto per embedding e diagnosi.

## Database e migrazione

- `schema_meta`: versione schema applicata.
- `source_files`: dimensione, mtime, conteggi ed errori per import incrementale.
- `emails`: `thread_key` e riferimento run import.
- `clean_texts`: blocchi current/thread/forward/signature/disclaimer/footer.
- `semantic_contexts`: strategia, sintesi, testo embedding, qualità, esclusione e metadati LLM.
- `attachments`: tipo, keyword, estratto, stato ed errore.

Le migrazioni sono additive e idempotenti. Prima di una migrazione di un database esistente viene
creata una copia `.backup-<timestamp>` quando abilitato; non vengono cancellati record legacy.

## Comandi

- `run`: pipeline incrementale completa.
- `import-status`, `status`, `doctor`: stato operativo e ambiente.
- `prepare-context`, `context-report`, `attachment-report`: livello semantico V2.
- `explain-email`, `explain-cluster`: tracciabilità del risultato.
- `reset-stage`: invalidazione esplicita e limitata di uno stadio.
- I comandi `run-pipeline`, `clean`, `embed`, `cluster` e report esistenti restano compatibili.

## Configurazione e dipendenze

La configurazione aggiunge progetto/input, `semantic_preparation`, `attachments`, `local_llm` ed
embedding mode. PDF, DOCX, XLSX e `llama-cpp-python` sono dipendenze opzionali: l'assenza produce uno
stato `unsupported` o fallback euristico, non un errore di pipeline. Nessun modello viene scaricato.

## Rischi

- MBOX enormi richiedono scansione sequenziale quando il file cambia; non esiste indice standard.
- I payload allegato non vengono conservati come BLOB: l'estrazione avviene durante parsing/import.
- Sintesi euristiche di thread e allegati sono meno precise di un LLM, ma deterministiche e locali.
- Un GGUF locale può richiedere RAM significativa; rimane disabilitato di default.

## Test previsti

Import invariato/modificato e deduplica; segmentazione e persistenza blocchi; classificazione tipi;
strategie current/thread/attachment/exclude; estrazione TXT e formati non supportati; fallback LLM;
selezione del testo semantico per embedding; report e comandi principali; migrazione schema V2.

## Autorizzazioni

Non sono necessarie autorizzazioni ulteriori per migrazioni additive, codice e test locali. Download di
modelli GGUF, installazione di OCR o cancellazione/rigenerazione distruttiva richiederanno invece una
richiesta esplicita e non fanno parte dell'upgrade automatico.
