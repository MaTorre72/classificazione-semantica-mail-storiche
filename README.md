# Classificazione semantica mail storiche

Pipeline locale, modulare e ripetibile per importare archivi email, normalizzare il testo, generare embedding, produrre cluster semantici e interrogare i risultati.

La V2 non clusterizza semplicemente il corpo della mail: ricostruisce un contesto operativo usando
messaggio corrente, thread precedente e allegati selezionati, poi genera
`semantic_text_for_embedding`. Tutti i contenuti restano sulla macchina.

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

## Comando consigliato V2

```powershell
email-cluster run --input mail --db data/email_cluster.sqlite --project archivio_storico --profile balanced
```

Il comando rileva ricorsivamente MBOX, EML e cartelle Thunderbird, salta file invariati, elabora solo
email e stadi nuovi, prepara il contesto, genera embedding semantici e aggiorna clustering e report.

```powershell
email-cluster status --project archivio_storico --input mail --db data/email_cluster.sqlite
email-cluster doctor --input mail --db data/email_cluster.sqlite
email-cluster context-report --project archivio_storico --db data/email_cluster.sqlite
email-cluster attachment-report --project archivio_storico --db data/email_cluster.sqlite
email-cluster explain-email --id 42 --db data/email_cluster.sqlite
```

Per aggiungere nuovi archivi basta copiarli nella stessa cartella e rilanciare `run`. Per invalidare
uno stadio in modo esplicito usa `reset-stage`; il comando cancella solo i derivati del progetto.

## Allegati e LLM locale

Il nome e la categoria degli allegati sono sempre usati. L'estrazione testuale opzionale si installa
con `pip install -e .[attachments]`. OCR resta disabilitato. Il sistema funziona senza LLM; un GGUF
locale può essere configurato in `local_llm`, dopo aver installato `.[local-llm]`. Nessun modello viene
scaricato automaticamente e nessuna API cloud viene chiamata.

Per embedding e clustering:

```powershell
.\.venv\Scripts\pip install -e .[ml]
email-cluster embed --project studio --db data/email_cluster.sqlite
email-cluster cluster --project studio --db data/email_cluster.sqlite
email-cluster clusters --db data/email_cluster.sqlite
```

Il cleaning decide quali email sono semanticamente idonee; il clustering lavora solo sugli
embedding di `operational_email` non escluse. Le email escluse restano nel database. Il rumore
HDBSCAN e' diverso: indica email ammesse al clustering ma non assegnate con sufficiente densita'.

Sono disponibili tre profili: `conservative`, `balanced` ed `exploratory`.

```powershell
email-cluster cluster --project studio --profile balanced --db data/email_cluster.sqlite
email-cluster cluster-sweep --project studio --limit 6 --db data/email_cluster.sqlite
email-cluster compare-runs --project studio --db data/email_cluster.sqlite
email-cluster clustering-report --run-id 12 --db data/email_cluster.sqlite
```

Un cluster dominante contiene una quota anomala delle email e viene segnalato automaticamente.
Silhouette, Davies-Bouldin e Calinski-Harabasz aiutano il confronto, ma non misurano da sole la
qualita' semantica: vanno lette insieme a rumore, dimensioni, probabilita' ed esempi rappresentativi.

Per eseguire tutta la pipeline in un comando:

```powershell
email-cluster run-pipeline --source mail --project archivio_storico --db data/email_cluster.sqlite
email-cluster status --db data/email_cluster.sqlite
```

Per aprire una piccola interfaccia grafica locale:

```powershell
email-cluster-gui
```

Su Windows puoi anche usare:

```powershell
.\start_gui.bat
```

## Smoke test reale

Sul campione locale `mail/mail_test_01.mbox` sono stati validati:

- import di 350 email senza errori;
- estrazione metadati di 643 allegati;
- cleaning di 350 testi;
- generazione di 339 embedding con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`;
- clustering di 339 email in 10 cluster piu' rumore.

Gli output runtime (`mail/`, `.venv/`, database SQLite e file in `data/output/`) sono esclusi da Git.

## Pipeline

1. `init-db` crea lo schema SQLite.
2. `import` scansiona cartelle, file `.eml` e `.mbox`, estrae metadati, corpo e allegati.
3. `clean` conserva `clean_text` per compatibilita' e produce `semantic_text` da oggetto e messaggio corrente.
4. `embed` genera embedding locali solo dagli `semantic_text` operativi e sufficientemente informativi.
5. `cluster` applica UMAP e HDBSCAN, salva run, assegnazioni e riepiloghi cluster.
6. `search`, `clusters`, `show-cluster`, `export` e `report` rendono i dati interrogabili.

## Guide operative

- [Uso operativo](docs/uso_operativo.md): client email, IMAP, sicurezza su archivi reali, MBOX enormi e revisione umana dei cluster.
- [Comandi CLI](docs/comandi.md): riferimento rapido dei comandi.
- [Architettura](docs/architettura.md): moduli e responsabilita'.

## Revisione cluster

Per rendere la classificazione piu' umana:

```powershell
email-cluster review-clusters --db data/email_cluster.sqlite --output data/output/cluster_review.csv
email-cluster set-label 0 "Acquisti e notifiche Amazon" --db data/email_cluster.sqlite
email-cluster report --db data/email_cluster.sqlite --output data/output/cluster_report.md
```

## Principi

- Ogni fase e' rieseguibile senza rifare quelle precedenti.
- Ogni elaborazione ha run e metadati persistenti.
- Il parser registra errori per singola email e continua.
- Il database conserva testo estratto e testo pulito per controllare la qualita' del cleaning.
- Tutto resta locale: nessun invio cloud obbligatorio.

## Qualita' del cleaning

`semantic_text` e' l'unico input per embedding e clustering. Firme, disclaimer, risposte citate,
inoltri e footer vengono segmentati e registrati nei flag di cleaning. PEC, newsletter, inviti,
notifiche automatiche, messaggi brevissimi e mail con soli allegati restano nel database ma sono
esclusi dal clustering principale.

```powershell
email-cluster cleaning-report --project archivio_storico --db data/email_cluster.sqlite
email-cluster clean-preview --email-id 42 --db data/email_cluster.sqlite
```

Le soglie e i tipi esclusi si modificano nella sezione `cleaning` di `config/default.yaml`.

## Struttura

```text
src/email_cluster/
  cli/          Comandi Typer
  gui/          Interfaccia grafica locale Tkinter
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
