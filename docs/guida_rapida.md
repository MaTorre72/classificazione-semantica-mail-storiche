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
# Controlli operativi

Procedi una fase alla volta dalla GUI e apri il report prodotto. Prima della discovery verifica che il numero di conversazioni sia plausibile, che i fallback non uniscano pratiche diverse e che la ricerca trovi termini noti. In caso di errore conserva database e sorgenti, correggi il prerequisito indicato e ripeti solo la fase interessata. Consulta `primi_passi.md` per il percorso completo e `troubleshooting.md` per il recupero.
# Nuovo percorso consigliato

Avvia `AVVIA_CONSOLE.bat` e usa le quattro sezioni dello Studio Workbench. Per prima cosa genera `outputs/study_pack`, poi leggi `study_report.html`. Se serve un'esplorazione visuale più ricca, genera l'Orange Pack. Solo dopo modifica `classification_workspace.csv` e importa le righe approvate per ottenere l'Atlante finale.

La ricerca e un supporto dentro Esplora Risultati, non una fase obbligatoria. Assistente locale e strumenti precedenti sono in Avanzate / Legacy.
