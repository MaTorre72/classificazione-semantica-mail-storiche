# Pipeline

1. Inventario read-only delle sorgenti.
2. Importazione incrementale e deduplica.
3. Parsing e pulizia versionata.
4. Ricostruzione verificabile delle Conversazioni.
5. Indice locale FTS5.
6. Entità e dizionari modificabili.
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

La pipeline tecnica è orchestrata da `build-study-dataset`, ma non viene più presentata come nove tappe utente. I checkpoint interni preparano conversazioni, indice, entità, documenti semantici e proposte; il contratto pubblico è il contenuto di `outputs/study_pack`.

Gli embedding sono opzionali. In loro assenza, TF-IDF + PCA produce coordinate esplorative con un warning esplicito. LLM e rete non sono prerequisiti.

## Cosa succede se rilancio la pipeline?

La modalità predefinita `safe` riusa conversazioni e dati già presenti quando l'archivio è invariato. Se trova nuove email che richiederebbero una ricostruzione, si ferma e non cancella nulla.

`--rebuild-derived` crea un backup SQLite, elimina in ordine soltanto dati ricostruibili e conserva decisioni umane e Atlante finale. `reset-project --confirm` è distruttivo: crea un backup e cancella l'intero progetto.

Un database vuoto e un progetto assente sono stati validi. Il read-model GUI restituisce conteggi zero senza interrogare tabelle derivate; soltanto le operazioni che richiedono uno studio già esistente vengono bloccate con un errore `missing_project`. Il comando di costruzione può creare nuovamente il progetto dallo stesso archivio.

## Pipeline snapshot MBOX

Il comando principale `email-atlas study` usa una copia offline delle cartelle Thunderbird. Le conversazioni sono l'unità tecnica; topic e categorie operative sono l'unità di revisione. BERTopic viene usato soltanto se disponibile e con dati locali; altrimenti il fallback deterministico è TF-IDF + SVD + KMeans. Gli allegati lunghi non vengono incorporati integralmente: semantic text usa nomi, keyword ed estratti limitati.
