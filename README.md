# Classificazione semantica mail storiche

Strumento locale per trasformare archivi MBOX/EML in **contesti operativi comprensibili**: pratiche,
adempimenti, temi tecnici, documentazione e conversazioni. I cluster sono solo un supporto tecnico;
la classificazione finale è costruita e confermata dall'utente.

Tutto resta sul computer: nessuna API cloud, telemetria o invio di email e allegati.

## Installazione

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e .[dev,ml]
```

## Uso normale

### 1. Importa o aggiorna l'archivio

```powershell
email-cluster run --input mail --project archivio_storico --db data/email_cluster.sqlite
```

Puoi aggiungere nuovi MBOX nella stessa cartella e rilanciare il comando: file ed email già elaborati
vengono saltati.

### 2. Apri il workbench

```powershell
email-cluster workbench --project archivio_storico --db data/email_cluster.sqlite
```

Mostra stato archivio, macro categorie e **una sola prossima azione consigliata**.

### 3. Controlla macro categorie e prossimo contesto

```powershell
email-cluster macro-review --project archivio_storico --db data/email_cluster.sqlite
email-cluster review --next --project archivio_storico --db data/email_cluster.sqlite
```

La separazione tra professionale, personale, account, newsletter, ecommerce e notifiche avviene prima
dei contesti professionali.

### 4. Approva o correggi

```powershell
email-cluster approve-context --context 12 --db data/email_cluster.sqlite
email-cluster rename-context --context 12 --name "Tenax — registri rifiuti sede TPM" --db data/email_cluster.sqlite
```

Sono disponibili anche spostamento/esclusione email, split operativo e marcatura non professionale.
Ogni azione è tracciata e non modifica le run tecniche originali.

### 5. Esporta

```powershell
email-cluster export-final --project archivio_storico --db data/email_cluster.sqlite
```

## Interfaccia grafica

```powershell
email-cluster-gui
```

La scheda **Contesti** offre workbench, prossimo contesto, approvazione, rinomina, split, LLM ed export.
I dettagli di clustering sono nella scheda **Avanzato**.

## LLM locale

Il sistema funziona senza LLM e segnala quando nomi/spiegazioni sono euristici. Opzionalmente supporta
Ollama esclusivamente su localhost o llama.cpp con un GGUF locale. Non scarica modelli automaticamente.
Il LLM propone nome, sintesi ed email sospette; l'utente mantiene sempre il controllo.

## Documentazione

- [Workflow normale](docs/comandi.md)
- [Comandi avanzati](docs/avanzato.md)
- [Contesti operativi V3.1](docs/v3_1_rientro_semplicita_controllo_contesto.md)
- [Revisione umana e LLM](docs/revisione_umano_llm.md)
- [Architettura](docs/architettura.md)

Per diagnosticare l'ambiente:

```powershell
email-cluster doctor --input mail --db data/email_cluster.sqlite
```
