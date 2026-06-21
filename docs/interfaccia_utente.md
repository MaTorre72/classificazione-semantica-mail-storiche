# Console locale V4

La console web è il percorso consigliato per usare il progetto dopo l'importazione.

```powershell
email-cluster ui --project archivio_storico --db data/email_cluster.sqlite
```

Si apre su `http://127.0.0.1:8765`. Il server ascolta solo sul computer locale, non invia dati
all'esterno e non modifica i file MBOX/EML sorgente.

## Flusso normale

1. **Panoramica** mostra una sola prossima azione utile e lo stato dei sei passaggi.
2. **Macro-categorie** permette di intercettare posta personale, automatica o anomala prima della
   classificazione professionale.
3. **Contesti operativi** è la coda principale: ogni elemento rappresenta una pratica, un cliente o
   un tema coerente.
4. Nel **dettaglio contesto** si approva, rinomina o chiede una proposta al LLM locale.
5. Nel **dettaglio email** si corregge la macro-categoria, si sposta o si esclude il messaggio.
6. **Esportazione** mostra i controlli qualità prima di creare il report HTML o il dataset CSV.

Le decisioni umane sono registrate nel database. Le run tecniche originali restano disponibili per
diagnosi e confronto.

## Avvio controllato

Per non aprire automaticamente il browser:

```powershell
email-cluster ui --project archivio_storico --db data/email_cluster.sqlite --no-open-browser
```

L'opzione `--host` può esporre la console in rete, ma non è consigliata perché l'applicazione non
implementa autenticazione. Il valore predefinito sicuro è `127.0.0.1`.
