# Autonomous Workflow

## Scopo

Questo workflow trasforma il repository in un sistema di sviluppo autonomo a cicli singoli, non infiniti e non interattivi. Ogni run:

1. prende il prossimo task dal backlog persistente;
2. genera un prompt operativo;
3. esegue Codex in sandbox prudente;
4. salva output e log;
5. esegue quality checks;
6. aggiorna stato e blocchi.

## File chiave

- `AGENTS.md`
- `docs/development_backlog.md`
- `docs/acceptance_criteria.md`
- `docs/non_interactive_codex.md`
- `.codex/prompts/*.md`
- `.codex/state/backlog.json`
- `.codex/state/run_log.md`
- `.codex/state/blocked.md`
- `.codex/state/decisions.md`
- `.codex/state/run.lock`

## Selezione del task

Lo script `scripts/codex_next_task.*` legge `.codex/state/backlog.json` e seleziona il primo task:

- non `done`
- non `blocked`
- con dipendenze soddisfatte
- con priorita piu alta

Un ciclo deve lavorare su un solo task.

## Lock file e sovrapposizioni

Il lock file e `.codex/state/run.lock`.

- Se il lock esiste ed e recente, la run esce senza fare nulla.
- Se il lock supera la soglia configurata, la run non parte e segnala una possibile esecuzione interrotta.
- Il lock viene rimosso alla fine del ciclo oppure in `finally` quando possibile.

## Dry-run

Usa il dry-run per validare selezione task e prompt senza avviare Codex:

```powershell
scripts/codex_next_task.ps1 -DryRun
```

```bash
scripts/codex_next_task.sh --dry-run
```

## Quality gates equivalenti agli hook

La sintassi hook nativa della CLI Codex non e verificata localmente in questo repository. Per questo il progetto usa script equivalenti:

- pre-run: `scripts/codex_guard.*`
- quality-gate: `scripts/run_quality_checks.*`
- secret-check: incluso in `scripts/run_quality_checks.*`
- output-check: incluso in `scripts/run_quality_checks.*`
- post-run: aggiornamento log e backlog nello script `scripts/codex_next_task.*`

Stato: manual integration required finche la CLI non viene verificata con `codex --help` e `codex exec --help`.

## Scheduling ogni 50 minuti

La modalita preferita del progetto e una automazione cron nativa di Codex, non uno scheduler esterno.

- Nome previsto: `Email Atlas sviluppo autonomo`
- Prompt sorgente: `.codex/prompts/automation_cycle.md`
- Cadenza: ogni 50 minuti, tutto il giorno, tutti i giorni
- Workspace: root del repository locale
- Esecuzione: locale, seriale, con lock file `.codex/state/run.lock`

La cron automation Codex deve:

1. aprire il repository locale come workspace della run;
2. leggere backlog e stato persistente dal repository;
3. fermarsi se un'altra run e gia in corso;
4. eseguire al massimo un task per ciclo;
5. aggiornare log e blocchi prima di chiudere.

Gli script `scripts/codex_guard.*`, `scripts/codex_next_task.*` e `scripts/run_quality_checks.*` restano nel repository come interfaccia locale verificabile, fallback manuale e documentazione eseguibile del comportamento atteso.

### Fallback opzionali

- Windows Task Scheduler e `cron` restano solo fallback manuali se l'automazione nativa Codex non fosse disponibile.
- La GitHub Action resta opzionale e non deve usare dati reali. Usa solo test, smoke sintetici e prompt di backlog.

## Politica di stop

Il ciclo si ferma se:

- il backlog non ha task candidati;
- esiste un lock recente;
- esiste un lock stale da analizzare;
- Codex fallisce;
- quality checks falliscono;
- emerge un blocco reale documentato.
