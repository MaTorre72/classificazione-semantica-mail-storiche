# Architettura

Il progetto e' una pipeline batch locale:

```text
archivio email -> parsing -> cleaning -> contesto semantico -> embedding -> clustering -> SQLite
```

Ogni fase legge risultati persistiti dalla fase precedente e scrive nuovi record versionati. Questo permette di cambiare cleaning, modello embedding o parametri di clustering senza ripetere tutto il lavoro.

## Moduli

- `ingestion`: scopre file `.eml`, `.mbox` e MBOX Thunderbird senza estensione.
- `parsing`: usa lo stack standard `email`/`mailbox`, converte HTML con BeautifulSoup e salva metadati allegati.
- `cleaning`: applica regole euristiche tracciate da `cleaning_version`.
- `attachments`: classifica nomi ed estrae selettivamente testo da formati supportati.
- `context`: sceglie current/thread/attachment/exclude e crea `semantic_text_for_embedding`.
- `llm`: arricchimento GGUF locale opzionale con fallback sicuro.
- `embeddings`: usa Sentence Transformers se installato con extra `ml`.
- `clustering`: usa UMAP + HDBSCAN se installati con extra `ml`, poi sintetizza keyword e rappresentanti.
- `storage`: contiene schema SQLite e repository applicativo.
- `export`: produce CSV, JSON e report Markdown.

## Database

Lo schema e' in `src/email_cluster/storage/database.py`. Le tabelle principali sono:

- `projects`
- `source_files`
- `emails`
- `attachments`
- `clean_texts`
- `semantic_contexts`
- `semantic_embeddings`
- `embedding_models`
- `embeddings`
- `clustering_runs`
- `email_clusters`
- `clusters`
- `errors`

## Estensioni consigliate

1. Migrazioni Alembic quando lo schema si stabilizza.
2. Dashboard locale Streamlit dopo avere import/cleaning affidabili.
3. Ricerca vettoriale per query semantiche libere.
4. Modulo allegati separato per PDF, Office, OCR e PEC.
5. Anonimizzazione opzionale prima di report o dataset di test.
