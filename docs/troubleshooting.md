# Risoluzione problemi

## Errore `UNIQUE constraint failed` sulle conversazioni

L'errore su `atlas_conversations.project_id, atlas_conversations.stable_key` poteva verificarsi
con archivi grandi contenenti messaggi senza `Message-ID` o con `Message-ID` riutilizzati. Due
conversazioni diverse finivano per condividere la stessa chiave tecnica. La chiave ora include
anche il `message_hash` locale e stabile dei messaggi.

Non cancellare il workspace: l'inserimento delle conversazioni avviene in transazione e può
essere rilanciato dopo l'aggiornamento. Ripeti lo stesso studio sul medesimo workspace e sulla
stessa copia storica dell'archivio, purché non sia un profilo attualmente usato da Thunderbird.

## Email importate ma dichiarate `non collegate`

Accade quando nuove cartelle o nuovi messaggi vengono aggiunti a un workspace che possiede già
conversazioni e risultati derivati. È una protezione, non una perdita di dati. Rilancia
`CREA_STUDIO.bat` con gli stessi percorsi e rispondi `s` a **Ricostruire conversazioni con
backup?**. Da PowerShell usa `--rebuild-stage build_conversations`.

Su archivi grandi l'estrazione del testo allegati può richiedere più sessioni. Le riprese saltano
i file sorgente che non contengono più allegati `metadata_only`, quindi non ricominciano da zero.
Stati come `unsupported`, `dependency_missing` e `too_large` sono esiti finali dichiarati, non
errori da rilanciare all'infinito.

## La cartella non e valida

Usa un percorso assoluto esistente e leggibile. Non spostare l'archivio durante l'elaborazione.

## Il parsing segnala errori

Controlla formato e permessi dei file. Gli errori restano nel report; conserva i sorgenti e prova prima su un campione.

## Le conversazioni sono troppo grandi

Apri il report conversazioni e controlla i gruppi creati con fallback. Subject generici e corti sono esclusi, ma omonimie residue sono possibili.

## La ricerca non restituisce risultati

Esegui prima **Indicizzazione**. Prova termini meno specifici e verifica che il parsing abbia prodotto testo.

## Le categorie sono frammentate

La discovery e euristica. Usa **Revisione** per approvare, rinominare, segnare ambigue o escludere; valuta le categorie suggerite da accorpare.

## Ripristino

I file email non vengono modificati. Prima di interventi sul database, chiudi la GUI e copia `data/email_cluster.sqlite`; per ricominciare usa un nuovo database invece di cancellare l'archivio.

## Foreign key durante la ricostruzione

Non disattivare le foreign key. Rilancia prima **Aggiorna studio**. Se il sistema segnala email nuove o derivati incompatibili, usa **Ricostruisci dati derivati**: viene creato automaticamente un file `.backup-...` accanto al database. **Azzera progetto** cancella anche revisioni e Atlante finale e richiede conferma.

## Errore: Project not found: archivio_storico

Significa che il database esiste ma non contiene il progetto configurato. Accade con un database nuovo oppure dopo **Azzera progetto**. Non è un guasto: la home mostra **Nessuno studio attivo**.

- Usa **Crea nuovo studio** o **Importa archivio** per ripartire.
- Usa **Seleziona database** se hai aperto il file SQLite sbagliato.
- **Azzera dati derivati** conserva sempre il progetto e serve per rigenerare conversazioni e analisi.
- **Azzera progetto** elimina invece lo studio completo dopo backup e conferma.
