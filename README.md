# Email Atlas

**Email Atlas non e uno strumento da usare tutti i giorni. E uno strumento di studio per costruire una classificazione utile partendo dall'archivio storico.**

Il progetto prepara conversazioni, dataset, distribuzioni, mappe semantiche, reti di relazioni e categorie candidate. Gli output possono essere esplorati nella GUI, in Orange Data Mining, Excel, LibreOffice, Gephi, Cytoscape o Python. Nessuna email viene spostata e nessun dato viene inviato fuori dal computer.

## Studio Workbench

La GUI ha quattro sezioni:

1. **Prepara Studio**: costruisce dataset puliti e riavviabili.
2. **Esplora Risultati**: apre report, conversazioni, mappe e relazioni.
3. **Esporta per Orange**: produce CSV e istruzioni per analisi visuale esterna.
4. **Costruisci Atlante**: esporta un workspace modificabile e importa decisioni umane.

Avvio Windows:

```text
AVVIA_CONSOLE.bat
```

## Comandi principali

```powershell
email-atlas build-study-dataset --input mail --db data/email_cluster.sqlite --project archivio_storico --output outputs/study_pack
email-atlas export-orange --db data/email_cluster.sqlite --project archivio_storico --output outputs/orange_pack
email-atlas import-classification --db data/email_cluster.sqlite --project archivio_storico --file outputs/study_pack/classification_workspace.csv --output outputs/atlas_finale
```

## Risultati centrali

`outputs/study_pack/` contiene dataset di conversazioni, messaggi, features, punti 2D, similarita, entita, soggetti, termini, allegati, cluster, rete, categorie candidate, workspace e `study_report.html`.

`outputs/orange_pack/` contiene file normalizzati per Orange e quattro workflow suggeriti.

`outputs/atlas_finale/` contiene `atlas_final.csv`, YAML, JSON e HTML derivati soltanto dalle righe approvate nel workspace.

Se gli embedding non sono disponibili, la mappa usa TF-IDF e PCA e lo dichiara nel report. L'LLM locale e facoltativo e non blocca nessun passaggio.

## Documentazione

- [Studio Workbench](docs/studio_workbench.md)
- [Esportazione Orange](docs/orange_export.md)
- [Esplorazione visuale](docs/visual_exploration.md)
- [Classification Workspace](docs/classification_workspace.md)
- [Atlante finale](docs/atlas_finale.md)
- [Guida rapida](docs/guida_rapida.md)
- [Privacy](docs/privacy.md)
- [Troubleshooting](docs/troubleshooting.md)

## Sviluppo

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check src tests
email-atlas smoke-test
```

Ricerca, assistente locale e strumenti precedenti sono disponibili solo in **Avanzate / Legacy**: sono supporti facoltativi, non tappe della classificazione.
