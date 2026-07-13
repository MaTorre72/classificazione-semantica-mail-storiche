# Verifica Fase 0

## Esito

La direzione conversation-first è compatibile con il repository, ma richiede un nuovo livello dati
additivo. Non sono state eseguite migrazioni o modifiche al database in questa fase.

## Evidenze controllate

- parser MIME, modelli, repository, schema SQLite e cleaning;
- CLI, configurazione, documentazione e suite test;
- conteggi read-only del database locale;
- presenza di header relazionali nei dati grezzi;
- assenza di tabelle Conversazione e FTS5;
- stato di cache, backup e supporto a elaborazioni lunghe.

## Verifica documentale

Il documento `docs/ripensamento_progetto_atlante_semantico.md` contiene tutti i dodici punti richiesti,
inventario verificato, strategia di compatibilità, rischi, gate e roadmap.

## Limiti noti

- non è stata misurata la qualità degli header sui 475 messaggi;
- gli account locali non sono ancora configurati, quindi ricevute/inviate non sono distinguibili;
- il numero reale di Conversazioni non è stimabile prima del backfill e del builder;
- checkpoint e resume sono ancora parziali;
- nessun indice full-text è presente.

## Fase successiva

Fase 1: comando `email-atlas inventory`, report HTML/JSON e test su fixture sintetiche, senza
classificazione e senza modificare le sorgenti.
