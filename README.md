# Email Atlas

Email Atlas trasforma archivi email storici EML/MBOX in un atlante locale di conversazioni e categorie revisionabili. Non modifica i file sorgente e non invia dati al cloud.

## A cosa serve

Aiuta a capire quali pratiche, soggetti e temi ricorrono in archivi grandi, mantenendo la decisione finale nelle mani dell'utente.

## Flusso consigliato

1. Inventario dei file.
2. Parsing e pulizia.
3. Ricostruzione e verifica delle conversazioni.
4. Indicizzazione, entita e documenti semantici.
5. Discovery euristica provvisoria.
6. Revisione umana, esportazione e valutazione.

## Avvio rapido

Su Windows avvia `AVVIA_CONSOLE.bat`. La console locale apre `http://127.0.0.1:8765` e guida tutte le fasi. Inserisci la cartella dell'archivio e premi un comando alla volta, controllando risultato e report prima di proseguire.

## Installazione

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e .[dev,ml,ui]
```

## Interfaccia grafica

La GUI e il punto di accesso principale: mostra stato, prossimo passo, conversazioni, ricerca, revisione e report. Le operazioni che ricostruiscono dati o generano proposte chiedono conferma. Vedi [guida GUI](docs/gui.md).

## CLI avanzata

```powershell
email-atlas inventory --input mail --db data/email_cluster.sqlite --project archivio_storico
email-atlas update --input mail --db data/email_cluster.sqlite --project archivio_storico
email-atlas search --db data/email_cluster.sqlite --project archivio_storico --query "contratto alfa"
email-atlas export-atlas --db data/email_cluster.sqlite --project archivio_storico --output data/atlas
```

Usa `email-atlas --help` e `email-atlas COMANDO --help` per le opzioni.

## Output

Il database SQLite resta in `data/`. I report HTML/JSON sono in `reports/`; l'Atlante esportato puo essere JSON, YAML, CSV, XLSX, Markdown e HTML. Ogni report indica sintesi, risultati, warning e passo successivo.

## Discovery ed embedding

La discovery attuale e **euristica e provvisoria**: combina termini degli oggetti, entita, domini ricorrenti e nomi degli allegati. Gli embedding possono essere calcolati e memorizzati, ma **non guidano ancora la discovery**. Le proposte non sono classificazioni definitive.

## Privacy

L'elaborazione e locale. `--public-safe` rimuove nomi di soggetti, contesti, mittenti e domini dall'export; non sostituisce una valutazione privacy sul dataset. Vedi [privacy](docs/privacy.md).

## Documentazione

- [Primi passi](docs/primi_passi.md)
- [Guida rapida](docs/guida_rapida.md)
- [Pipeline](docs/pipeline.md)
- [Revisione umana](docs/revisione_umana.md)
- [Aggiornamenti periodici](docs/aggiornamento_periodico.md)
- [Glossario](docs/glossario.md)
- [Risoluzione problemi](docs/troubleshooting.md)
- [Revisione UX](docs/ux_review.md)

## Verifica per sviluppatori

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check src tests
email-atlas smoke-test
```

## Funzioni precedenti

Il comando `email-cluster` e le schermate precedenti restano disponibili da **Funzioni precedenti** per compatibilita. Il percorso raccomandato per nuovo lavoro e Email Atlas.
