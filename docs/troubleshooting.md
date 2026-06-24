# Risoluzione problemi

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
