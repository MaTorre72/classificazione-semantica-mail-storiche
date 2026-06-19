# Comandi CLI

## Creare database

```powershell
email-cluster init-db --db data/email_cluster.sqlite
```

## Eseguire tutta la pipeline

```powershell
email-cluster run-pipeline --source mail --project archivio_storico --db data/email_cluster.sqlite
email-cluster status --db data/email_cluster.sqlite
```

Usa `--skip-ml` se vuoi fermarti a import, cleaning ed export senza embedding/clustering.

## Interfaccia grafica

```powershell
email-cluster-gui
```

La finestra permette di scegliere sorgente, progetto, database e cartella output, poi lanciare i comandi principali senza scriverli a mano. I comandi continuano a girare nella stessa pipeline CLI e il log viene mostrato nella parte bassa della finestra.

Su Windows e' disponibile anche `start_gui.bat` nella cartella del progetto.

## Importare una cartella

```powershell
email-cluster import --source "C:\archivi\mail" --project studio --db data/email_cluster.sqlite
```

## Pulire i testi

```powershell
email-cluster clean --project studio --db data/email_cluster.sqlite
```

Il campo storico `clean_text` contiene il messaggio corrente pulito. `semantic_text` combina
`subject_clean` e `body_current_message_clean` ed e' il solo testo usato dall'ML. Le email
automatiche, PEC, newsletter, inviti, notifiche di consegna, messaggi troppo brevi e mail con soli
allegati sono conservate ma marcate come escluse.

Per controllare il risultato complessivo e ispezionare una singola email:

```powershell
email-cluster cleaning-report --project studio --db data/email_cluster.sqlite
email-cluster clean-preview --email-id 42 --db data/email_cluster.sqlite
```

Il report mostra distribuzione dei tipi, esclusioni, lunghezze e rimozioni effettuate. Configura
`min_semantic_chars`, `min_unique_words`, `max_semantic_chars`, `exclude_message_types` e i pattern
aggiuntivi nella sezione `cleaning` di `config/default.yaml`. Cambia anche `version` quando modifichi
le regole, cosi' il cleaning viene rigenerato senza cancellare lo storico.

## Generare embedding

Richiede:

```powershell
pip install -e .[ml]
```

Poi:

```powershell
email-cluster embed --project studio --db data/email_cluster.sqlite
```

## Clustering

```powershell
email-cluster cluster --project studio --db data/email_cluster.sqlite
email-cluster clusters --db data/email_cluster.sqlite
email-cluster show-cluster 12 --db data/email_cluster.sqlite
```

Il primo comando `embed` puo' scaricare il modello da Hugging Face nella cache utente locale. Su Windows puo' comparire un warning sui symlink della cache: non blocca l'esecuzione, usa solo piu' spazio disco.

## Revisione umana dei cluster

```powershell
email-cluster review-clusters --db data/email_cluster.sqlite --output data/output/cluster_review.csv
email-cluster set-label 2 "Pratiche tecniche e allegati" --db data/email_cluster.sqlite
email-cluster report --db data/email_cluster.sqlite --output data/output/cluster_report.md
```

## Ricerca ed export

```powershell
email-cluster search --query rentri --db data/email_cluster.sqlite
email-cluster search --sender cliente@example.com --db data/email_cluster.sqlite
email-cluster export --format csv --output data/output/export.csv --db data/email_cluster.sqlite
email-cluster report --output data/output/report.md --db data/email_cluster.sqlite
```
