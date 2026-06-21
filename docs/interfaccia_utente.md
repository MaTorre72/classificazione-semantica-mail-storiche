# Console locale

Avvia la console con un doppio clic su `AVVIA_CONSOLE.bat`, oppure:

```powershell
email-cluster ui --project archivio_storico --db data/email_cluster.sqlite
```

Si apre su `http://127.0.0.1:8765`. Il server resta sul computer locale e non modifica MBOX o EML.

## Percorso normale

1. **Panoramica** indica la prossima azione utile.
2. **Aree** separa posta professionale, personale e automatica.
3. **Insiemi** raccoglie email sullo stesso argomento, cliente o pratica.
4. **Classificazione** gestisce Aree, Insiemi, Etichette e Regole.
5. Nel dettaglio di un Insieme puoi confermare, rinominare o chiedere aiuto al LLM.
6. **Esportazione** controlla gli elementi ancora da verificare prima di creare HTML o CSV.

Le Regole mostrano sempre quante email modificheranno e richiedono conferma.
