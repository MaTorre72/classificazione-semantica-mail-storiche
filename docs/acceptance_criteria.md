# Acceptance Criteria

## Fase infrastruttura autonoma

La fase e accettata solo se:

1. esiste `AGENTS.md` con regole permanenti;
2. esiste backlog persistente sia human-readable sia JSON;
3. esiste workflow non interattivo documentato;
4. esistono script `codex_next_task` per Windows e Unix;
5. esistono script `codex_guard` per Windows e Unix;
6. esistono script `run_quality_checks` per Windows e Unix;
7. esiste `run_log.md` persistente;
8. esiste gestione dei blocchi in `.codex/state/blocked.md`;
9. esiste lock file `.codex/state/run.lock`;
10. esiste modalita dry-run;
11. gli script puntano a sandbox prudente;
12. l'integrazione hook non verificata e marcata `manual integration required`;
13. ogni ciclo e progettato per aggiornare backlog, run log e blocchi;
14. il sistema non dipende da GUI, cloud o dati reali;
15. la prossima priorita operativa e su stage, allegati e qualita topic.

## Test tecnici da guidare nel tempo

Il backlog deve condurre almeno a questi esiti:

1. prima analisi senza allegati, seconda con allegati: `attachment_text` viene eseguito;
2. il cambio opzione allegati invalida gli stage dipendenti;
3. allegati gia estratti non vengono riestratti inutilmente;
4. stopword email rimuovono token come `your`, `come`, `data`, `sent`, `subject`;
5. pattern come `03_2026` non entrano nelle label;
6. topic GitHub diventa `Account / notifiche tecniche`;
7. topic Google diventa `Account / notifiche tecniche`;
8. topic fattura diventa categoria amministrativa leggibile;
9. topic PEC/Hiro riceve etichetta leggibile;
10. `classification_workspace.csv` non e tutto `Da definire`;
11. i campi proposti non copiano sempre la raw label;
12. `study_report.html` mostra stato allegati;
13. `study_report.html` mostra metodo topic;
14. `study_report.html` dichiara fallback TF-IDF;
15. pipeline rilanciata due volte non perde opzioni allegati;
16. `--sample-size` produce output validi;
17. workspace grande evita caricamenti inutili in memoria;
18. nessun dato viene inviato fuori dal computer;
19. una run Codex non interattiva completa un task e aggiorna backlog;
20. la schedulazione ogni 50 minuti evita sovrapposizioni grazie al lock file.
