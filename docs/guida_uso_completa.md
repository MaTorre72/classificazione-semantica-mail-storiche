# Email Atlas - Guida completa all'uso

## 1. Che cosa fa il programma

Email Atlas studia una **copia offline** di un archivio email Thunderbird/MBOX. Ricostruisce conversazioni, individua soggetti e temi ricorrenti, censisce gli allegati e prepara una tabella di categorie candidate da revisionare.

Non sposta email, non modifica Thunderbird, non accede a Gmail e non invia dati in rete. Il risultato è una classificazione ragionata dell'archivio storico.

Il percorso normale è:

1. prepara una copia dei file MBOX;
2. esegui lo studio;
3. leggi `study_report.html`;
4. revisiona `classification_workspace.csv`;
5. genera l'Atlante finale;
6. facoltativamente esplora i dati con Orange.

## 2. Prima di iniziare

### Requisiti

- Windows 10/11;
- ambiente `.venv` già installato;
- spazio libero almeno pari alla dimensione dell'archivio più un margine;
- una copia separata dei dati Thunderbird.

Per verificare l'installazione:

```powershell
.\.venv\Scripts\email-atlas.exe --help
```

### Sicurezza: non usare il profilo attivo

1. Chiudi Thunderbird.
2. Individua il profilo da Thunderbird tramite **Aiuto > Informazioni per la risoluzione dei problemi > Cartella del profilo**.
3. Non indicare quella cartella direttamente a Email Atlas.
4. Copia in una nuova cartella soltanto le directory e i file MBOX che vuoi studiare.

Esempio:

```text
D:\EmailAtlas\snapshot_2026-06-29\
  Inbox
  Sent
  Archives.sbd\2022
  Archives.sbd\2023
  Mail\Local Folders\Clienti
  Inbox.msf              <- ignorato automaticamente
```

I MBOX Thunderbird spesso non hanno estensione. Email Atlas li riconosce dal contenuto. Sono accettati anche `.mbox`, `.mbx` ed `.eml`.

Assicurati di copiare **Sent/Posta inviata**: senza posta inviata la ricostruzione delle conversazioni è molto meno affidabile.

## 3. Metodo più semplice: menu Windows

Apri con doppio clic:

```text
EMAIL_ATLAS.bat
```

Il menu propone:

1. creare o aggiornare lo studio;
2. costruire l'Atlante finale;
3. generare il pacchetto Orange;
4. aprire la GUI minima;
5. aprire questa guida;
6. controllare l'integrita del workspace;
7. riparare in modo conservativo schema o progetto mancanti.

## Controllo e riparazione del workspace

Se lo studio segnala un database incoerente, non cancellare il database e non disattivare le
foreign key. Esegui:

```powershell
.\.venv\Scripts\email-atlas.exe doctor-workspace --workspace "workspace_studio_email"
```

Il doctor verifica progetto, `source_files`, vincoli SQLite e tabelle derivate. Se propone una
riparazione, usa:

```powershell
.\.venv\Scripts\email-atlas.exe repair-workspace --workspace "workspace_studio_email"
```

La riparazione crea prima un file `email_atlas.sqlite.backup-...`. Ricrea soltanto schema o
progetto mancanti: non elimina righe. Se esistono violazioni delle foreign key, si ferma e chiede
di usare un workspace nuovo o un backup integro.

Da Windows puoi usare direttamente `CONTROLLO_WORKSPACE.bat` e `RIPARA_WORKSPACE.bat`.

Puoi anche usare direttamente:

- `CREA_STUDIO.bat`;
- `COSTRUISCI_ATLANTE.bat`;
- `ESPORTA_ORANGE.bat`;
- `AVVIA_CONSOLE.bat`.
- `CONTROLLO_WORKSPACE.bat`;
- `RIPARA_WORKSPACE.bat`.

## 4. Primo studio da riga di comando

Apri PowerShell nella cartella del progetto ed esegui:

```powershell
.\.venv\Scripts\email-atlas.exe study `
  --input "D:\EmailAtlas\snapshot_2026-06-29" `
  --workspace "D:\EmailAtlas\studio_completo" `
  --with-attachments-text `
  --max-attachment-mb 20
```

### `--input`

Cartella contenente la **copia** MBOX. Può contenere sottocartelle `.sbd`, archivi, Inbox, Sent e cartelle locali.

### `--workspace`

Cartella di lavoro che Email Atlas può creare e aggiornare. Non deve coincidere con lo snapshot.

Una struttura consigliata:

```text
D:\EmailAtlas\
  snapshot_2026-06-29\   dati originali copiati
  studio_completo\       database, report e CSV prodotti
```

## 5. Opzioni del comando `study`

| Opzione | Quando usarla |
|---|---|
| `--resume` | Predefinita. Riusa workspace e file già importati. |
| `--no-resume` | Ricrea lo stato logico dello studio; non usare senza motivo. |
| `--rebuild-stage build_conversations` | Ricostruisce conversazioni e derivati creando prima un backup. |
| `--with-attachments-text` | Estrae localmente testo da formati supportati. |
| `--no-attachments-text` | Registra solo nome, tipo, dimensione e keyword degli allegati. |
| `--max-attachment-mb 20` | Non analizza allegati oltre la dimensione indicata. |
| `--embedding-provider none` | Usa il fallback testuale locale, rapido e senza modelli. |
| `--embedding-provider sentence-transformers` | Usa embedding locali se dipendenze e modello sono disponibili. |
| `--embedding-model NOME` | Seleziona il modello locale da usare. |
| `--sample-size N` | Registra la dimensione del campione desiderato per prove preparatorie. |
| `--stages list` | Mostra i nomi degli stage disponibili. |
| `--stages scan_input,import_mbox,...` | Registra gli stage richiesti nel checkpoint. |

Per il primo utilizzo consiglio:

```powershell
email-atlas study --input "D:\snapshot" --workspace "D:\studio" --with-attachments-text
```

Per archivi molto grandi, inizia senza testo allegati:

```powershell
email-atlas study --input "D:\snapshot" --workspace "D:\studio_prova" --no-attachments-text
```

## 6. Che cosa accade durante lo studio

Gli stage logici sono:

1. `scan_input`: trova MBOX/EML e ignora `.msf`;
2. `import_mbox`: importa i messaggi nel database locale;
3. `parse_messages`: normalizza testi e header;
4. `detect_sent_received`: riconosce account e cartelle inviate;
5. `build_conversations`: collega reply tramite Message-ID/References e fallback prudente;
6. `extract_attachments_metadata`: censisce allegati;
7. `extract_attachment_text_optional`: estrae testo supportato entro i limiti;
8. `build_semantic_text`: crea testo sintetico di conversazione;
9. `compute_embeddings_optional`: calcola embedding solo se richiesti;
10. `topic_discovery`: usa BERTopic se disponibile, altrimenti TF-IDF + SVD + KMeans;
11. `build_classification_workspace`: prepara categorie candidate;
12. `generate_report`: crea il report HTML autonomo.

## 7. File prodotti nel workspace

### File da aprire per primi

- `study_report.html`: quadro generale, warning e prossimi passi;
- `classification_workspace.csv`: tabella da revisionare;
- `conversations.csv`: una riga per conversazione;
- `topics.csv`: topic individuati;
- `attachments.csv`: censimento allegati.

### File tecnici

- `input_inventory.csv`: MBOX/EML analizzati;
- `messages.csv`: messaggi importati;
- `conversation_messages.csv`: collegamento messaggi-conversazioni;
- `conversations_enriched.csv`: conversazioni con topic e segnali;
- `attachment_texts.csv`: estratti, se abilitati;
- `clusters.csv`, `entities.csv`, `nodes.csv`, `edges.csv`;
- `workspace.json`: configurazione e manifest;
- `state.json`: checkpoint;
- `email_atlas.sqlite`: database locale;
- `logs/study.log`: log sintetico.

## 8. Come leggere `study_report.html`

Controlla nell'ordine:

1. **Ricevute e inviate**: se le inviate sono zero, verifica di avere copiato Sent/Posta inviata.
2. **Conversazioni miste**: mostrano che reply ricevute e inviate sono state collegate.
3. **Conversazioni totali**: troppe conversazioni singole indicano header mancanti o archivio incompleto.
4. **Allegati censiti/analizzati**: un allegato non analizzato resta comunque visibile come metadato.
5. **Topic principali**: sono proposte esplorative, non categorie definitive.
6. **Domini e soggetti**: aiutano a riconoscere clienti, enti, fornitori e rumore.
7. **Warning**: risolvili prima della revisione finale.

## 9. Revisionare `classification_workspace.csv`

Apri il file in Excel o LibreOffice. Non eliminare o rinominare le colonne.

Le colonne automatiche spiegano perché esiste la proposta:

- `proposed_name`, `proposed_scope`, `proposed_activity`;
- `conversation_count`;
- `representative_conversations`;
- `borderline_conversations`, `outlier_conversations`;
- `main_terms`, `main_domains`, `main_attachments`;
- `confidence`, `suggested_decision`.

Compila `human_decision` con uno di questi valori:

| Decisione | Significato | Campi da compilare |
|---|---|---|
| `approve` | La categoria va bene. | Facoltativamente i campi `final_*`. |
| `rename` | Categoria valida ma nome da cambiare. | `final_name` obbligatorio. |
| `merge` | Unire più righe nella stessa categoria. | Stesso `final_name` sulle righe da unire. |
| `exclude` | Rumore o categoria inutile. | Eventuale motivazione in `notes`. |
| `unclear` | Servono altre verifiche. | Spiega il dubbio in `notes`. |
| `split_later` | Categoria troppo ampia, da dividere dopo. | Descrivi la divisione in `notes`. |

Esempio:

```text
human_decision: rename
final_name: Autorizzazioni ambientali - integrazioni enti
final_scope: Professionale operativo
final_activity: Integrazioni documentali autorizzative
final_theme: AUA / AIA / enti di controllo
notes: Include ARPAV e richieste documentali degli enti
```

Non devi revisionare ogni conversazione: revisiona le categorie e usa gli ID rappresentativi per controllare esempi reali.

## 10. Costruire l'Atlante finale

Dopo aver salvato il CSV:

```powershell
.\.venv\Scripts\email-atlas.exe build-atlas --workspace "D:\EmailAtlas\studio_completo"
```

Output:

- `atlas_final.xlsx`;
- `atlas_final.yaml`;
- `atlas_final.json`;
- `atlas_final.html`.

Entrano nell'Atlante solo `approve`, `rename` e `merge`. `exclude`, `unclear` e `split_later` restano fuori dal risultato finale.

## 11. Orange opzionale

```powershell
.\.venv\Scripts\email-atlas.exe export-orange --workspace "D:\EmailAtlas\studio_completo"
```

Apri prima `orange/orange_readme.md` e `orange/orange_workflow_suggestions.md`. Troverai quattro percorsi:

1. mappa conversazioni;
2. topic testuali con Corpus/Topic Modelling;
3. Document Map;
4. rete con Network Explorer.

Orange non è necessario per costruire l'Atlante.

## 12. GUI minima

Avvia:

```text
AVVIA_CONSOLE.bat
```

Nella sezione **Studio snapshot Thunderbird / MBOX** inserisci:

- cartella snapshot;
- cartella workspace;
- scelta estrazione testo allegati;
- dimensione massima.

La GUI richiama gli stessi servizi della CLI. Per archivi molto grandi, la CLI o `CREA_STUDIO.bat` rendono più evidente il log e sono generalmente preferibili.

## 13. Rilanciare e aggiornare

Puoi rilanciare lo stesso comando sullo stesso workspace. I file invariati e le email duplicate vengono saltati.

Se hai aggiunto nuovi MBOX allo snapshot, rilancia normalmente. Se il sistema segnala che la ricostruzione delle conversazioni deve cambiare:

```powershell
email-atlas study --input "D:\snapshot" --workspace "D:\studio" --rebuild-stage build_conversations
```

Prima del rebuild viene creato un backup del database.

## 14. Problemi comuni

### Nessun MBOX trovato

- verifica di avere copiato file senza estensione come Inbox/Sent;
- non copiare soltanto `.msf`;
- controlla che i file MBOX non siano vuoti.

### Posta inviata assente

Copia Sent/Posta inviata e rilancia. Senza inviate il risultato è dichiarato fragile.

### Allegati non estratti

Controlla `extraction_status` in `attachments.csv`. Possibili valori: `extracted`, `metadata_only`, `too_large`, `unsupported`, `dependency_missing`, `error`.

### Workspace vuoto o incompleto

Esegui nuovamente `study`. Non eseguire `build-atlas` finché non esistono `workspace.json` e `classification_workspace.csv`.

### Il processo richiede molto tempo

Usa `--no-attachments-text` per la prima prova. Conserva la finestra aperta e controlla `logs/study.log`.

### Privacy

Tutta l'elaborazione è locale. Non condividere workspace, CSV o report senza averne valutato il contenuto: possono includere indirizzi, soggetti e brevi estratti delle email.
