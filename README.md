# Classificazione semantica mail storiche

Pipeline locale, modulare e ripetibile per importare archivi email, normalizzare il testo, generare embedding, produrre cluster semantici e interrogare i risultati.

La prima versione e' una CLI Python con database SQLite. Le fasi pesanti di machine learning sono opzionali: il progetto puo' importare, pulire, cercare ed esportare email anche senza installare i pacchetti `ml`.

## Avvio rapido

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e .[dev]
email-cluster init-db --db data/email_cluster.sqlite
email-cluster import --source data/input --project studio --db data/email_cluster.sqlite
email-cluster clean --project studio --db data/email_cluster.sqlite
email-cluster search --query rentri --db data/email_cluster.sqlite
email-cluster export --format csv --output data/output/emails.csv --db data/email_cluster.sqlite
```

Per embedding e clustering:

```powershell
.\.venv\Scripts\pip install -e .[ml]
email-cluster embed --project studio --db data/email_cluster.sqlite
email-cluster cluster --project studio --db data/email_cluster.sqlite
email-cluster clusters --db data/email_cluster.sqlite
```

## Pipeline

1. `init-db` crea lo schema SQLite.
2. `import` scansiona cartelle, file `.eml` e `.mbox`, estrae metadati, corpo e allegati.
3. `clean` produce `clean_text` tracciato e versionato.
4. `embed` genera embedding locali con Sentence Transformers.
5. `cluster` applica UMAP e HDBSCAN, salva run, assegnazioni e riepiloghi cluster.
6. `search`, `clusters`, `show-cluster`, `export` e `report` rendono i dati interrogabili.

## Principi

- Ogni fase e' rieseguibile senza rifare quelle precedenti.
- Ogni elaborazione ha run e metadati persistenti.
- Il parser registra errori per singola email e continua.
- Il database conserva testo estratto e testo pulito per controllare la qualita' del cleaning.
- Tutto resta locale: nessun invio cloud obbligatorio.

## Struttura

```text
src/email_cluster/
  cli/          Comandi Typer
  ingestion/    Scansione file locali
  parsing/      Parser EML/MBOX
  cleaning/     Regole euristiche verificabili
  embeddings/   Embedding locali opzionali
  clustering/   UMAP/HDBSCAN opzionali
  storage/      Schema SQLite e repository
  export/       CSV/JSON/report
docs/
config/
tests/
data/
```

