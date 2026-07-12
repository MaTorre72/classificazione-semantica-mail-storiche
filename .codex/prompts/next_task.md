# Email Atlas Autonomous Cycle

Leggi prima:

1. `AGENTS.md`
2. `docs/development_backlog.md`
3. `.codex/state/backlog.json`
4. `.codex/state/run_log.md`
5. `.codex/state/blocked.md`

Lavora in questo ciclo su un solo task:

- Task ID: `{{TASK_ID}}`
- Titolo: `{{TASK_TITLE}}`
- Area: `{{TASK_AREA}}`
- Priorita: `{{TASK_PRIORITY}}`
- Descrizione: `{{TASK_DESCRIPTION}}`
- Test richiesti: `{{TASK_TESTS}}`
- Accettazione: `{{TASK_ACCEPTANCE}}`

Regole del ciclo:

- prima di iniziare il task, leggi nel run log gli ultimi esiti relativi allo stesso task e applica la regola anti-loop definita in `AGENTS.md`;
- non aprire nuovi fronti;
- non introdurre GUI complessa;
- non introdurre cloud;
- non introdurre dipendenze obbligatorie da LLM;
- preferisci affidabilita pipeline, file prodotti, test e report;
- se tocchi comportamento, aggiorna test o smoke check;
- esegui quality checks ragionevoli;
- aggiorna `docs/development_backlog.md` e `.codex/state/backlog.json`;
- aggiorna `.codex/state/run_log.md`;
- se sei bloccato, aggiorna `.codex/state/blocked.md` con causa precisa e prossima mossa sicura;
- lascia il repository in stato coerente.

Riepilogo finale richiesto:

- task scelto
- file modificati
- test aggiunti
- test eseguiti
- esito
- prossimo task suggerito
- rischi
- blocchi
