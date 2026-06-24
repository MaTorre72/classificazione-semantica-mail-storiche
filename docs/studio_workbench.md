# Studio Workbench

Email Atlas e un laboratorio per analizzare una fotografia storica della posta, non un client quotidiano. Il risultato principale e un insieme di file portabili e verificabili.

## Percorso

1. **Prepara Studio** importa senza modificare i sorgenti, pulisce, ricostruisce conversazioni, estrae entita e genera i dataset.
2. **Esplora Risultati** permette di leggere distribuzioni, punti 2D, relazioni e conversazioni reali.
3. **Esporta per Orange** crea un pacchetto indipendente dalla GUI.
4. **Costruisci Atlante** trasforma decisioni esplicite nel file di lavoro in un Atlante finale.

Il comando `build-study-dataset` e riavviabile: import e tabelle usano chiavi/checkpoint esistenti. Prima di elaborare molti GB, esegui una prova su una copia rappresentativa e conserva il database.

## Cosa non fa

Non sposta email, non crea regole quotidiane, non integra Thunderbird o Virgilio, non richiede cloud e non usa un LLM per decidere la classificazione.

## Aggiornare o ricostruire

**Aggiorna studio** usa la modalità sicura: con file invariati riusa i dati. Se nuove email rendono necessaria una ricostruzione, si ferma per proteggere revisioni e Atlante finale.

**Ricostruisci dati derivati** crea prima un backup e rigenera conversazioni, documenti, embedding, entità e proposte. Le decisioni umane e l'Atlante finale restano nel database.

**Azzera progetto** richiede conferma esplicita, crea un backup e cancella tutto il progetto. Usalo soltanto per ricominciare davvero.
