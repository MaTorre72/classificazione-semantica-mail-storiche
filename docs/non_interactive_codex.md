# Non Interactive Codex

## Obiettivo

Documentare come eseguire un singolo ciclo di sviluppo autonomo con Codex senza interazione continua.

## Modalita preferita

La modalita preferita del repository e una automazione cron nativa di Codex sul workspace locale, con prompt allineato a `.codex/prompts/automation_cycle.md`.

- niente scheduler esterno obbligatorio;
- niente dipendenze cloud aggiuntive;
- un solo task per ciclo;
- lock file locale per evitare sovrapposizioni.

## Comando previsto

Per il fallback locale scriptato, il flusso e progettato attorno a:

```text
codex exec --sandbox workspace-write --prompt-file .codex/prompts/next_task.md
```

Lo script `scripts/codex_next_task.*` seleziona un task, parte dal template `.codex/prompts/next_task.md` e genera poi il prompt effettivo in `.codex/runs/<timestamp>/effective_prompt.md`.

Per l'automazione cron nativa di Codex, invece, il prompt di riferimento del repository resta `.codex/prompts/automation_cycle.md`.

## Stato verifica CLI

Nel sandbox corrente il binario `codex.exe` risulta presente ma `codex --help` e `codex exec --help` non sono eseguibili per `Accesso negato` (verifica locale del 2026-06-30). Per questo:

- la sintassi sopra e trattata come target operativo del progetto;
- gli script permettono override tramite parametro `-CodexBin` o variabile `CODEX_BIN`;
- l'integrazione finale con la CLI reale va verificata fuori da questo sandbox.

Stato: manual integration required.

## Script disponibili

- `scripts/codex_guard.ps1` e `.sh`: controlli iniziali, lock, stato repository e cartelle richieste
- `scripts/codex_next_task.ps1` e `.sh`: selezione task, prompt operativo, invocazione Codex, logging e quality gates
- `scripts/run_quality_checks.ps1` e `.sh`: lint, test, smoke, secret check, large-file check, forbidden-surface check

## Variabili e parametri principali

- `CODEX_BIN`: path al binario Codex
- `-DryRun` / `--dry-run`: non esegue Codex
- `-LockMinutes` / `--lock-minutes`: soglia lock stale
- `-SkipQualityChecks` / `--skip-quality-checks`: solo per debugging locale
- `-Sandbox` / `--sandbox`: default `workspace-write`

## Output run

Ogni ciclo crea:

- `.codex/runs/<timestamp>/effective_prompt.md`
- `.codex/runs/<timestamp>/codex.stdout.log`
- `.codex/runs/<timestamp>/codex.stderr.log`
- `.codex/runs/<timestamp>/quality.log`
- `.codex/runs/<timestamp>/summary.json`

## Integrazione hook

Non e stata trovata o verificata una sintassi hook ufficiale all'interno del repository. Finche non viene confermata sulla CLI reale:

- usa gli script come equivalenti;
- non aggiungere configurazioni hook inventate;
- registra il risultato nel backlog `EA-EPIC0-HOOKS`.
