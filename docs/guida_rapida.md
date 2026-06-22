# Guida rapida

## Che cosa fa

Email Atlas legge archivi locali, ricostruisce Conversazioni, rende l'Archivio ricercabile e aiuta
a costruire un Atlante di Categorie revisionate. Non sposta messaggi, non sostituisce Thunderbird,
non è un CRM e non invia dati fuori dal computer.

## Percorso completo

```powershell
email-atlas inventory --input mail --db data/email_cluster.sqlite --project archivio_storico
email-atlas parse --db data/email_cluster.sqlite --project archivio_storico
email-atlas build-conversations --db data/email_cluster.sqlite --project archivio_storico --account studio@example.it
email-atlas index --db data/email_cluster.sqlite --project archivio_storico
email-atlas extract-entities --db data/email_cluster.sqlite --project archivio_storico
email-atlas build-semantic-docs --db data/email_cluster.sqlite --project archivio_storico
email-atlas discover --db data/email_cluster.sqlite --project archivio_storico
email-atlas review --db data/email_cluster.sqlite --project archivio_storico
email-atlas export-atlas --db data/email_cluster.sqlite --project archivio_storico --output data/atlas
email-atlas evaluate --db data/email_cluster.sqlite --project archivio_storico
```

Prima dell'importazione usa `inventory`: mostra cosa contiene la sorgente senza classificarla. La
revisione trasforma proposte automatiche in Categorie dell'Atlante. Il LLM è sempre opzionale.

Per una dimostrazione isolata: `email-atlas smoke-test`.
