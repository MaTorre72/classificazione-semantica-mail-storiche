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
- `review_sessions`, `cluster_reviews`, `email_reviews`
- `taxonomy_labels`, `label_examples`, `label_rules`
- `llm_runs`, `llm_cache`, `llm_email_suggestions`, `llm_cluster_suggestions`
- `operational_contexts`, `email_context_assignments`, `context_review_events`

## Revisione V3

La run automatica è immutabile. Una `review_session` sovrappone decisioni umane e proposte LLM,
costruendo una classificazione finale esportabile. Tassonomia, esempi e regole alimentano suggerimenti
progressivi senza training pesante.

## Contesti V3.1

Le macro categorie vengono assegnate prima del raggruppamento. Il cluster è solo una sorgente per
costruire `operational_contexts`; assegnazioni e correzioni umane sono tracciate separatamente. Il
report finale legge i contesti, non i `cluster_id`.
- `errors`

## Estensioni consigliate

1. Migrazioni Alembic quando lo schema si stabilizza.
2. Dashboard locale Streamlit dopo avere import/cleaning affidabili.
3. Ricerca vettoriale per query semantiche libere.
4. Modulo allegati separato per PDF, Office, OCR e PEC.
5. Anonimizzazione opzionale prima di report o dataset di test.
