# Workflow consigliato

## Aggiorna archivio

```powershell
email-cluster run --input mail --project archivio_storico --db data/email_cluster.sqlite
```

## Avvia workbench

```powershell
email-cluster workbench --project archivio_storico --db data/email_cluster.sqlite
```

Il workbench crea o aggiorna i contesti operativi dalla run tecnica esistente e indica una sola azione.

## Rivedi

```powershell
email-cluster macro-review --project archivio_storico --db data/email_cluster.sqlite
email-cluster review --next --project archivio_storico --db data/email_cluster.sqlite
```

Azioni principali:

```powershell
email-cluster approve-context --context 12 --db data/email_cluster.sqlite
email-cluster rename-context --context 12 --name "Nome operativo" --db data/email_cluster.sqlite
email-cluster exclude-from-context --context 12 --email-id 123 --db data/email_cluster.sqlite
email-cluster move-to-context --email-id 123 --context 15 --db data/email_cluster.sqlite
email-cluster split-context --context 12 --db data/email_cluster.sqlite
email-cluster mark-context-nonprofessional --context 12 --db data/email_cluster.sqlite
```

## LLM locale opzionale

```powershell
email-cluster ask-context-llm --context 12 --db data/email_cluster.sqlite
```

Se disabilitato, il comando non blocca il workflow. Nessun modello viene scaricato.

## Esporta

```powershell
email-cluster export-final --project archivio_storico --db data/email_cluster.sqlite
email-cluster export-context-report --project archivio_storico --format csv --output data/output/contexts.csv --db data/email_cluster.sqlite
```

## GUI e diagnosi

```powershell
email-cluster-gui
email-cluster doctor --input mail --db data/email_cluster.sqlite
```

I cluster sono supporto tecnico, non la classificazione finale. Consulta [Comandi avanzati](avanzato.md)
solo per tuning, debug o analisi delle run.
