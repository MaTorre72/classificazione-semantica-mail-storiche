# Development Backlog

Backlog persistente ordinato per priorita. Ogni ciclo autonomo deve scegliere un solo task aperto, aggiornare questo file e sincronizzare `.codex/state/backlog.json`.

## Regole stato

- `pending`: non ancora iniziato
- `in_progress`: attivo nel ciclo corrente o pronto per il prossimo
- `blocked`: fermo per dipendenza reale
- `done`: accettato con test e log aggiornati

## Task

### EA-INCREMENTAL-REBUILD-AND-ATTACHMENT-RESUME

- Area: workspace-stage-management
- Priorita: P0
- Stato: done
- Titolo: esporre rebuild sicuro nel BAT e rendere incrementale la ripresa allegati
- Descrizione: permettere all'operatore di includere nuove email in un workspace esistente con backup esplicito e impedire che una ripresa dell'estrazione allegati riprocessi i file sorgente già completati.
- File coinvolti: `CREA_STUDIO.bat`, `src/email_cluster/atlas/conversations.py`, `src/email_cluster/atlas/workspace_study.py`, `tests/test_windows_launchers.py`, `docs/*`
- Criteri di accettazione: prompt rebuild nel BAT; messaggio errore con comando reale; solo allegati `metadata_only` e relative sorgenti vengono ripresi; workspace reale completato
- Rischio: medio
- Dipendenze: `EA-CONVERSATION-STABLE-KEY-COLLISION`
- Note ultimo ciclo: 2026-07-12: `wsp_2` completato su 26.740 email, 17.430 conversazioni, 40 topic e 22.967 allegati; 12/12 stage verdi, nessun warning; backup SQLite creato prima del rebuild.

### EA-CONVERSATION-STABLE-KEY-COLLISION

- Area: conversation-reconstruction
- Priorita: P0
- Stato: done
- Titolo: impedire collisioni stable_key su archivi reali con Message-ID assente o riutilizzato
- Descrizione: rendere univoca e ripetibile la chiave delle conversazioni usando il `message_hash` locale oltre ai metadati e ai Message-ID.
- File coinvolti: `src/email_cluster/atlas/conversations.py`, `tests/test_atlas_conversations.py`, `docs/troubleshooting.md`
- Criteri di accettazione: conversazioni con stessi metadati ma hash diversi non collidono; Message-ID riutilizzati non collidono; ricostruzione completa sul database copiato da `wsp_2`
- Rischio: medio
- Dipendenze: nessuna
- Note ultimo ciclo: 2026-07-12: validato prima su copia del database e poi con rilancio completo di `wsp_2`: 1450 messaggi, 954 conversazioni, 22 topic e 12/12 stage completati senza collisioni o warning.

### EA-CLEANUP-LAUNCHERS-AND-LEGACY

- Area: repository-maintenance
- Priorita: P1
- Stato: done
- Titolo: verificare launcher Windows e archiviare file superati nelle sottocartelle
- Descrizione: provare realmente il percorso BAT su fixture locale, mantenere solo i launcher correnti alla radice e archiviare launcher e rapporti storici senza cancellare dati o moduli ancora referenziati.
- File coinvolti: `*.bat`, `archive/`, `reports/archive/`, `tests/test_windows_launchers.py`, `.gitignore`
- Criteri di accettazione: menu e launcher specializzati verificati; GUI Tkinter legacy archiviata; report progettuali storici archiviati; workspace locali ignorati; moduli ancora importati o testati preservati
- Rischio: basso
- Dipendenze: `EA-DOCS-OPERATOR-MANUAL`
- Note ultimo ciclo: 2026-07-12: menu, study, doctor, Orange e build-atlas verificati su fixture locale; repair verificato nel percorso di annullamento sicuro; `email-cluster ui --help` conferma la console web; vecchio `start_gui.bat` e due report storici archiviati.

### EA-DOCS-OPERATOR-MANUAL

- Area: documentation
- Priorita: P1
- Stato: done
- Titolo: riordinare documentazione, comandi e launcher Windows
- Descrizione: definire un solo punto di ingresso consigliato, separare il percorso moderno dalle superfici legacy e produrre un manuale operativo verificato sui launcher e sull'help CLI reale.
- File coinvolti: `README.md`, `docs/README.md`, `docs/guida_rapida.md`, `docs/guida_uso_completa.md`, `docs/comandi.md`
- Criteri di accettazione: `EMAIL_ATLAS.bat` indicato senza ambiguita; percorso snapshot -> studio -> revisione -> Atlante documentato; launcher e CLI distinti dalle superfici legacy; indice documentale disponibile
- Rischio: basso
- Dipendenze: nessuna
- Note ultimo ciclo: 2026-07-12: completato il riordino operator-facing; 21 documenti storici sono stati conservati in `docs/archive/` con un indice esplicito, senza cancellazioni e senza modificare la pipeline.

### EA-EPIC0-BOOT

- Area: autonomous-dev
- Priorita: P0
- Stato: done
- Titolo: bootstrap infrastruttura autonoma Codex
- Descrizione: creare AGENTS, backlog persistente, prompt, stato, guard, next-task runner, quality checks e documentazione iniziale.
- File coinvolti stimati: `AGENTS.md`, `docs/*`, `.codex/*`, `scripts/*`, `.github/workflows/*`
- Comandi da eseguire: `scripts/run_quality_checks.ps1`, `scripts/codex_next_task.ps1 -DryRun`
- Test da aggiungere: smoke del workflow non interattivo e parsing backlog
- Criteri di accettazione: file base esistenti, lock file gestito, dry-run disponibile, quality gate invocabile, stato persistente inizializzato
- Rischio: medio
- Dipendenze: nessuna
- Note ultimo ciclo: completato nel primo ciclo con integrazione Codex documentata come manuale dove la CLI non e verificabile dal sandbox corrente.

### EA-EPIC0-HOOKS

- Area: autonomous-dev
- Priorita: P1
- Stato: done
- Titolo: rifinire integrazione hook o equivalenti script
- Descrizione: collegare guard, quality gate, output check e secret check alla modalita reale supportata dalla CLI Codex o mantenere la procedura manuale documentata.
- File coinvolti stimati: `docs/non_interactive_codex.md`, `.codex/`, `scripts/`
- Comandi da eseguire: `codex --help`, `codex exec --help`
- Test da aggiungere: verifica help CLI e compatibilita argomenti
- Criteri di accettazione: nessuna sintassi inventata; integrazione verificata o dichiarata manuale
- Rischio: basso
- Dipendenze: EA-EPIC0-BOOT
- Note ultimo ciclo: documentata la distinzione tra prompt nativo e runner scriptato; aggiunto test repository-level sui prompt attesi e sullo stato `manual integration required`; quality checks completi superati, mentre `codex --help` e `codex exec --help` restano non eseguibili nel sandbox per `Accesso negato`.

### EA-EPIC1-WORKSPACE

- Area: workspace-stage-management
- Priorita: P1
- Stato: done
- Titolo: rendere robusti stato workspace, stage e invalidazione
- Descrizione: consolidare `state.json`, checkpoint, `--resume`, `--stages`, `--rebuild-stage` e invalidazione degli stage dipendenti.
- File coinvolti stimati: `src/email_cluster/atlas/workspace_study.py`, `tests/*`, `docs/pipeline.md`
- Comandi da eseguire: `email-atlas study --workspace <ws> --stages list`
- Test da aggiungere: resume, rebuild-stage, invalidazione dipendenze
- Criteri di accettazione: stage autonomi, rilanciabili e con stato chiaro
- Rischio: alto
- Dipendenze: EA-EPIC0-BOOT
- Note ultimo ciclo: completato con stato stage persistente (`state.json` v2), stop reale su `--stages`, resume con skip degli stage completi solo se l'artefatto minimo esiste ancora, e invalidazione a valle su `--rebuild-stage` o drift delle opzioni di studio.

### EA-EPIC2-ATTACHMENTS

- Area: attachments
- Priorita: P1
- Stato: done
- Titolo: allegati come stage autonomo e invalidante
- Descrizione: separare `attachment_metadata` e `attachment_text`, supportare batch, limiti dimensione e invalidazione degli stage successivi.
- File coinvolti stimati: `src/email_cluster/atlas/*attachment*`, `src/email_cluster/atlas/workspace_study.py`, `tests/*`
- Comandi da eseguire: `email-atlas study --workspace <ws> --with-attachments-text`
- Test da aggiungere: prima senza allegati, poi con allegati; nessuna riestrazione inutile
- Criteri di accettazione: stage attachments rilanciabile e coerente
- Rischio: alto
- Dipendenze: EA-EPIC1-WORKSPACE
- Note ultimo ciclo: completato separando import metadata-only da `extract_attachment_text_optional`; il cambio `--with/--no-attachments-text` invalida solo lo stage testo e i successivi, con resume senza reimport dei messaggi invariati.

### EA-EPIC3-CLEANING

- Area: text-cleaning
- Priorita: P1
- Stato: done
- Titolo: pulizia testo severa per email storiche
- Descrizione: introdurre stopword email, filtri date/pattern, rimozione header/footer/disclaimer e versionamento preprocessing.
- File coinvolti stimati: `src/email_cluster/atlas/parsing.py`, `src/email_cluster/*clean*`, `tests/*`
- Comandi da eseguire: `email-atlas study --sample-size 50 --workspace <ws>`
- Test da aggiungere: rimozione `your`, `come`, `data`, `sent`, `subject`; esclusione pattern data da topic label
- Criteri di accettazione: `semantic_text` e topic source molto piu leggibili
- Rischio: alto
- Dipendenze: EA-EPIC1-WORKSPACE
- Note ultimo ciclo: completato con preprocessing `v2.1.0`, rimozione di stopword email e pattern data nel cleaner, e label topic che non riusano piu token come `subject`, `sent`, `data` o `03_2026`.

### EA-EPIC4-SCOPE

- Area: scope-discovery
- Priorita: P2
- Stato: done
- Titolo: classificazione preliminare di scope
- Descrizione: aggiungere `probable_scope`, `scope_confidence` e `scope_reason` per separare meglio i topic.
- File coinvolti stimati: `src/email_cluster/atlas/discovery.py`, `src/email_cluster/atlas/workspace_study.py`, `tests/*`
- Comandi da eseguire: `email-atlas study --workspace <ws>`
- Test da aggiungere: scope popolato e non tutto indeterminato
- Criteri di accettazione: topic separati per scope preliminare
- Rischio: medio
- Dipendenze: EA-EPIC3-CLEANING
- Note ultimo ciclo: completato con classificazione scope centralizzata e propagata a `conversations.csv` e `classification_workspace.csv`; ogni conversazione espone `scope_confidence` e `scope_reason`, mentre i topic ereditano uno `proposed_scope` preliminare non piu lasciato a `Da definire`.

### EA-EPIC5-TOPICS

- Area: topic-candidates
- Priorita: P1
- Stato: done
- Titolo: topic grezzi in categorie candidate revisionabili
- Descrizione: sostituire label frammentate con categorie candidate, `label_reason`, warning e conversazioni rappresentative.
- File coinvolti stimati: `src/email_cluster/atlas/discovery.py`, `reports`, `tests/*`
- Comandi da eseguire: `email-atlas study --workspace <ws>`
- Test da aggiungere: GitHub e Google in `Account / notifiche tecniche`, fatture in categoria amministrativa, PEC/Hiro leggibile
- Criteri di accettazione: `topics.csv` e report leggibili e revisionabili
- Rischio: alto
- Dipendenze: EA-EPIC3-CLEANING, EA-EPIC4-SCOPE
- Note ultimo ciclo: completato con normalizzazione locale delle label topic in categorie revisionabili guidate da scope, termini, domini e segnali allegati; `topics.csv` ora espone `label_reason`, `warnings`, `main_domains`, `main_attachments`, borderline e outlier, mentre `classification_workspace.csv` riusa le stesse motivazioni.

### EA-EPIC6-CLASSIFICATION-WORKSPACE

- Area: workspace-review
- Priorita: P2
- Stato: done
- Titolo: classification workspace davvero revisionabile
- Descrizione: valorizzare `suggested_decision`, `proposed_scope`, `proposed_activity`, `proposed_theme` con esempi concreti.
- File coinvolti stimati: `src/email_cluster/atlas/workspace_study.py`, `tests/*`, `docs/classification_workspace.md`
- Comandi da eseguire: `email-atlas study --workspace <ws>`
- Test da aggiungere: campi non tutti `Da definire`; niente semplice copia della raw label
- Criteri di accettazione: file utile per revisione umana
- Rischio: medio
- Dipendenze: EA-EPIC5-TOPICS
- Note ultimo ciclo: completato arricchendo `classification_workspace.csv` con esempi di subject in `description`, `proposed_activity` e `proposed_theme` derivati da euristiche locali invece che copiati dal nome categoria, e `suggested_decision` prudente (`approve`, `exclude`, `unclear`) tracciata anche nelle note.

### EA-EPIC7-STUDY-REPORT

- Area: reporting
- Priorita: P2
- Stato: done
- Titolo: report di studio leggibile senza GUI
- Descrizione: mostrare stato allegati, qualita testo, metodo topic, warning, link CSV e limiti fallback.
- File coinvolti stimati: `src/email_cluster/atlas/*report*`, `tests/*`
- Comandi da eseguire: `email-atlas study --workspace <ws>`
- Test da aggiungere: presenza di stato allegati, metodo topic e warning TF-IDF
- Criteri di accettazione: `study_report.html` autosufficiente
- Rischio: medio
- Dipendenze: EA-EPIC2-ATTACHMENTS, EA-EPIC5-TOPICS
- Note ultimo ciclo: completato rendendo `study_report.html` autosufficiente anche senza GUI; il report ora espone stato allegati per `extraction_status`, metodo topic attivo, fallback dichiarati (`TF-IDF + SVD + KMeans`), warning e link ai CSV principali.

### EA-EPIC8-SCALE

- Area: scalability
- Priorita: P2
- Stato: done
- Titolo: scalabilita per archivi grandi
- Descrizione: batch, streaming, sample-size, filtri data/cartelle e limiti di memoria.
- File coinvolti stimati: `src/email_cluster/atlas/*`, `tests/*`, `docs/*`
- Comandi da eseguire: `email-atlas study --sample-size 50 --workspace <ws>`
* Test da aggiungere: benchmark ripetibile su almeno 10.000 messaggi; misurazione del tempo totale e del picco di memoria; verifica di `sample-size`, `limit-messages` e `limit-conversations`; verifica dei filtri data/cartella oppure trasferimento esplicito di tali filtri in un task successivo.

* Criteri di accettazione:

  1. la pipeline completa termina correttamente su almeno 10.000 messaggi senza errori di memoria;
  2. tempo di esecuzione, picco di memoria, messaggi elaborati, conversazioni elaborate e dimensione degli output sono registrati in `docs/scalability_benchmark.md`;
  3. `sample-size`, `limit-messages` e `limit-conversations` limitano realmente i dati letti ed esportati;
  4. i principali export vengono prodotti senza mantenere inutilmente in memoria copie complete dell’archivio;
  5. i filtri data/cartella sono implementati e testati oppure trasferiti in un nuovo task esplicitamente non bloccante;
  6. tutti i quality check sono verdi.

* Piano di chiusura:

  * Run 1: predisporre ed eseguire il benchmark, senza ulteriori micro-ottimizzazioni preventive;
  * Run 2: correggere esclusivamente eventuali problemi dimostrati dal benchmark e decidere la gestione dei filtri data/cartella;
  * Run 3: rieseguire benchmark e quality check, aggiornare l’EPIC a `done` o `blocked` e registrare il risultato finale.

* Vincolo: non sono ammessi ulteriori run `partial-progress` oltre questo piano di chiusura. Le ottimizzazioni residue non necessarie ai criteri sopra indicati devono essere trasferite in task separati.

- Rischio: alto
- Dipendenze: EA-EPIC1-WORKSPACE
- Note ultimo ciclo: 2026-07-12: chiusura completata con benchmark sintetico locale da 10.000 messaggi e 5.000 conversazioni; pipeline completa in 326,061 s, picco Python 21,722 MiB, output 40,615 MiB e 12/12 stage completati. I filtri data/cartella sono trasferiti a `EA-EPIC8-FILTERS`.

### EA-EPIC8-FILTERS

- Area: scalability
- Priorita: P3
- Stato: done
- Titolo: filtri data e cartella per lo study workspace
- Descrizione: aggiungere filtri locali espliciti per intervallo data e cartelle sorgente senza modificare il contratto di scalabilita gia accettato.
- File coinvolti stimati: `src/email_cluster/atlas/workspace_study.py`, `src/email_cluster/atlas/cli.py`, `tests/*`, `docs/*`
- Test da aggiungere: inclusione ed esclusione per data; inclusione ed esclusione per cartella snapshot
- Criteri di accettazione: filtri applicati prima degli export, persistiti nello stato e coperti da invalidazione/test
- Rischio: medio
- Dipendenze: EA-EPIC8-SCALE
- Note ultimo ciclo: 2026-07-12: aggiunti `--date-from`, `--date-to` e `--source-folder` ripetibile; i filtri agiscono prima degli export, sono persistiti e invalidano `build_conversations` al cambio. Test mirato e quality checks completi verdi.
- Note ultimo ciclo: 2026-07-12: `workspace_study.py` costruisce `selected_conversation_ids` direttamente dall'ordine gia restituito da `_conversation_rows()`, evitando `sorted(...)` e una lista temporanea in piu; test mirati e quality checks completi verdi (`124 passed`).
- Note ultimo ciclo: 2026-07-12: `_conversation_selected_texts()` ora streama i testi selezionati in batch ordinati invece di materializzare un dizionario per conversazione; la regressione in `tests/test_atlas_reset.py` blocca l'ordine di `unique_clean_text` e i quality checks completi sono verdi (`123 passed`).
- Note ultimo ciclo: 2026-07-12: `messages.csv` e `conversation_messages.csv` in `workspace_study.py` ora vengono scritti nello stesso passaggio streaming invece di materializzare `message_rows`; gli ID messaggio restano raccolti on the fly per il filtro allegati e il test mirato su `limit_messages` piu i quality checks completi sono verdi (`124 passed`).
- Note ultimo ciclo: 2026-07-12: `_semantic_points()` ora consuma il cursor embedding direttamente invece di materializzarlo in una lista, e una regressione in `tests/test_study_workbench.py` copre il path `embeddings_pca` con cache minima; quality checks completi verdi (`124 passed`).
- Note ultimo ciclo: 2026-07-12: `entities.csv` in `workspace_study.py` ora streama direttamente dal cursor DB invece di materializzare `entity_rows`, e `tests/test_thunderbird_workspace.py` blocca il dominio `example.it` nel fixture; test mirato e quality checks completi verdi (`124 passed`).
- Note ultimo ciclo: 2026-07-12: `workspace_study.py` ora evita di materializzare `selected_message_ids` quando `limit_messages` non e impostato e libera `selected_conversation_ids` subito dopo l'export allegati; test mirati e quality checks completi verdi (`124 passed`).
- Note ultimo ciclo: 2026-07-12: `selected_conversation_ids` e `selected_message_ids` in `workspace_study.py` ora usano buffer `array('I')` compatti invece di `set`/`list`; la regressione in `tests/test_thunderbird_workspace.py` verifica l'allineamento dei `message_id` tra `messages.csv` e `conversation_messages.csv`, e i quality checks completi sono verdi (`124 passed`).
- Note ultimo ciclo: 2026-07-12: `attachment_texts.csv` viene scritto in streaming durante l'export allegati e il contesto per conversazione resta in stringhe bounded invece che in liste di tuple; test mirati e quality checks completi verdi (`124 passed`).
- Note ultimo ciclo: 2026-07-11: `build_conversations()` ora passa l'array compatto `conversation_email_ids` direttamente a `_conversation_selected_texts` invece di copiarlo in lista; la regressione in `tests/test_atlas_reset.py` verifica che l'helper riceva `array('I')` e i quality checks completi sono verdi (`123 passed`).
- Note ultimo ciclo: 2026-07-11: `build_conversations()` ora ricarica `selected_text` per conversazione in batch dopo il grouping, cosi il seed iniziale resta solo metadati e il testo non vive piu per tutta la materializzazione; test mirati e quality checks completi verdi (`122 passed`).
- Note ultimo ciclo: 2026-07-11: nel ramo parziale `build_classification_workspace` `topics` viene liberato prima di `finalize_partial()`, cosi il return non tiene vivo l'intero buffer topic; test mirati e quality checks completi verdi (`122 passed`).
- Note ultimo ciclo: 2026-07-11: `study.py` ora streama `conversation_messages.csv`, `entities.csv` e `attachments.csv` direttamente dai cursori del DB durante `export_study_pack`, cosi non mantiene copie materializzate extra; test mirati e quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: `_conversation_rows()` pre-aggrega `entity_names` e `attachment_names` in CTE separate prima di ricomporre le conversazioni, cosi evita il join moltiplicativo tra messaggi, entita e allegati; aggiunta regressione su conversazione con piu entita e allegati, quality checks completi verdi (`122 passed`).
- Note ultimo ciclo: 2026-07-11: `workspace_study.py` ora usa una sequenza di `topic_id` allineata a `rows` invece del dizionario `assignments`, cosi il workspace tiene un buffer in meno durante l'enriched; test mirati e quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: `attachments.csv` ora viene streamato dal cursor DB in `workspace_study.py` invece di materializzare tutta la lista; vengono trattenuti solo i record minimi per `attachment_texts.csv` quando richiesto. Quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: `study.py` ora calcola i conteggi del report da uno snapshot minimo e libera `conversation_export` prima delle fasi finali; test mirati e quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-10: `message_rows` viene liberato appena scritti i CSV dei messaggi; dopo il report vengono eliminati anche `inventory_rows`, `attachment_rows`, `enriched` e `topics`, cosi il workspace non li trattiene fino al return. Quality checks verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-10: liberati `topics_by_id`, `assignments` e `attachments_by_conversation` subito dopo `enriched`; `attachment_rows` ridotte al payload minimo per il report e `rows` rilasciato prima della classificazione. Quality checks verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-10: rimosso il buffer duplicato `attachment_report_rows`; il report usa direttamente `attachment_rows` e il workspace rilascia gli allegati solo dopo la generazione di `study_report.html`. Test mirati e quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: `analysis_text` viene tenuto solo quando `semantic_text` e vuoto, cosi il payload delle righe resta piu piccolo senza perdere il fallback necessario sui reset derivati; il test di rerun dopo reset e i quality checks completi sono verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: svuotati i campi transienti gia copiati nell'enriched workspace e rilasciati `semantic_text`/`analysis_text` dopo `_terms`, cosi il tratto finale trattiene meno payload senza cambiare CSV o report; quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: `export_study_pack` costruisce `subjects.csv` e il report finale da `conversation_export` gia condensato e libera `rows` subito dopo la derivazione, cosi il picco memoria dell'export scende senza cambiare i file prodotti; quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: dopo gli export intermedi `enriched`, `attachment_rows` e `topics` vengono ridotti ai soli campi ancora richiesti da report e contatori finali, cosi il payload residente cala senza cambiare CSV o report; test mirati e quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: `input_inventory.csv` viene contato con un helper leggero e `inventory_rows` viene rilasciato subito dopo la scrittura; il report legge il conteggio dal CSV esistente anche sui rerun, cosi il workspace resta corretto senza trattenere l'inventario fino al return. Test mirato sul rerun e quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: il workspace precompila i contatori del report e libera `enriched` subito dopo i CSV delle conversazioni, cosi il tratto finale non trattiene piu il payload di report durante allegati/topic/classification; test mirato e quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: `src/email_cluster/atlas/study.py` ora libera i buffer di export dopo l'ultimo uso, riduce a snapshot minimi i dati che arrivano al report e scrive `classification_workspace.csv` prima della riduzione dei candidati; quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: il report allegati usa ora `attachment_count`, `attachment_analyzed` e `attachment_status` precomputati e `attachment_rows` viene liberato prima del rendering HTML, cosi il tratto finale trattiene meno memoria senza cambiare l'output; quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: `_terms(rows)` viene calcolato subito dopo gli export topic/entity e `semantic_text`/`analysis_text` vengono liberati prima della classification workspace e del report finale, cosi il payload testuale non resta residente piu a lungo del necessario; targeted workspace tests e quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: gli allegati vengono esportati subito dopo la query e prima di `topic_discovery`; il workspace conserva solo una cache minimale di snippet per conversazione fino a `enriched`, cosi `attachment_rows` non resta residente attraverso i passi successivi. Quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: `assignments` e `attachment_contexts_by_conversation` vengono svuotati mentre si costruisce `enriched`, cosi il workspace rilascia per-conversation mapping e snippet allegati subito dopo l'uso senza cambiare CSV o report; test mirato e quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: i messaggi vengono esportati subito dopo la query e `message_rows` viene liberato prima di allegati e topic, cosi il buffer piu grande non resta residente durante il resto del workspace; quality checks completi verdi (`121 passed`).
- Note ultimo ciclo: 2026-07-11: validata la serie di ottimizzazioni gia presente in `workspace_study.py` e `conversations.py`; guard e quality checks completi verdi (`121 passed`), task ancora in_progress sul fronte memoria/streaming residuo.
- Note ultimo ciclo: 2026-07-11: `build_conversations()` ora alloca in modo lazy `message_ids` e il testo unico per le conversazioni monomessaggio, e rilascia i buffer temporanei prima del round-trip SQL; quality checks completi verdi (`121 passed`).

### EA-EPIC9-ORANGE

- Area: export-orange
- Priorita: P3
- Stato: done
- Titolo: pacchetto Orange opzionale minimale
- Descrizione: mantenere export e guida Orange senza introdurre dipendenze obbligatorie.
- File coinvolti stimati: `src/email_cluster/atlas/study.py`, `docs/orange_export.md`, `tests/*`
- Comandi da eseguire: `email-atlas export-orange --workspace <ws>`
- Test da aggiungere: export workspace Orange
- Criteri di accettazione: export opzionale e documentato
- Rischio: basso
- Dipendenze: EA-EPIC6-CLASSIFICATION-WORKSPACE
- Note ultimo ciclo: 2026-07-12: chiuso verificando l'export opzionale gia presente, il comando CLI `export-orange --workspace`, la guida dedicata e i test sui CSV/workflow; test mirati verdi e quality checks completi verdi.

### EA-EPIC10-ATLAS

- Area: final-atlas
- Priorita: P2
- Stato: done
- Titolo: costruzione Atlante finale
- Descrizione: consolidare `build-atlas`, import decisioni manuali e output finali HTML/XLSX/YAML.
- File coinvolti stimati: `src/email_cluster/atlas/workspace_study.py`, `src/email_cluster/atlas/export.py`, `tests/*`
- Comandi da eseguire: `email-atlas build-atlas --workspace <ws>`
- Test da aggiungere: validazione decisioni importate
- Criteri di accettazione: Atlante finale consistente e derivato solo da decisioni approvate
- Rischio: medio
- Dipendenze: EA-EPIC6-CLASSIFICATION-WORKSPACE
- Note ultimo ciclo: 2026-07-12: consolidata la validazione delle decisioni e degli ID candidati per l'import diretto; `build-atlas` accetta solo decisioni note e mantiene esplicito il contratto degli ID topic del workspace. Output finali CSV/JSON/YAML/HTML/XLSX verificati; quality checks verdi (`126 passed`).
