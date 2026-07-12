# Pipeline

1. Inventario read-only delle sorgenti.
2. Importazione incrementale e deduplica.
3. Parsing e pulizia versionata.
4. Ricostruzione verificabile delle Conversazioni.
5. Indice locale FTS5.
6. Entita e dizionari modificabili.
7. Documenti semantici conversation-first.
8. Rappresentazioni locali opzionali e cached.
9. Discovery di Categorie candidate.
10. Revisione umana, export ed evaluation.

Le fasi sono idempotenti dove possibile. Le tabelle legacy restano disponibili. Operazioni invasive
richiedono backup e consenso; i batch embedding supportano cache, batch e `--low-power`.

# Contratto delle fasi

Ogni fase legge i risultati della precedente e produce dati nel database o un report, senza modificare EML/MBOX. Inventario misura; parsing estrae e pulisce; conversazioni collega con header e fallback prudente; indice abilita la ricerca; entita e documenti semantici preparano evidenze; discovery propone categorie euristiche; revisione registra decisioni; export pubblica l'Atlante; evaluate segnala frammentazione. Gli embedding memorizzati non guidano oggi la discovery.

Un risultato tecnicamente riuscito non equivale a un risultato corretto: controlla warning, esempi di conversazioni lunghe, categorie fragili e rapporto categorie/conversazioni.

# Output di studio

La pipeline tecnica e orchestrata da `build-study-dataset`, ma non viene piu presentata come nove tappe utente. I checkpoint interni preparano conversazioni, indice, entita, documenti semantici e proposte; il contratto pubblico e il contenuto di `outputs/study_pack`.

Gli embedding sono opzionali. In loro assenza, TF-IDF + PCA produce coordinate esplorative con un warning esplicito. LLM e rete non sono prerequisiti.

## Cosa succede se rilancio la pipeline?

La modalita predefinita `safe` riusa conversazioni e dati gia presenti quando l'archivio e invariato. Se trova nuove email che richiederebbero una ricostruzione, si ferma e non cancella nulla.

Nel workspace di `email-atlas study`, `state.json` traccia stage completati, target richiesti e opzioni usate. `--stages` si ferma davvero allo stage richiesto; `--resume` salta uno stage solo se risulta completo e l'artefatto minimo atteso esiste ancora; `--rebuild-stage <stage>` invalida quello stage e tutti i successivi.

`--sample-size N` limita davvero l'import ai primi `N` messaggi dello snapshot. Se il valore cambia tra due run, lo stage `import_mbox` e i successivi vengono invalidati; il report finale aggiunge anche un warning esplicito per distinguere il campione rapido da uno studio completo.

`--limit-messages N` non cambia l'import nel database: limita invece il dettaglio esportato in `messages.csv`, `conversation_messages.csv` e `attachments.csv` del workspace rapido. Se il valore cambia tra due run, `build_conversations` e gli stage successivi vengono invalidati, cosi `--resume` riusa import/parsing ma rigenera export e report coerenti.

`--limit-conversations N` limita invece l'export dello study workspace alle prime `N` conversazioni ricostruite, riducendo CSV, topic e report senza reimportare i messaggi gia acquisiti. Se il valore cambia tra due run, `build_conversations` e gli stage successivi vengono invalidati, mentre parsing e import restano riusabili via `--resume`.

`--date-from YYYY-MM-DD` e `--date-to YYYY-MM-DD` selezionano le conversazioni che intersecano l'intervallo richiesto. `--source-folder NOME` e ripetibile e seleziona le conversazioni che contengono almeno un messaggio proveniente dalla cartella o dal file MBOX indicato. I filtri sono applicati prima degli export, persistiti in `state.json` e `workspace.json`; ogni variazione invalida `build_conversations` e gli stage successivi senza rifare import e parsing.

Gli allegati hanno due momenti distinti: `import_mbox` registra sempre i metadati, mentre `extract_attachment_text_optional` popola o svuota gli estratti in base a `--with-attachments-text` e `--no-attachments-text`. Cambiare `--max-attachment-mb` o l'opzione testo non richiede reimportare i messaggi invariati: invalida soltanto lo stage testo allegati e quelli successivi.

La pulizia testo storica usa ora il preprocessing `v2.1.0`: subject e current message filtrano stopword email ricorrenti (`subject`, `sent`, `data`, `your`, `come`) e pattern data come `03_2026` o `10/06/2024`. Questo rende piu leggibili `semantic_text`, conversazioni e label topic, e forza il ricalcolo dei `clean_texts` quando la versione cambia.

Lo studio workspace assegna anche `probable_scope`, `scope_confidence` e `scope_reason` per ogni conversazione, usando soli segnali locali da subject, testo e partecipanti. Il `classification_workspace.csv` riusa poi lo scope prevalente del topic come `proposed_scope`, cosi i topic non partono tutti da `Da definire`.

`--rebuild-derived` crea un backup SQLite, elimina in ordine soltanto dati ricostruibili e conserva decisioni umane e Atlante finale. `reset-project --confirm` e distruttivo: crea un backup e cancella l'intero progetto.

Un database vuoto e un progetto assente sono stati validi. Il read-model GUI restituisce conteggi zero senza interrogare tabelle derivate; soltanto le operazioni che richiedono uno studio gia esistente vengono bloccate con un errore `missing_project`. Il comando di costruzione puo creare nuovamente il progetto dallo stesso archivio.

## Pipeline snapshot MBOX

Il comando principale `email-atlas study` usa una copia offline delle cartelle Thunderbird. Le conversazioni sono l'unita tecnica; topic e categorie operative sono l'unita di revisione. BERTopic viene usato soltanto se disponibile e con dati locali; altrimenti il fallback deterministico e TF-IDF + SVD + KMeans. Gli allegati lunghi non vengono incorporati integralmente: semantic text usa nomi, keyword ed estratti limitati.

`study_report.html` deve restare autosufficiente anche senza GUI: dichiara stato allegati, metodo topic attivo, fallback disponibili, warning e link ai CSV principali da revisionare.
