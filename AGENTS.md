# AGENTS

## Missione

Email Atlas e una pipeline locale, incrementale, rilanciabile e non interattiva per studiare archivi storici email personali e professionali, anche oltre 100.000 messaggi. Il risultato atteso sono dataset CSV leggibili, report HTML, un classification workspace revisionabile, un Atlante finale e test automatici affidabili.

## Priorita permanenti

- Se devi scegliere tra aggiungere funzionalita nuove e rendere affidabili i file gia prodotti, scegli rendere affidabili i file gia prodotti.
- Se devi scegliere tra GUI e pipeline CLI, scegli pipeline CLI.
- Se devi scegliere tra automazione totale opaca e revisione manuale assistita chiara, scegli revisione manuale assistita chiara.
- Se devi scegliere tra topic tecnicamente corretti ma incomprensibili e categorie candidate semplici ma revisionabili, scegli categorie candidate revisionabili.
- Preferisci CSV, report, test, checkpoint e comandi non interattivi rispetto a nuove superfici utente.

## Cosa non fare

- Non introdurre GUI complesse come asse principale del prodotto.
- Non introdurre cloud, servizi remoti o Gmail live.
- Non introdurre Virgilio o automazioni operative sulla posta reale.
- Non rendere obbligatori LLM, database esterni o server pesanti.
- Non disattivare foreign key.
- Non cancellare dati senza backup esplicito.
- Non lavorare sul profilo Thunderbird vivo: usa solo snapshot o copie locali MBOX/maildir.
- Non usare `danger-full-access` negli script ordinari.

## Regole dati, privacy e output

- Tutto resta locale al repository o a workspace locali espliciti.
- Nessun dato email deve uscire dal computer durante test, smoke o workflow autonomi.
- I report devono dichiarare fallback, limiti qualitativi e parti da revisionare.
- Gli output devono essere leggibili tramite file: CSV, HTML, JSON, YAML, markdown.
- Gli artifact di run automatici vanno in `.codex/runs/` e non devono diventare dati di prodotto.

## Regole branch e stato repository

- Lavora su branch dedicato, non direttamente su `main`.
- Non ripulire cambi non tuoi.
- Se il worktree contiene cambi estranei al task, evita di toccarli e limita le modifiche ai file necessari.
- Ogni ciclo deve lasciare il repository in stato coerente anche se non perfettamente pulito.

## Criteri per scegliere il prossimo task

1. Scegli il task aperto con priorita piu alta e dipendenze soddisfatte.
2. Preferisci il task che riduce rischio sistemico: affidabilita stage, invalidazione, test, report, quality gates.
3. Apri un solo fronte per ciclo.
4. Se un task e bloccato, registralo e passa al successivo solo se il blocco e reale e documentato.

### Regola anti-loop e chiusura dei task

Prima di modificare il codice, controlla nel run log gli ultimi esiti relativi al task selezionato.

Dopo tre run consecutivi con esito `partial-progress` sullo stesso task, il run successivo deve essere esclusivamente un run di chiusura. Non sono ammesse ulteriori ottimizzazioni incrementali o modifiche marginali.

Il run di chiusura deve produrre uno dei seguenti risultati:

1. verificare i criteri di accettazione, aggiornare il task a `done` e registrare le evidenze;
2. aggiornare il task a `blocked`, indicando una dipendenza concreta e verificabile;
3. trasferire le attività residue non indispensabili in uno o più nuovi task e chiudere il task corrente.

Un task deve essere chiuso quando i suoi criteri di accettazione sono soddisfatti, anche se sono ancora possibili ulteriori perfezionamenti.

Ogni run con esito `partial-progress` deve indicare:

* quale specifico criterio di accettazione è stato affrontato;
* quale prova o misurazione dimostra l’avanzamento;
* quali condizioni esatte restano necessarie per chiudere il task.

Non sono ammesse formule generiche come “resta aperto il fronte più ampio”, “sono possibili ulteriori ottimizzazioni” o equivalenti.

Le ottimizzazioni prestazionali devono essere giustificate da un benchmark, da una misurazione o da un problema riproducibile. Non modificare il codice soltanto perché è possibile ridurre ulteriormente una struttura dati o anticiparne il rilascio.

## Definizione di done

Un task e `done` solo se:

- il comportamento target e implementato;
- esistono test o smoke check pertinenti;
- i documenti/stato pertinenti sono aggiornati;
- backlog e run log riportano l'esito;
- non richiede spiegazioni implicite per essere usato nel ciclo successivo.

## Comandi di test e verifica

Usa, nell'ordine opportuno e se disponibili:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\email-atlas.exe --help
.\.venv\Scripts\email-atlas.exe smoke-test
```

## Completamento del ciclo

Ogni ciclo Codex deve:

1. leggere questo file, il backlog e lo stato corrente;
2. lavorare su un solo task;
3. aggiornare test o smoke check se il task cambia comportamento;
4. eseguire quality checks ragionevoli;
5. aggiornare `docs/development_backlog.md`;
6. aggiornare `.codex/state/backlog.json`;
7. aggiornare `.codex/state/run_log.md`;
8. aggiornare `.codex/state/blocked.md` se esiste un blocco reale;
9. documentare rischi, limiti e prossimo task suggerito.
