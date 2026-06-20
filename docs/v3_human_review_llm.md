# V3: revisione umana assistita e LLM locale

## Stato attuale

La V2 dispone di import incrementale, cleaning e segmentazione persistenti, `semantic_contexts`,
embedding semantici, clustering diagnostico, allegati, explain e LLM locale opzionale. Le run sono
ripetibili e non distruttive. La revisione esistente permette però soltanto una label manuale nella
tabella `clusters` e un CSV: manca un workflow umano completo.

## Limiti e motivazione

Un cluster può essere matematicamente coerente ma operativamente misto, oppure separare email che
appartengono alla stessa pratica. Tuning e LLM non possono sostituire la conoscenza dell'utente.
Occorre distinguere sempre risultato automatico, suggerimento LLM, decisione umana e risultato finale.

## Architettura V3

La V3 aggiunge un livello sopra le run immutabili:

```text
clustering_run -> review_session -> cluster/email reviews -> final classification
                                    -> taxonomy + examples + interpretable rules
                                    -> LLM suggestions (optional, cached)
```

Nuovi moduli: `review` per sessioni, priorità, azioni ed export; `active_learning` per similarità con
esempi e regole; `llm` per client Ollama/llama.cpp, schemi Pydantic, prompt, cache e assistente review.

## Tabelle

`review_sessions`, `cluster_reviews`, `email_reviews`, `taxonomy_labels`, `label_examples`,
`label_rules`, `llm_runs`, `llm_cache`, `llm_email_suggestions`, `llm_cluster_suggestions` e
`review_suggestions`. Le revisioni non sovrascrivono assegnazioni o run precedenti.

## Comandi

Sessioni: `review-start`, `review-dashboard`, `review-cluster`, `review-next`, azioni approve/rename/
reject/mixed/split/merge, move/exclude/label email ed `export-review`.

Tassonomia: `add-taxonomy-label`, `add-label-example`, `add-label-rule`, `apply-label-rules`,
`suggest-from-examples`.

LLM: `llm-check`, `llm-label-clusters`, `llm-triage-emails`, `llm-suggest-taxonomy` e
`llm-review-report`. Senza backend disponibile i comandi terminano con fallback leggibile.

Analisi: `suggest-splits`, `suggest-merges`, `apply-split` non distruttivo, report HTML e dataset finale.

## Revisione e priorità

All'avvio vengono create review cluster pending con score maggiore per bassa coerenza/probabilità,
label debole, rumore, cluster grandi o sender eterogenei. Le email borderline ricevono priorità per
rumore, probabilità bassa e strategie thread/attachment dominant. `review-next` porta al caso più utile.

## LLM locale

Sono supportati Ollama solo su `localhost` e llama.cpp con GGUF locale. Output JSON validati con
Pydantic, un retry, cache per hash input/modello/prompt e persistenza separata. Il LLM propone, non
approva né modifica decisioni umane.

## Active learning leggero

Gli embedding delle email vengono confrontati con esempi positivi/negativi delle label tramite cosine
similarity. Regole trasparenti per sender, subject, attachment e message type possono generare
suggerimenti. Non viene addestrato alcun modello complesso.

## Migrazione e sicurezza

Schema versione 3, migrazione additiva e backup automatico autorizzato prima dell'upgrade. Nessuna run,
embedding o contesto viene rigenerato o cancellato. Non si installano backend né modelli LLM.

## Criteri e test

La V3 è accettata quando sessioni, azioni cluster/email, tassonomia, esempi, priorità, export e fallback
LLM funzionano localmente; automatico/LLM/umano restano separati; test DB, review, active learning,
cache e CLI passano con fake LLM.

## Rischi e autorizzazioni

La qualità dipende dalla revisione e dal numero di esempi. Split/merge sono suggerimenti, non modifiche
alle run. Sono autorizzati schema, backup e migrazione V3. Installazione Ollama/llama.cpp, download
modelli e rigenerazione ML restano fuori ambito e richiedono nuova autorizzazione.
