# Aggiornamento periodico

```powershell
email-atlas update --input mail --db data/email_cluster.sqlite --project archivio_storico
```

L'update importa solo messaggi nuovi, riusa la deduplica, aggiorna pulizia, Conversazioni, indice,
entità, documenti e proposte. Gli embedding hanno cache separata e vengono calcolati solo quando
cambia l'impronta del documento. Le Categorie approvate non vengono cancellate.
