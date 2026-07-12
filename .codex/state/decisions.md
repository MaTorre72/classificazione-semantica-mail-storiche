# Decisions

## 2026-06-30

- La pipeline CLI e il prodotto principale; GUI e LLM locali restano opzionali e non devono guidare il backlog.
- Gli script di sviluppo autonomo usano lock file e singolo task per run, non loop infiniti.
- L'integrazione hook nativa Codex non viene inventata: si usano script equivalenti finche la CLI reale non e verificata.
- Gli artifact di run vanno in `.codex/runs/` e devono restare separati dagli output di prodotto.
- Il primo task applicativo dopo il bootstrap e `EA-EPIC1-WORKSPACE`, prima di allegati, pulizia testo e topic.
- La schedulazione preferita e una cron automation nativa di Codex ogni 50 minuti sul workspace locale; scheduler esterni restano solo fallback manuali.
