# UI V4: console locale di classificazione assistita

## Decisione architetturale

La GUI Tkinter resta disponibile per compatibilità, ma non è adatta a dashboard, wizard, filtri,
spiegazioni progressive e pannelli decisionali. La nuova UI usa FastAPI, Jinja2 e JavaScript minimo
in stile HTMX, senza SPA e senza risorse esterne. Il server ascolta soltanto `127.0.0.1` per default.

## Principi UX

Ogni pagina indica posizione, lavoro già svolto, decisioni mancanti, intervento umano richiesto,
prossima azione e conseguenza dei pulsanti. Metriche UMAP/HDBSCAN sono collassate nei dettagli tecnici.

## Struttura

- `/`: dashboard, workflow e una sola prossima azione.
- `/wizard`: percorso in sei passi con skip esplicito.
- `/llm`: backend locale, rilevamento Ollama, modelli installati e test.
- `/macro`: macro-categorie, anomalie e correzioni rapide.
- `/contexts`: board filtrabile dei contesti operativi.
- `/contexts/{id}`: decisione, spiegazione, email sospette e pannello LLM.
- `/emails/{id}`: comprensione del sistema, testo, thread, allegati e decisione umana.
- `/taxonomy`: vista macro → cliente → dominio → contesto.
- `/export`: controllo qualità ed export locale.

## Componenti

Badge di stato/confidenza, pannello prossima azione, card contesto, tabella email, pannello LLM,
barra decisioni, warning, dettagli tecnici collassabili, albero tassonomia e progress stepper sono
macro Jinja riutilizzabili.

## Sicurezza

Nessun CDN, font remoto, analytics o telemetria. Ollama è interrogato solo su localhost. Nessun
modello viene scaricato. Le azioni distruttive non sono esposte. Tutte le correzioni usano i servizi
non distruttivi V3.1 e restano tracciate in SQLite.

## Dipendenze

Extra opzionale `ui`: FastAPI e Uvicorn. Jinja2 è già disponibile come dipendenza transitiva, ma viene
dichiarato esplicitamente nell'extra. CLI e pipeline restano utilizzabili senza UI.

## Smoke test

1. `email-cluster ui --project archivio_storico --db data/email_cluster.sqlite`
2. Aprire `http://127.0.0.1:8765`.
3. Verificare dashboard e wizard.
4. Aprire macro, contesti e un dettaglio.
5. Approvare/rinominare un contesto di test.
6. Verificare LLM disabilitato e rilevamento Ollama non raggiungibile.
7. Aprire export e generare report HTML/CSV.
