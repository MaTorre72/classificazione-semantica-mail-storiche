# Uso del LLM

Il sistema funziona senza LLM. Ollama locale può aiutare a nominare Categorie, sintetizzare
Conversazioni e spiegare ambiguità; non decide l'Atlante e non modifica dati senza conferma.

```powershell
email-atlas llm-status
```

Risposte identiche sono cached e validate con Pydantic. Timeout, testo libero e JSON invalido sono
errori leggibili. Nessun download automatico. Il cloud non è configurato né usato.
