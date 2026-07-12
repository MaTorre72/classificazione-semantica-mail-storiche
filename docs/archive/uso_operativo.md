# Uso operativo

Questa guida spiega come usare il progetto in modo pratico e sicuro con archivi email reali.

## 1. Client di posta e IMAP

### Stato attuale

Il progetto oggi lavora su file locali:

- `.mbox`;
- `.eml`;
- cartelle Thunderbird che contengono file MBOX.

Questa scelta e' intenzionale per la prima versione: evita di collegarsi direttamente a caselle reali, riduce il rischio operativo e rende ogni analisi ripetibile sullo stesso identico archivio.

### Flusso consigliato con client di posta

Per Thunderbird:

1. configura l'account nel client;
2. sincronizza le cartelle che vuoi analizzare;
3. chiudi Thunderbird prima dell'import;
4. copia i file MBOX in una cartella di lavoro;
5. lancia la pipeline sulla copia.

Esempio:

```powershell
.\.venv\Scripts\email-cluster.exe run-pipeline --source mail --project archivio_storico --db data\email_cluster.sqlite
```

Per Outlook o altri client:

1. esporta in `.eml` o converti in `.mbox`;
2. lavora sempre su una copia;
3. tieni separati export originali, database e report.

### IMAP diretto

L'integrazione IMAP non e' ancora implementata nel codice. Va aggiunta come modulo separato, non dentro il parser MBOX/EML.

Architettura consigliata:

```text
IMAP server
  -> connettore read-only
  -> download incrementale messaggi
  -> salvataggio locale EML/MBOX
  -> pipeline esistente
```

Regole per farlo bene:

- usare una password applicativa o OAuth, mai la password principale;
- aprire la casella in sola lettura;
- salvare `uid`, `folder`, `message_id` e data di download;
- non cancellare, spostare o marcare messaggi come letti;
- scaricare prima un campione piccolo;
- tenere il connettore IMAP disaccoppiato dalla classificazione.

Comandi futuri suggeriti:

```powershell
email-cluster imap-sync --account studio --folder INBOX --output data/input/imap/studio
email-cluster run-pipeline --source data/input/imap/studio --project studio
```

## 2. File di posta reali in produzione

Gli archivi email sono dati sensibili. La regola base e': il progetto lavora su copie locali, mai sull'originale operativo.

### Procedura sicura

1. crea una cartella di lavoro dedicata;
2. copia gli archivi nella sottocartella `mail/`;
3. rendi la cartella accessibile solo all'utente Windows corrente;
4. esegui import e cleaning;
5. controlla `email-cluster status`;
6. esporta solo cio' che serve;
7. non versionare mai mail, database o output.

Il repository gia' ignora:

- `.venv/`;
- `.tools/`;
- `mail/`;
- `data/*.sqlite`;
- `data/output/*`.

### Cosa non fare

- Non mettere MBOX o EML in Git.
- Non inviare database SQLite o report a terzi senza revisione.
- Non usare caselle IMAP reali in scrittura.
- Non cancellare gli originali dopo l'import: il database non e' un archivio legale sostitutivo.

### Controlli minimi prima di lavorare su produzione

```powershell
git status --short
.\.venv\Scripts\email-cluster.exe status --db data\email_cluster.sqlite
```

Il primo comando deve evitare dati sensibili tracciati da Git. Il secondo deve mostrare `errors = 0` o comunque un numero di errori spiegabile.

## 3. Archivi enormi

Per MBOX da qualche GB bisogna ragionare per lotti.

### Rischi

- parsing lento;
- database molto grande;
- embedding costoso;
- clustering UMAP/HDBSCAN pesante in RAM;
- report troppo estesi per essere letti.

### Strategia consigliata

1. importare una cartella o un MBOX alla volta;
2. usare progetti separati per anni, clienti o caselle;
3. generare embedding a batch con `--limit`;
4. clusterizzare sottoinsiemi coerenti;
5. salvare report per run;
6. passare a PostgreSQL/pgvector quando SQLite diventa stretto.

Esempio:

```powershell
.\.venv\Scripts\email-cluster.exe import --source mail\2023 --project archivio_2023
.\.venv\Scripts\email-cluster.exe clean --project archivio_2023
.\.venv\Scripts\email-cluster.exe embed --project archivio_2023 --limit 5000
```

Per archivi molto grandi, il comando unico `run-pipeline` e' comodo ma non sempre ideale: meglio controllare una fase alla volta.

### Evoluzioni tecniche necessarie

- progress bar per MBOX grandi;
- import incrementale con checkpoint;
- compattazione e indici SQLite dedicati;
- clustering per finestra temporale;
- storage vettoriale esterno per ricerca semantica;
- dashboard di campionamento invece di report enormi.

## 4. Revisione umana di etichette e cluster

Il clustering produce ipotesi. La classificazione diventa utile quando una persona rivede e corregge le etichette.

### Workflow attuale

1. genera i cluster;
2. esporta il file di revisione;
3. leggi parole chiave e email rappresentative;
4. assegna etichette manuali ai cluster buoni;
5. rigenera il report.

Comandi:

```powershell
.\.venv\Scripts\email-cluster.exe clusters --db data\email_cluster.sqlite
.\.venv\Scripts\email-cluster.exe review-clusters --db data\email_cluster.sqlite --output data\output\cluster_review.csv
.\.venv\Scripts\email-cluster.exe set-label 2 "Pratiche tecniche e allegati" --db data\email_cluster.sqlite
.\.venv\Scripts\email-cluster.exe report --db data\email_cluster.sqlite --output data\output\cluster_report.md
```

### Come leggere un cluster

Guarda in ordine:

1. dimensione;
2. keyword;
3. email rappresentative;
4. mittenti ricorrenti;
5. coerenza;
6. rumore.

Un cluster grande ma generico va diviso con parametri diversi o con un sottoinsieme temporale. Un cluster piccolo ma coerente puo' essere molto utile operativamente.

### Evoluzioni consigliate

- dashboard Streamlit locale;
- editor etichette manuali;
- campionamento casuale di email per cluster;
- flag `accetta`, `unisci`, `dividi`, `ignora`;
- dataset supervisionato costruito dalle etichette manuali.

