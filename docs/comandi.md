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

## Importare una cartella

```powershell
email-cluster import --source "C:\archivi\mail" --project studio --db data/email_cluster.sqlite
```

## Pulire i testi

```powershell
email-cluster clean --project studio --db data/email_cluster.sqlite
```

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

## Ricerca ed export

```powershell
email-cluster search --query rentri --db data/email_cluster.sqlite
email-cluster search --sender cliente@example.com --db data/email_cluster.sqlite
email-cluster export --format csv --output data/output/export.csv --db data/email_cluster.sqlite
email-cluster report --output data/output/report.md --db data/email_cluster.sqlite
```
