# LLM locale

Il LLM è un assistente opzionale. La pipeline, la revisione e l'esportazione funzionano anche quando
è disattivato.

La pagina **LLM locale** verifica Ollama su `http://127.0.0.1:11434`, elenca i modelli già presenti e
salva la scelta in `config/default.yaml`. Non scarica né installa modelli.

Le risposte sono validate rispetto a uno schema strutturato. Una proposta non viene applicata finché
l'utente non la conferma nel dettaglio del contesto. La configurazione raccomandata mantiene
`mode: suggestions_only`.

Per sicurezza sono accettati endpoint Ollama su `localhost` o `127.0.0.1`. Testi delle email e
allegati non vengono inviati a servizi cloud.
