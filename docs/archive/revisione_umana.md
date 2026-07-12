# Revisione umana

`email-atlas review` elenca le Categorie candidate. Azioni disponibili: `approve`, `rename`,
`exclude`, `deprecate`, `ambiguous`, `merge`. Esempio:

```powershell
email-atlas review --db data/email_cluster.sqlite --project archivio_storico --candidate 4 --action approve --name "Gestione rifiuti"
```

Ogni decisione viene salvata in `atlas_review_decisions`. L'obiettivo è ridurre e chiarire le
Categorie, non moltiplicarle.
# Criteri di decisione

Approva solo categorie con nome comprensibile, evidenze coerenti e confini distinguibili. Rinomina quando il tema è corretto ma il nome è opaco; marca ambigua quando mancano prove; escludi rumore, categorie personali non pertinenti o proposte duplicate. Controlla prima categorie fragili e suggerimenti di accorpamento. Le decisioni sono tracciate nel database e la discovery non le sostituisce.
