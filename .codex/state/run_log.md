# Run Log

## 2026-07-12 - launcher Windows verificati e residui storici archiviati

- Task: `EA-CLEANUP-LAUNCHERS-AND-LEGACY`
- Esito: completed
- Modifiche: mantenuti sette `.bat` correnti alla radice; aggiunto `EMAIL_ATLAS_NO_OPEN` per smoke non interattivi; aggiunti controlli ambiente mancanti; archiviati il launcher Tkinter `start_gui.bat` e due report progettuali storici; aggiunto `wsp_*/` a `.gitignore` senza cancellare il workspace locale dell'utente.
- Verifiche eseguite: menu exit; studio completo su 6 fixture EML; doctor integro; export Orange; build-atlas; annullamento prudente repair; `email-cluster ui --help`; test automatici dei launcher; scansione riferimenti e import dei moduli legacy.
- Evidenze: study completato con 12/12 stage, 5 conversazioni e 2 topic; doctor con foreign key attive e nessuna violazione; Orange con otto file; Atlante con cinque formati.
- Rischi/limiti: la console web non è stata lasciata in esecuzione durante il test; il suo comando e le opzioni sono stati verificati dall'help. I moduli storicamente denominati v2/v3/ui restano attivi perché sono importati e coperti da regressioni.
- Prossimo task suggerito: nessun task candidabile noto.

## 2026-07-12 - documentazione operativa e launcher riordinati

- Task: `EA-DOCS-OPERATOR-MANUAL`
- Esito: completed
- Modifiche: aggiunto `docs/README.md`; README, guida rapida e comandi indicano `EMAIL_ATLAS.bat` come punto di ingresso consigliato; 21 vecchie versioni e guide superate sono state conservate in `docs/archive/` con un proprio indice.
- Verifiche eseguite: lettura dei launcher `.bat`; `email-atlas --help`; help di `doctor-workspace`, `build-atlas` ed `export-orange`; controllo diff, link e backlog JSON.
- Rischi/limiti: i documenti storici e avanzati restano nel repository per tracciabilita ma non sono necessari al percorso normale.
- Prossimo task suggerito: nessun task candidabile noto.

## 2026-07-12 - optional Orange export verified and closed

- Task: `EA-EPIC9-ORANGE`
- Esito: completed
- Modifiche: nessuna modifica funzionale necessaria; riconciliati backlog e stato dopo aver verificato che `export_orange_workspace`, il comando `email-atlas export-orange --workspace`, `docs/orange_export.md` e i test dedicati soddisfano gia il criterio di accettazione senza rendere Orange una dipendenza obbligatoria.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' -m pytest tests\test_study_workbench.py tests\test_thunderbird_workspace.py -q -k 'orange'`, `& '.\.venv\Scripts\email-atlas.exe' export-orange --help`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`.
- Rischi/limiti: Orange e i suoi add-on restano strumenti esterni facoltativi; la pipeline produce soltanto CSV e istruzioni locali e non verifica l'apertura nell'applicazione Orange.
- Prossimo task suggerito: nessun task candidabile noto.

## 2026-07-12 - study filters by date and source folder

- Task: `EA-EPIC8-FILTERS`
- Esito: completed
- Modifiche: `email-atlas study` espone `--date-from`, `--date-to` e `--source-folder` ripetibile; la selezione delle conversazioni applica i filtri prima degli export, persiste le opzioni in `state.json` e `workspace.json` e invalida `build_conversations` quando cambiano.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k 'date_and_source_folder_filters'`, `& '.\.venv\Scripts\email-atlas.exe' study --help`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Rischi/limiti: il filtro cartella seleziona una conversazione se almeno un suo messaggio proviene dalla sorgente richiesta; gli altri messaggi della stessa conversazione restano inclusi per non spezzare il thread.
- Prossimo task suggerito: `EA-EPIC9-ORANGE`

## 2026-07-12 - scalability epic closed with 10k-message benchmark

- Task: `EA-EPIC8-SCALE`
- Esito: completed
- Modifiche: aggiunto `scripts/scalability_benchmark.py`, eseguito il benchmark locale su 10.000 email sintetiche e registrati i risultati in `docs/scalability_benchmark.md`; i filtri data/cartella residui sono stati trasferiti nel task non bloccante `EA-EPIC8-FILTERS`.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' scripts\scalability_benchmark.py --messages 10000 --run-dir .codex\runs\scale-20260712`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Evidenze: 10.000 messaggi e 5.000 conversazioni esportati, 12/12 stage completati in 326,061 s, picco memoria Python 21,722 MiB, workspace 40,615 MiB; limiti rapidi coperti dai test automatici.
- Rischi/limiti: `tracemalloc` misura le allocazioni Python e non il resident set complessivo; filtri data/cartella rimandati esplicitamente a `EA-EPIC8-FILTERS`.
- Prossimo task suggerito: `EA-EPIC8-FILTERS`

## 2026-07-12 - conversation and classification exports now stream directly

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) scrive `conversations.csv`, `conversations_enriched.csv` e `classification_workspace.csv` in streaming invece di trattenere i buffer `enriched`/`classification`; i contenuti e le colonne restano invariati.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or sample_size_limits_imported_messages_but_keeps_valid_workspace_outputs or limit_conversations_trims_workspace_outputs_and_invalidates_resume or limit_messages_trims_workspace_message_exports_and_invalidates_resume or scope_classification_populates_scope_confidence_and_reason'`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirati verdi (`5 passed`, `12 deselected`); quality checks completi verdi (`124 passed`), con i warning non bloccanti noti su Starlette/httpx, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-12 - selected conversation ids now reuse the ordered conversation query

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) costruisce `selected_conversation_ids` direttamente dall'ordine gia restituito da `_conversation_rows()`, evitando il `sorted(...)` intermedio e una lista temporanea in piu senza cambiare gli export.
- Verifiche eseguite: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or limit_conversations_trims_workspace_outputs_and_invalidates_resume or sample_size_limits_imported_messages_but_keeps_valid_workspace_outputs'"`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirati verdi (`3 passed`, `14 deselected`); quality checks completi verdi (`124 passed`), con i warning non bloccanti noti su Starlette/httpx, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 15 minuti.

## 2026-07-12 - selected message ids are now skipped on the common full-export path

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) costruisce `selected_message_ids` solo quando `limit_messages` e impostato e libera `selected_conversation_ids` subito dopo l'export allegati; il ramo allegati mantiene l'output invariato nel caso standard senza il filtro ridondante sui `message_id`.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' -m py_compile .\src\email_cluster\atlas\workspace_study.py`, `& '.\.venv\Scripts\python.exe' -m pytest .\tests\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or sample_size_limits_imported_messages_but_keeps_valid_workspace_outputs or limit_conversations_trims_workspace_outputs_and_invalidates_resume or limit_messages_trims_workspace_message_exports_and_invalidates_resume or attachment_text_stage_can_resume_without_reimporting_messages'`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirati verdi (`5 passed`, `12 deselected`); quality checks completi verdi (`124 passed`), con i warning non bloccanti noti su Starlette/httpx, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 35 minuti.

## 2026-07-12 - attachment texts now stream directly from the attachment scan

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) ora scrive `attachment_texts.csv` in streaming mentre scorre gli allegati, mantiene `attachment_contexts_by_conversation` come stringhe bounded invece di liste di tuple e rimuove il buffer `attachment_text_rows`.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or attachment_text_stage_can_resume_without_reimporting_messages or limit_messages_trims_workspace_message_exports_and_invalidates_resume'`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirati verdi (`3 passed`, `14 deselected`); quality checks completi verdi (`124 passed`), con i warning non bloccanti noti su Starlette/httpx, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 15 minuti.

## 2026-07-12 - selected message exports now use compact ID buffers

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) usa ora `array('I')` per `selected_conversation_ids` e `selected_message_ids` invece di `set`/`list`; [`tests/test_thunderbird_workspace.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_thunderbird_workspace.py) aggiunge una regressione che confronta i `message_id` di `messages.csv` e `conversation_messages.csv`.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or attachment_text_stage_can_resume_without_reimporting_messages'`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirato verde (`2 passed`, `15 deselected`); quality checks completi verdi (`124 passed`), con i warning non bloccanti noti su Starlette/httpx, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-12 - message exports now stream in one pass

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) ora scrive `messages.csv` e `conversation_messages.csv` nello stesso passaggio streaming, accumulando gli ID messaggio on the fly per il filtro allegati invece di materializzare `message_rows`.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k 'limit_messages_trims_workspace_message_exports_and_invalidates_resume or attachment_text_stage_can_resume_without_reimporting_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace'`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirato verde (`3 passed`, `14 deselected`); quality checks completi verdi (`124 passed`), con i warning non bloccanti noti su Starlette/httpx, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 1 ora.

## 2026-07-12 - entities export now streams directly from the cursor

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) ora streama `entities.csv` direttamente dal cursor DB invece di materializzare `entity_rows`; [`tests/test_thunderbird_workspace.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_thunderbird_workspace.py) aggiunge una regressione che verifica il dominio `example.it` nel CSV entity del fixture.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirato verde (`17 passed`); quality checks completi verdi (`124 passed`), con i warning non bloccanti noti su Starlette/httpx, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 25 minuti.

## 2026-07-12 - semantic points now stream cached embeddings directly

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) ora consuma il cursor di `atlas_embedding_cache` direttamente in `_semantic_points()` invece di materializzare prima una lista intermedia; [`tests/test_study_workbench.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_study_workbench.py) aggiunge una regressione con cache embedding minima che copre il path `embeddings_pca`.
- Verifiche eseguite: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_study_workbench.py -q -k 'semantic_points_stream_cached_embeddings_without_extra_list or semantic_map_network_and_report_are_explorable or study_pack_produces_documented_standard_csvs'"`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirati verdi (`3 passed`, `5 deselected`); quality checks completi verdi (`124 passed`), con i warning non bloccanti noti su Starlette/httpx, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 10 minuti.

## 2026-07-12 - selected conversation texts now stream in order

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) ora streama `_conversation_selected_texts()` in batch ordinati con una CTE `requested` invece di materializzare un dizionario per conversazione; la logica di dedup resta in streaming e [`tests/test_atlas_reset.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_atlas_reset.py) blocca anche l'ordine del `unique_clean_text` per il caso a due messaggi senza header.
- Verifiche eseguite: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_atlas_reset.py -q"`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirati verdi (`13 passed`); quality checks completi verdi (`123 passed`), con i warning non bloccanti noti su Starlette/httpx, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 40 minuti.

## 2026-07-11 - conversation selected text loader reuses compact arrays

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) ora passa l'array compatto `conversation_email_ids` direttamente a `_conversation_selected_texts` invece di copiarlo in una lista, e [`tests/test_atlas_reset.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_atlas_reset.py) verifica che il loader riceva proprio `array('I')`.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ''codex-email-atlas''; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & ''.\.venv\Scripts\python.exe'' -m pytest tests\test_atlas_reset.py -q -k ''build_conversations_passes_compact_email_arrays_to_text_loader or build_conversations_rebuilds_with_sparse_email_ids or build_conversations_fallback_links_without_buffering_all_subject_rows or build_conversations_uses_body_text_when_clean_text_is_missing'''`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirati verdi (`4 passed`, `9 deselected`); quality checks completi verdi (`123 passed`), con gli stessi warning non bloccanti noti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-11 - partial classification workspace return releases topics buffer

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) libera `topics` prima di `finalize_partial()` quando il run si ferma a `build_classification_workspace`, cosi il ramo parziale non tiene vivo l'intero buffer topic durante la return.
- Verifiche eseguite: `powershell -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path (Get-Location) '.tmp'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_thunderbird_workspace.py -q -k 'rebuild_stage_invalidates_downstream_without_opening_second_front or study_report_declares_attachment_state_topic_method_and_fallback or sample_size_limits_imported_messages_but_keeps_valid_workspace_outputs'"`, `powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1`
- Note: test mirati verdi (`3 passed`, `14 deselected`); quality checks completi verdi (`122 passed`), con i warning non bloccanti noti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-11 - conversation aggregation split into separate CTEs

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) ora pre-aggrega `entity_names` e `attachment_names` in CTE separate dentro `_conversation_rows()`, cosi evita il join moltiplicativo tra messaggi, entita e allegati senza cambiare gli output; aggiunta una regressione che copre una conversazione con piu entity e attachment rows.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_study_workbench.py tests\\test_thunderbird_workspace.py -q -k 'conversation_rows_keep_entities_and_attachments_aggregated or study_pipeline_builds_mixed_conversations_attachments_and_workspace or pipeline_rerun_empty_workspace_atlas_and_orange'"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1`
- Note: test mirati verdi (`3 passed`, `21 deselected`); quality checks completi verdi (`122 passed`), con i warning non bloccanti noti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 40 minuti.

## 2026-07-11 - study export rows streamed directly from cursors

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) ora streama `conversation_messages.csv`, `entities.csv` e `attachments.csv` direttamente dai cursori del DB durante `export_study_pack`, evitando tre copie materializzate intermedie senza cambiare output o contratto.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_study_workbench.py tests\\test_atlas_reset.py -q"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1`
- Note: test mirati verdi (`18 passed`); quality checks completi verdi (`121 passed`), con i warning non bloccanti noti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 30 minuti.

## 2026-07-11 - topic ids kept alongside conversation rows

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) ora usa una sequenza di `topic_id` allineata a `rows` invece del dizionario `assignments` per collegare i topic alle conversazioni durante l'enriched workspace; l'output resta invariato.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or study_report_declares_attachment_state_topic_method_and_fallback or pipeline_rerun_empty_workspace_atlas_and_orange'"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1`
- Note: test mirati verdi (`3 passed`, `14 deselected`); quality checks completi verdi (`121 passed`), con i warning non bloccanti noti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 15 minuti.

## 2026-07-11 - study report now uses summary counters earlier

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) ora calcola i conteggi del report da uno snapshot minimo, libera `conversation_export` prima delle fasi finali e passa al report solo i totali necessari; l'output resta invariato.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_study_workbench.py tests\\test_thunderbird_workspace.py -q -k 'build_study_dataset_runs_the_complete_local_pipeline or study_pack_produces_documented_standard_csvs or study_report_declares_attachment_state_topic_method_and_fallback'"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1`
- Note: test mirati verdi (`3 passed`, `20 deselected`); quality checks completi verdi (`121 passed`), con i warning non bloccanti noti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 15 minuti.

## 2026-07-11 - attachment export streamed from cursor

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) ora streama `attachments.csv` dal cursor DB invece di materializzare tutta la lista, aggiorna contatori e context in volo e conserva solo i record minimi per `attachment_texts.csv` quando richiesto; l'output resta invariato.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or attachment_text_stage_can_resume_without_reimporting_messages or pipeline_rerun_empty_workspace_atlas_and_orange'"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: test mirati verdi (`3 passed`, `14 deselected`); quality checks completi verdi (`121 passed`), con i warning non bloccanti noti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 35 minuti.

## 2026-07-11 - term extraction released before classification workspace

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) calcola `_terms(rows)` subito dopo gli export di topic ed entita, poi rilascia `semantic_text` e `analysis_text` prima di `classification_workspace.csv` e del report finale; l'output resta invariato.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or study_report_declares_attachment_state_topic_method_and_fallback or sample_size or limit_conversations or limit_messages or pipeline_rerun_empty_workspace_atlas_and_orange'"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1`
- Note: test mirati verdi (`6 passed`, `11 deselected`); quality checks completi verdi (`121 passed`), con i warning non bloccanti noti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-11 - conversations buffer lazily allocates single-item lists

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) ora alloca in modo lazy `message_ids` e il testo unico per le conversazioni monomessaggio, poi rilascia i buffer temporanei prima del round-trip SQL; il contratto esterno resta invariato.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path (Get-Location) '.tmp'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\.venv\Scripts\python.exe' -m pytest tests\test_atlas_conversations.py tests\test_atlas_reset.py -q"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ''codex-email-atlas''; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & ''.\scripts\run_quality_checks.ps1'''`
- Note: test mirati verdi (`15 passed`); quality checks completi verdi (`121 passed`), con i warning non bloccanti noti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-11 - EA-EPIC8-SCALE validation pass after memory trims

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: nessun nuovo cambio di codice in questo ciclo; ho verificato il worktree gia modificato per la scalabilita, confermato che le riduzioni di memoria in `workspace_study.py` e `conversations.py` restano coerenti, e lasciato il task aperto sul fronte memoria/streaming residuo.
- Verifiche eseguite: `powershell -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\scripts\run_quality_checks.ps1'"`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 30 minuti.

## 2026-07-11 - message exports released before attachment loading

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) scrive `messages.csv` e `conversation_messages.csv` subito dopo la query dei messaggi, poi libera `message_rows` prima di caricare allegati e topic, cosi il buffer piu grande non resta residente durante il resto del workspace; l'output resta invariato.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ''codex-email-atlas''; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & ''.\\.venv\\Scripts\\python.exe'' -m pytest tests\\test_thunderbird_workspace.py -q; & ''.\\scripts\\run_quality_checks.ps1'''`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 25 minuti.

## 2026-07-11 - workspace study pops per-conversation maps during enrichment

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) svuota `assignments` e `attachment_contexts_by_conversation` mentre costruisce `enriched`, cosi le mappe per conversazione e gli snippet allegati vengono rilasciati subito dopo l'uso; l'output resta invariato.
- Verifiche eseguite: `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ''codex-email-atlas''; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & .\\.venv\\Scripts\\python.exe -m pytest tests\\test_thunderbird_workspace.py -q'`, `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ''codex-email-atlas''; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & .\\scripts\\run_quality_checks.ps1'`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 15 minuti.

## 2026-07-11 - attachment exports moved before topic discovery

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) esporta `attachments.csv` e `attachment_texts.csv` subito dopo la query degli allegati, libera `attachment_rows` prima di `topic_discovery` e usa una cache minimale di snippet per conversazione fino alla costruzione di `enriched`; l'output resta invariato.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or attachment_text_stage_can_resume_without_reimporting_messages or study_report_declares_attachment_state_topic_method_and_fallback or limit_conversations or limit_messages or pipeline_rerun_empty_workspace_atlas_and_orange'"`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 45 minuti.

## 2026-07-11 - attachment report summary released before workspace HTML

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) calcola `attachment_count`, `attachment_analyzed` e `attachment_status` prima del report, libera `attachment_rows` subito dopo gli export allegati e passa al renderer HTML solo i contatori necessari; l'output resta invariato.
- Verifiche eseguite: `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_thunderbird_workspace.py -q"`, `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1"`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 25 minuti.

## 2026-07-11 - study pack prunes long-lived export buffers

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) condensa `conversation_export`, `points`, `terms` e `candidates` in snapshot minimi dopo gli export CSV, libera `message_rows`, `entities`, `subject_rows`, `similarity_edges`, `nodes` ed `edges` appena finiscono il loro ultimo uso e scrive `classification_workspace.csv` prima della riduzione dei candidati; `_write_study_report()` usa solo i conteggi necessari per la sezione rete.
- Verifiche eseguite: `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_study_workbench.py tests\\test_thunderbird_workspace.py -q"`, `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); restano i warning non bloccanti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 35 minuti.

## 2026-07-11 - study conversation rows now select fewer columns

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) restringe `_conversation_rows()` ai soli campi davvero usati downstream, porta in SQL il fallback `semantic_text <- analysis_text` e rimuove colonne SQL copiate solo per essere scartate; il primo giro di test ha mostrato che `status` serve ancora all'export, quindi il campo resta nel select finale.
- Verifiche eseguite: `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_study_workbench.py tests\\test_thunderbird_workspace.py -q"`, `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1"`
- Note: quality checks completi verdi (`121 passed`); il fronte piu ampio di scalabilita resta aperto.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-11 - workspace study releases report rows earlier

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) precompila i contatori del report mentre costruisce `enriched`, libera la lista subito dopo i CSV delle conversazioni e passa a `study_report.html` uno snapshot di conteggi gia pronto, cosi il tratto finale non trattiene piu il payload di report durante allegati/topic/classification.
- Verifiche eseguite: `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\\.venv\\Scripts\\python.exe' -m pytest tests\\test_thunderbird_workspace.py -q"`, `C:\\WINDOWS\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); restano i warning non bloccanti su Starlette/httpx, core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 15 minuti.

## 2026-07-11 - workspace study trims resident report payload

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) riduce `enriched`, `attachment_rows` e `topics` ai soli campi ancora richiesti dopo gli export intermedi, cosi il report finale conserva gli stessi output con meno payload residente.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; & '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tempRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-email-atlas'; New-Item -ItemType Directory -Force $tempRoot | Out-Null; $env:TEMP = $tempRoot; $env:TMP = $tempRoot; $env:TMPDIR = $tempRoot; powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1"`
- Note: quality checks completi verdi (`121 passed`); resta aperto il fronte piu ampio di scalabilita su lettura incrementale e streaming.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-11 - study pack releases raw conversation rows earlier

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) costruisce `subjects.csv` e il report finale da `conversation_export` gia condensato, libera `rows` subito dopo la derivazione e mantiene il report su una vista piu piccola senza cambiare i file prodotti.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_study_workbench.py tests\test_atlas_reset.py -q"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); resta aperto il fronte piu ampio di scalabilita su lettura incrementale e streaming.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 5 minuti.

## 2026-07-11 - workspace study strips transient row payloads before graph export

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) svuota dai row i campi transienti gia copiati nell'enriched workspace e rilascia `semantic_text`/`analysis_text` dopo `_terms`, cosi il tratto finale trattiene meno payload senza cambiare CSV o report.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); resta aperta la parte piu ampia di scalabilita su lettura incrementale/streaming.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 25 minuti.

## 2026-07-11 - workspace study keeps analysis fallback only when semantic text is missing

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) e [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) tengono `analysis_text` solo quando `semantic_text` e vuoto, cosi il payload delle righe resta piu piccolo senza rompere il fallback usato dai rerun dopo reset derivati; i helper di topic/report continuano a usare il testo raw solo quando serve.
- Verifiche eseguite: `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py tests\test_study_workbench.py -q"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_workspace_health.py::test_study_after_derived_reset_and_second_rerun -q"`, `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); il default temp di pytest nel sandbox non era accessibile, quindi le verifiche sono state eseguite con `TEMP/TMP/TMPDIR` puntati a `.tmp` nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 40 minuti.

## 2026-07-10 - workspace study removes duplicate attachment report buffer

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) non costruisce piu `attachment_report_rows`; il report usa direttamente `attachment_rows` e gli allegati vengono rilasciati solo dopo `study_report.html`, cosi il workspace evita una copia temporanea inutile senza cambiare output.
- Verifiche eseguite: `powershell -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k 'study_report_declares_attachment_state_topic_method_and_fallback or sample_size_limits_imported_messages_but_keeps_valid_workspace_outputs or limit_conversations_trims_workspace_outputs_and_invalidates_resume or limit_messages_trims_workspace_message_exports_and_invalidates_resume'"`, `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 10 minuti.

## 2026-07-10 - workspace study frees attachment summaries earlier

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) libera `topics_by_id`, `assignments` e `attachments_by_conversation` subito dopo la costruzione di `enriched`, comprime `attachment_rows` in un payload minimo per il report e rilascia `rows` prima della classificazione, cosi il ciclo trattiene meno strutture pesanti nel tratto finale.
- Verifiche eseguite: `powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q"`, `powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-10 - workspace export buffers released after use

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: `src/email_cluster/atlas/workspace_study.py` rilascia `message_rows` subito dopo i CSV dei messaggi e libera `inventory_rows`, `attachment_rows`, `enriched` e `topics` dopo il report, cosi il workspace non trattiene piu quei buffer fino al return.
- Verifiche eseguite: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 15 minuti.

## 2026-07-10 - topic summaries moved into discovery

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) salva `scope_summary` ed `example_subjects` nei topic durante `_topic_discovery`, cosi la classification workspace non ricostruisce piu `topic_members`; liberati anche `topics_by_id`, `assignments`, `attachments_by_conversation` ed `entity_rows` appena non servono.
- Verifiche eseguite: `& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 15 minuti.

## 2026-07-10 - conversation linking buffers released earlier

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) rilascia `by_message_id` e `latest_by_subject` subito dopo il calcolo dei root e azzera il buffer union-find `parent` tramite riassegnazione, cosi la fase di grouping trattiene meno memoria senza cambiare output o report.
- Verifiche eseguite: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_atlas_reset.py -q"`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 7 minuti.

## 2026-07-10 - conversation rows slimmed and workspace buffers released

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) elimina i campi raw non riusati dalla vista conversazione appena il record derivato e pronto; [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) libera `term_rows`, `graph_edges`, `graph_nodes`, `classification`, `rows` e `topic_members` dopo gli export intermedi, cosi il finale del ciclo trattiene meno memoria.
- Verifiche eseguite: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 2 minuti.

## 2026-07-10 - workspace exports keep SQLite rows compact

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) ora serializza solo le colonne richieste in `_write_csv` e accetta righe mapping-like senza copiare tutte le chiavi extra; [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) conserva `message_rows`, `attachment_rows` ed `entity_rows` come `sqlite3.Row` invece di convertirle subito in `dict`, e il report legge gli allegati con accesso per colonna.
- Verifiche eseguite: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q"`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-09 - conversation seed rows compacted with tuple metadata

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) conserva ora `linked_ids` e `participants` come tuple interne nella `ConversationSeedRow`, riducendo l'overhead per seed row senza cambiare output o report e mantenendo compatibili i helper pubblici.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_conversations.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 15 minuti.

## 2026-07-09 - conversation dedupe bytes and container release

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) usa ora `sha256(...).digest()` per il set `seen` di dedupe dei testi e rilascia `linked_ids`/`participants` sostituendoli con contenitori vuoti dopo l'uso, riducendo il payload temporaneo per conversation senza cambiare output o report.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 5 minuti.

## 2026-07-09 - conversation insert payload compacted with arrays

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) conserva ora il payload per-conversation in `array("I")` e `array("B")` e lo passa a `executemany` tramite `zip`, cosi la fase di insert resta piu compatta senza cambiare output o report.
- Verifiche eseguite: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_atlas_reset.py -q"`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k \"sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace or study_report_declares_attachment_state_topic_method_and_fallback\""`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 10 minuti.

## 2026-07-09 - rows released progressively during conversation grouping

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) ora libera ogni row gia consumata durante il grouping impostando il riferimento della lista a `None` subito dopo l'uso; la ricostruzione resta invariata ma il picco memoria cala per archivi grandi.
- Verifiche eseguite: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_atlas_reset.py -q"`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_thunderbird_workspace.py -q -k \"sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace or study_report_declares_attachment_state_topic_method_and_fallback\""`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-09 - union-find parent compacted to array

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) usa ora `array('I')` per il buffer union-find `parent`, cosi l'overhead della struttura durante il linking resta piu basso sui workspace grandi senza cambiare output o report.
- Verifiche eseguite: `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -Command "& '.\.venv\Scripts\python.exe' -m pytest tests\test_atlas_reset.py -q"`, `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 10 minuti.

## 2026-07-09 - union-find parent released before aggregation

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) libera `parent` subito dopo la copia di `conversation_root` nei row, cosi il buffer union-find non resta residente per tutta la fase di aggregazione finale.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); nessun blocco nuovo.
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 18 minuti.

## 2026-07-09 - conversation seeds cleaned early and subject maps compacted

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) ora salva subject gia pulito nei seed row, tiene `latest_by_subject` come indice compatto invece di una tupla e libera `rows`/`parent` subito dopo il grouping, cosi il picco memoria del ricostruzione si abbassa senza cambiare l'output.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace or study_report_declares_attachment_state_topic_method_and_fallback"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run_quality_checks.ps1`
- Note: regressione sul fallback risolta cambiando `latest_by_subject` a indice puro; quality checks completi verdi (`121 passed`).
- Prossimo task suggerito: `EA-EPIC8-SCALE`
- Run time: circa 20 minuti.

## 2026-07-01 - conversation message rows keep relation codes compact until final insert

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) non salva piu nella lista temporanea `conversation_rows` la stringa `relation_method` per ogni messaggio: trattiene il solo `relation_code` intero e lo riconverte al nome testuale soltanto nell'`executemany` finale verso `atlas_conversation_messages`, riducendo ancora il payload per-messaggio durante il grouping senza cambiare output o report.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre ancora la retention iniziale della lista `rows` o altre strutture per-riga residue.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation rows store compact relation codes until final write

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) sostituisce il metodo di relazione per-riga da stringa a codice intero compatto nelle seed row di `build_conversations()` e converte di nuovo al nome testuale solo prima di inserire `atlas_conversation_messages`, riducendo ancora il payload temporaneo della lista `rows` senza cambiare output o report.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre ancora la retention iniziale della lista `rows` o altre strutture per-riga residue.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation seeds precompute direction and drop header links earlier

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) sostituisce `sender_lower` nelle seed row con un flag booleano `is_incoming` calcolato una sola volta e svuota `linked_ids` subito dopo il linking header, riducendo ancora il payload trattenuto in memoria da `build_conversations()` senza cambiare output o report.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre ancora la retention iniziale della lista `rows` o altre strutture per-riga residue.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation seed rows moved to slotted dataclass

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) sostituisce le seed row `dict` di `build_conversations()` con una struttura interna `ConversationSeedRow` basata su `dataclass(slots=True)`, conserva `message_id` gia normalizzato e continua a svuotare i campi pesanti appena consumati. La ricostruzione resta invariata ma riduce l'overhead memoria per-email della lista `rows`.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre ancora la retention iniziale della lista `rows` o la mappa `by_message_id`.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation seed rows pre-trim header and participant payload

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) costruisce ora seed row piu leggere gia durante la lettura dal database: estrae subito gli ID collegati da `References` e `In-Reply-To`, normalizza i partecipanti e il sender lowercase, e non conserva nel ciclo successivo `raw_headers_json`, `recipients` o `sender`. La ricostruzione conversazioni resta invariata ma riduce il payload per-email trattenuto in memoria prima del linking.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation rebuild keeps one text column per email

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) non carica piu in memoria sia `current_message_text` sia `body_extracted_text` per ogni riga durante `build_conversations()`: la query seleziona direttamente `coalesce(c.current_message_text, e.body_extracted_text)` come `selected_text` e la pipeline usa quel solo campo temporaneo. [`tests/test_atlas_reset.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_atlas_reset.py) aggiunge una regressione che verifica il fallback al `body_extracted_text` quando manca la riga `clean_texts`.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre la retention della lista `rows` o altre strutture iniziali della ricostruzione conversazioni.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation grouping drops consumed row fields earlier

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) ora svuota appena possibile le mappe temporanee del linking (`by_message_id`, `latest_by_subject`) e rimuove dai row object i campi gia consumati (`subject`, `original_message_id`, date, testi e flag allegati) mentre il `groupby` finale costruisce `atlas_conversations`, riducendo la memoria residente senza cambiare output o report.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`120 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre la memoria della lettura iniziale dal database o della lista `rows`.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation union-find no longer keeps email-id index map

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) non mantiene piu `index_by_email_id` durante `build_conversations()`: il linking header usa gli indici di enumerazione delle righe e il fallback per subject conserva `(row_index, row)` per riusare direttamente la union-find, riducendo un dizionario per archivio senza cambiare output o report.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`120 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre la memoria della lettura iniziale `rows` o della mappa `by_message_id`.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation grouping now avoids per-group member list copies

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) non costruisce piu `members = list(members_iter)` per ogni conversazione durante il `groupby` finale di `build_conversations()`: aggrega conteggi, partecipanti, testi unici e righe da inserire in un solo passaggio, poi rimuove dai row object i campi temporanei piu pesanti appena non servono piu. Il contratto del report e delle tabelle Atlas resta invariato.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`120 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre la memoria della prima lettura `rows` o delle mappe temporanee (`index_by_email_id` / `by_message_id`) prima del grouping.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - subject fallback no longer buffers all rows per topic

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) non costruisce piu `subjects[subject]` con tutte le righe prima del fallback `subject_participants_date`; il linking conserva solo l'ultimo candidato utile per subject nel flusso ordinato, riducendo il buffering per archivi grandi. [`tests/test_atlas_reset.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_atlas_reset.py) aggiunge una regressione che inserisce due email senza header ma con subject/partecipanti coerenti e verifica il raggruppamento fallback.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`120 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre ulteriormente le strutture trattenute per riga durante la ricostruzione o introdurre lettura ancora piu incrementale.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - union-find compacted for sparse email ids

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) non mantiene piu `parent` come dizionario keyed by email-id durante `build_conversations()`: usa una struttura compatta indicizzata per posizione e mappa i link header direttamente agli indici riga, riducendo overhead memoria senza cambiare output o report. [`tests/test_atlas_reset.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_atlas_reset.py) aggiunge una regressione con email ID `999` per bloccare il supporto a ID sparsi/non contigui.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`119 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre ancora memoria/latency nella lettura incrementale dei messaggi o nel buffering per subject.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation rows now drop raw fields after linkage analysis

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) ora memorizza partecipanti e sender normalizzato direttamente su ogni riga, elimina `raw_headers_json`, `recipients` e `sender` appena non servono piu, e sostituisce la mappa esterna `relation_method` con `_relation_method` per-riga. La ricostruzione conserva lo stesso output ma trattiene meno dati durante `build_conversations()`.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`118 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre le strutture union-find ancora residenti o introdurre lettura piu incrementale dei messaggi.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-06-30 - bootstrap autonomous development

- Task: `EA-EPIC0-BOOT`
- Esito: completed
- Modifiche: creati AGENTS, backlog persistente, workflow, criteri, prompt, stato, script guard/next-task/quality e workflow GitHub opzionale
- Verifiche previste: dry-run script, lint/test/smoke o fallback equivalente
- Note: `codex.exe --help` e `codex exec --help` non verificabili nel sandbox corrente per `Accesso negato`; integrazione CLI marcata `manual integration required`
- Prossimo task suggerito: `EA-EPIC1-WORKSPACE`

## 2026-06-30 - repository cleanup and native Codex scheduling

- Task: `EA-EPIC0-HOOKS`
- Esito: partial-progress
- Modifiche: rimossi artifact di run interrotta, ripristinati report tracked cancellati, aggiunto prompt `.codex/prompts/automation_cycle.md`, riallineata la documentazione alla cron automation nativa Codex
- Verifiche eseguite: `python -m pytest -q`, `email-atlas --help`, `email-atlas smoke-test`
- Note: la schedulazione preferita e ora interna a Codex; la verifica della sintassi hook/CLI nativa resta esterna al sandbox
- Prossimo task suggerito: `EA-EPIC1-WORKSPACE`

## 2026-06-30 - hook integration contract stabilized

- Task: `EA-EPIC0-HOOKS`
- Esito: completed
- Modifiche: chiarita in `docs/non_interactive_codex.md` la separazione tra automazione nativa Codex (`automation_cycle.md`) e runner locale scriptato (`next_task.md`); aggiunto `tests/test_codex_automation_assets.py` per bloccare regressioni su prompt attesi e stato `manual integration required`
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_codex_automation_assets.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: `codex --help` e `codex exec --help` confermano ancora `Accesso negato` nel sandbox corrente, quindi l'integrazione CLI resta correttamente documentata come manuale
- Prossimo task suggerito: `EA-EPIC1-WORKSPACE`

## 2026-06-30 - workspace stage state hardened

- Task: `EA-EPIC1-WORKSPACE`
- Esito: completed
- Modifiche: `src/email_cluster/atlas/workspace_study.py` ora persiste `state.json` v2 con `stage_details`, `selected_targets` e opzioni; `--stages` si ferma allo stage richiesto; `--resume` riusa solo stage completi con artefatto minimo ancora presente; `--rebuild-stage` invalida lo stage richiesto e tutti i successivi
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_workspace_health.py::test_study_after_derived_reset_and_second_rerun -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`104 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace
- Prossimo task suggerito: `EA-EPIC2-ATTACHMENTS`

## 2026-06-30 - attachment text stage decoupled from import

- Task: `EA-EPIC2-ATTACHMENTS`
- Esito: completed
- Modifiche: `src/email_cluster/atlas/workspace_study.py` importa sempre gli allegati in modalita metadata-only durante `import_mbox`; lo stage `extract_attachment_text_optional` ora popola gli estratti in un secondo passaggio oppure li azzera quando `--no-attachments-text` e attivo; il cambio opzioni allegati invalida solo questo stage e i successivi. Aggiunto in `tests/test_thunderbird_workspace.py` il caso `senza allegati -> con allegati` con resume senza reimport dei messaggi.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_workspace_health.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: gli estratti allegati precedenti vengono rimossi quando il workspace torna a `--no-attachments-text`, cosi `build_semantic_text` non riusa testo stale.
- Prossimo task suggerito: `EA-EPIC3-CLEANING`

## 2026-06-30 - historical email text cleaning hardened

- Task: `EA-EPIC3-CLEANING`
- Esito: completed
- Modifiche: `src/email_cluster/cleaning/normalizer.py` ora rimuove stopword email ad alto rumore e pattern data sia da subject sia dal current message; `src/email_cluster/config.py` porta il preprocessing a `v2.1.0` per forzare il ricalcolo pulito; `src/email_cluster/atlas/workspace_study.py` costruisce le label topic da termini filtrati, cosi token come `subject`, `sent`, `data` e `03_2026` non riappaiono nelle etichette.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_cleaning.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`109 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC4-SCOPE`

## 2026-06-30 - preliminary scope classification propagated to workspace

- Task: `EA-EPIC4-SCOPE`
- Esito: completed
- Modifiche: `src/email_cluster/atlas/discovery.py` introduce `classify_scope` con scope, confidence e reason locali; `src/email_cluster/atlas/study.py` propaga questi campi alle conversazioni; `src/email_cluster/atlas/workspace_study.py` esporta `scope_confidence` e `scope_reason` nei CSV e usa lo scope prevalente del topic come `proposed_scope` nel `classification_workspace.csv`; `docs/pipeline.md` documenta il contratto aggiornato.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_workspace_health.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: i topic del fixture possono restare piccoli e mescolati, quindi i test bloccano la presenza di scope preliminari motivati senza assumere cluster perfettamente puri; warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile.
- Prossimo task suggerito: `EA-EPIC5-TOPICS`

## 2026-06-30 - topic categories made revision-friendly

- Task: `EA-EPIC5-TOPICS`
- Esito: completed
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) ora trasforma i topic grezzi in categorie candidate guidate da scope, termini, domini e segnali allegati; `topics.csv` esporta `label_reason`, `warnings`, `main_domains`, `main_attachments`, borderline e outlier; `classification_workspace.csv` riusa motivazione e warning della categoria. [`tests/test_thunderbird_workspace.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_thunderbird_workspace.py) copre account GitHub/Google, amministrativo fatture, PEC/Hiro e il nuovo contratto dei CSV.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_cleaning.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`112 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC6-CLASSIFICATION-WORKSPACE`

## 2026-06-30 - classification workspace made reviewable

- Task: `EA-EPIC6-CLASSIFICATION-WORKSPACE`
- Esito: completed
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) ora arricchisce `classification_workspace.csv` con esempi concreti di subject in `description`, proposte locali per `proposed_activity` e `proposed_theme` che non copiano il nome categoria, e `suggested_decision` prudente (`approve`, `exclude`, `unclear`) riportata anche in `notes`. Aggiornata anche [`docs/classification_workspace.md`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/docs/classification_workspace.md) sul significato revisionabile di questi campi e rafforzati i test in [`tests/test_thunderbird_workspace.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_thunderbird_workspace.py).
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_cleaning.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`113 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC7-STUDY-REPORT`

## 2026-06-30 - study report made self-contained

- Task: `EA-EPIC7-STUDY-REPORT`
- Esito: completed
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) ora rende `study_report.html` autosufficiente senza GUI, con sezioni dedicate a stato allegati per `extraction_status`, metodo topic attivo, fallback dichiarati e dataset principali; aggiornata anche [`docs/pipeline.md`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/docs/pipeline.md) sul contratto del report e aggiunto in [`tests/test_thunderbird_workspace.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_thunderbird_workspace.py) un test esplicito su allegati, metodo topic e fallback TF-IDF.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`114 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - sample-size made effective for rapid study runs

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/cli/app.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/cli/app.py) ora accetta `--sample-size` anche nell'import e tronca davvero i messaggi processati; [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) passa il limite allo study workspace e segnala nel report quando il dataset e un campione rapido; aggiornati [`tests/test_thunderbird_workspace.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_thunderbird_workspace.py) e [`docs/pipeline.md`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/docs/pipeline.md).
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: primo step di `EA-EPIC8-SCALE` chiuso senza aprire un secondo fronte; restano limiti dedicati su conversazioni e memoria per completare l'epic.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation limit added to rapid study workspace runs

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/cli.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/cli.py) espone `--limit-conversations`; [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) limita conversazioni, messaggi e allegati esportati nello study workspace, registra l'opzione in `state.json` e `workspace.json`, invalida `build_conversations` se il valore cambia e aggiunge un warning esplicito nel report; aggiornati [`tests/test_thunderbird_workspace.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_thunderbird_workspace.py) e [`docs/pipeline.md`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/docs/pipeline.md).
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: secondo step di `EA-EPIC8-SCALE` chiuso senza aprire una nuova epic; resta da affrontare il fronte memoria/streaming per archivi molto grandi.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - rapid study limits now cut intermediate memory load

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/study.py) accetta ora un `limit` opzionale in `_conversation_rows`, cosi lo study workspace non legge tutte le conversazioni prima di troncarle. [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) filtra inoltre `messages` e `attachments` lato query SQL sul solo sottoinsieme di conversazioni e messaggi selezionati, riducendo i caricamenti intermedi nelle run rapide.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k 'sample_size or limit_conversations or limit_messages'`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k 'study_pipeline_builds_mixed_conversations_attachments_and_workspace or study_report_declares_attachment_state_topic_method_and_fallback'`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`117 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - workspace graph export now respects rapid conversation limits

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) non usa piu `export_study_pack` per copiare `nodes.csv` e `edges.csv` dentro lo study workspace: genera i grafi direttamente dalle conversazioni gia selezionate e dai termini locali, evitando una rilettura dell'intero dataset e la creazione di `_base_pack`. [`tests/test_thunderbird_workspace.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_thunderbird_workspace.py) verifica che con `--limit-conversations` anche i nodi e gli archi referenzino solo le conversazioni effettivamente esportate.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k 'limit_conversations or limit_messages or sample_size'`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`117 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation rebuild avoids unused heavy columns

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) ora legge per `build_conversations` solo le colonne realmente usate per ricostruzione e analisi (`current_message_text`, header essenziali, testo estratto, flag allegati), evitando di caricare in memoria l'intera riga `emails` e campi puliti non usati come `quoted_thread_text` e `forwarded_text`.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`117 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre anche le strutture in memoria della union-find o introdurre lettura piu incrementale nella ricostruzione conversazioni.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation report examples capped for large archives

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) non accumula piu un record di esempio per ogni conversazione ricostruita: mantiene solo buffer piccoli per `long_conversation_examples`, conversazioni isolate, fallback, casi da verificare e multi-message, riducendo l'overhead memoria del report su archivi grandi senza cambiare il payload restituito. [`tests/test_atlas_reset.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_atlas_reset.py) blocca i limiti massimi di questi insiemi.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`118 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre la memoria della ricostruzione prima del grouping finale, in particolare union-find e metadati tenuti per riga.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-01 - conversation grouping no longer duplicates row references

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) non costruisce piu il dizionario intermedio `groups` con una lista di righe per ogni conversazione. Dopo la union-find annota il root su ogni email, ordina una sola volta e processa i membri tramite `itertools.groupby`, riducendo la memoria intermedia mantenuta durante `build_conversations()` su archivi grandi senza cambiare output o report.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "sample_size or limit_conversations or limit_messages or study_pipeline_builds_mixed_conversations_attachments_and_workspace"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`118 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre la memoria delle mappe `parent` e `relation_method` oppure introdurre lettura piu incrementale dei messaggi.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-11 - inventory count now survives resume reruns

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/workspace_study.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/workspace_study.py) conta `input_inventory.csv` con un helper leggero, rilascia `inventory_rows` subito dopo la scrittura del CSV e passa al report solo il conteggio necessario; sui rerun con resume il report rilegge il conteggio dall'inventario esistente invece di dipendere dal buffer ancora in memoria. [`tests/test_thunderbird_workspace.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/tests/test_thunderbird_workspace.py) aggiunge una regressione sul rerun che verifica il conteggio inventario nel report.
- Verifiche eseguite: `.\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k 'pipeline_rerun_empty_workspace_atlas_and_orange or study_pipeline_builds_mixed_conversations_attachments_and_workspace or study_report_declares_attachment_state_topic_and_fallback'`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`121 passed`); warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile nel workspace. Prossimo fronte utile: ridurre ancora i buffer di ricostruzione in `conversations.py` o rendere piu incrementale la lettura iniziale.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-11 - conversation seeds fetch texts per batch

- Task: `EA-EPIC8-SCALE`
- Esito: partial-progress
- Modifiche: [`src/email_cluster/atlas/conversations.py`](C:/Users/Marco/Documents/Classificazione%20semantica%20mail%20storiche/src/email_cluster/atlas/conversations.py) ora materializza solo i metadati seed iniziali e ricarica `selected_text` per conversazione in batch dopo il grouping, cosi il buffer di testo non resta vivo per tutta la materializzazione. `ConversationSeedRow` non conserva piu il testo completo e il fallback body/clean text resta invariato.
- Verifiche eseguite: `& .\.venv\Scripts\python.exe -m py_compile src\email_cluster\atlas\conversations.py`, `& .\.venv\Scripts\python.exe -m pytest tests\test_atlas_reset.py -q`, `& .\.venv\Scripts\python.exe -m pytest tests\test_thunderbird_workspace.py -q -k "study_pipeline_builds_mixed_conversations_attachments_and_workspace or limit_conversations or limit_messages or sample_size"`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`
- Note: quality checks completi verdi (`122 passed`); residuo futuro ancora aperto su `message_ids` e altre strutture pre-grouping se si vuole continuare a stringere il picco memoria.
- Prossimo task suggerito: `EA-EPIC8-SCALE`

## 2026-07-12 - Atlante finale validation consolidated

- Task: `EA-EPIC10-ATLAS`
- Esito: completed
- Modifiche: `import_classification` valida intestazioni, ID numerici, duplicati e appartenenza delle categorie prima di scrivere; `build_atlas_from_workspace` rifiuta decisioni sconosciute e distingue esplicitamente gli ID topic del workspace dalle PK database. Gli output finali restano derivati soltanto da `approve`, `rename` e `merge` normalizzati.
- Verifiche eseguite: `& .\.venv\Scripts\python.exe -m pytest tests\test_study_workbench.py tests\test_thunderbird_workspace.py -q -k "classification or pipeline_rerun_empty_workspace_atlas_and_orange"`; `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_quality_checks.ps1`.
- Note: test mirati verdi (`5 passed`); quality checks completi verdi (`126 passed`). Warning non bloccanti invariati su FastAPI/TestClient, joblib core fisici e `.pytest_cache` non scrivibile.
- Rischi/limiti: gli ID topic del workspace non sono PK database; il contratto e ora esplicito e l'import CLI diretto continua a validare le PK.
- Prossimo task suggerito: `EA-EPIC9-ORANGE`
