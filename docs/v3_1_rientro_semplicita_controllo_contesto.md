# V3.1: rientro su semplicità, controllo e contesto

## Cosa non funziona nella V3

La V3 è tecnicamente completa ma presenta troppe entità e comandi in primo piano. Cluster, run,
probabilità, split matematici, tassonomia e suggerimenti chiedono all'utente di interpretare il
meccanismo invece di confermare il significato operativo. Un cluster può inoltre mescolare email
professionali e notifiche personali perché la somiglianza testuale non coincide con una pratica.

## Rientro di prodotto

Il risultato principale diventa `operational_context`: una pratica, un adempimento, un tema tecnico,
una documentazione o una conversazione. Il cluster resta una sorgente tecnica. Prima di creare contesti
professionali, ogni email riceve una macro categoria; categorie incompatibili non vengono mescolate.

## Comandi principali

- `run`: aggiorna l'archivio e la pipeline tecnica.
- `workbench`: mostra stato, crea/aggiorna contesti e indica una sola prossima azione.
- `review`: apre il prossimo contesto oppure quello richiesto.
- `export-final`: esporta report e dataset per contesti.
- `doctor`: controlla l'ambiente locale.

Tutti gli altri comandi restano compatibili ma sono documentati in `docs/avanzato.md`.

## Workflow guidato

1. Stato archivio e macro categorie.
2. Costruzione dei contesti da email compatibili, cluster, subject, sender, thread e allegati.
3. Revisione del contesto più prioritario.
4. Approvazione, rinomina, spostamento/esclusione o split motivato.
5. Esportazione della classificazione finale.

Il workbench mostra sempre una sola azione consigliata.

## Modello di classificazione

Le macro categorie sono: professionale operativo, professionale amministrativo, personale,
automatico/account, newsletter/eventi, ecommerce/spedizioni, notifiche tecniche e rumore. Solo le
prime due alimentano contesti professionali automaticamente. Le altre formano contesti separati.

`operational_contexts` conserva nome, tipo, cliente/ente, dominio, pratica/tema, sintesi, motivazione,
azione consigliata, sorgente, confidenza e stato. `email_context_assignments` conserva assegnazione,
macro categoria, motivo e revisione. `context_review_events` traccia ogni correzione senza distruggere
lo storico.

## Ruolo del LLM

Il LLM locale, se abilitato, riceve solo schede sintetiche e propone nome, spiegazione, email fuori
contesto e azione. Non assegna né approva. Senza LLM vengono usate euristiche e viene mostrato un
avviso di qualità limitata; nessun modello viene scaricato.

## GUI

La schermata principale diventa una console contesti: lista prioritaria, riepilogo operativo,
email incluse/sospette e pochi comandi (approva, rinomina, split, sposta, escludi, non professionale,
LLM, esporta). Metriche UMAP/HDBSCAN restano nei dettagli avanzati.

## Schema e migrazione

Migrazione additiva a schema 4 con backup automatico. Run, review V3, embedding e contesti semantici
restano intatti. I contesti operativi possono essere ricostruiti senza rigenerare ML.

## Criteri di accettazione

Un solo workflow consigliato; separazione macro visibile; nessun contesto professionale contaminato
senza warning; revisione in poche azioni; split con nomi e motivi; report leggibile; funzionamento senza
LLM; vecchi comandi disponibili ma non dominanti.
