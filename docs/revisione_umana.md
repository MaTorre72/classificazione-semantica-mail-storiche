# Revisione umana

`email-atlas review` elenca le Categorie candidate. Azioni disponibili: `approve`, `rename`,
`exclude`, `deprecate`, `ambiguous`, `merge`. Esempio:

```powershell
email-atlas review --db data/email_cluster.sqlite --project archivio_storico --candidate 4 --action approve --name "Gestione rifiuti"
```

Ogni decisione viene salvata in `atlas_review_decisions`. L'obiettivo è ridurre e chiarire le
Categorie, non moltiplicarle.
