# Report implementazione Atlante

## Funzioni consegnate

- nuova CLI `email-atlas` compatibile con `email-cluster`;
- inventario HTML/JSON non distruttivo;
- parsing e cleaning riusando la pipeline versionata;
- ricostruzione Conversazioni con header e fallback prudente;
- FTS5 e ricerca con evidenze;
- entità basate su domini e dizionari YAML;
- documenti semantici di Conversazione;
- embedding locale cached, batch e low-power;
- discovery con limiti anti-frammentazione;
- revisione umana tracciata;
- export YAML, JSON, CSV, Markdown, HTML e modalità public-safe;
- aggiornamento incrementale;
- valutazione qualità;
- fixture sintetiche e smoke test end-to-end.

## Privacy

Nessun cloud è usato. Le sorgenti non sono modificate. LLM e embedding sono locali e opzionali.
L'export pubblico rimuove riferimenti identificativi principali.

## Limiti noti

- la direzione ricevuta/inviata richiede account espliciti per essere affidabile;
- il fallback Conversazione privilegia precisione e può lasciare thread separati;
- la discovery euristica è intenzionalmente semplice e deve essere revisionata;
- XLSX è rimandato perché opzionale e non necessario al formato base;
- FAISS/hnswlib non sono richiesti dalla prima versione: SQLite e cache restano sufficienti;
- il cloud LLM non è implementato per mantenere il default privacy-by-design.

## Verifica

La verifica automatica comprende unit test Atlante e `email-atlas smoke-test`. La suite legacy deve
restare verde per garantire compatibilità.
