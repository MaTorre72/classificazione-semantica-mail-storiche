# Email Atlas Native Codex Automation

Leggi prima, in quest'ordine (Se il file `memory.md` non esiste, prosegui senza errore.):

1. `C:\Users\Marco\.codex\automations\email-atlas-sviluppo-autonomo\memory.md`
2. `AGENTS.md`
3. `docs/development_backlog.md`
4. `docs/acceptance_criteria.md`
5. `.codex/state/backlog.json`
6. `.codex/state/run_log.md`
7. `.codex/state/blocked.md`
8. `.codex/state/decisions.md`

Prima di iniziare il task, leggi nel run log gli ultimi esiti relativi allo stesso task e applica la regola anti-loop definita in `AGENTS.md`.

Se risultano almeno tre run consecutivi con esito `partial-progress`, questo ciclo è obbligatoriamente un run di chiusura:

* non cercare nuove micro-ottimizzazioni;
* confronta lo stato corrente con ciascun criterio di accettazione;
* esegui soltanto le verifiche o le modifiche strettamente necessarie alla chiusura;
* concludi il task come `done` o `blocked`, oppure trasferisci il lavoro residuo in un nuovo task separato.

In questo caso non terminare nuovamente con `partial-progress`.

Obiettivo del ciclo:

- eseguire un solo task del backlog;
- fermarti subito se esiste un blocco reale o se il backlog non offre task candidabili;
- lasciare il repository in stato coerente e tracciabile.

Guardrail operativi:

- lavora solo dentro questo workspace locale;
- non introdurre GUI complessa;
- non introdurre cloud o servizi remoti;
- non usare dati email reali fuori dal repository;
- non aprire piu di un fronte nello stesso ciclo;
- se trovi un lock file recente in `.codex/state/run.lock`, non avviare un nuovo ciclo;
- se trovi un lock stale, registra il blocco in `.codex/state/blocked.md` e fermati.

Procedura del ciclo:

1. Esegui `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex_guard.ps1`.
2. Se il guard fallisce per lock recente, esci senza modifiche.
3. Seleziona da `.codex/state/backlog.json` il primo task non `done`, non `blocked`, con dipendenze soddisfatte e priorita piu alta.
4. Lavora solo su quel task.
5. Se modifichi comportamento, aggiorna test o smoke check pertinenti.
6. 6. Esegui `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1` prima di chiudere il ciclo.
7. Aggiorna `docs/development_backlog.md`, `.codex/state/backlog.json`, `.codex/state/run_log.md` e `.codex/state/blocked.md` se serve.
8. Nel riepilogo finale indica task, file toccati, test eseguiti, esito, rischi e prossimo task suggerito.

Politica di stop:

- se il backlog e vuoto o tutti i task candidabili sono bloccati, fermati;
- se trovi errori bloccanti o dipendenze mancanti, documentali in modo conciso e fermati;
- se i quality checks falliscono, non passare a un secondo task.
