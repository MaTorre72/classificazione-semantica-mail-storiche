# Console locale

Avvia la console con un doppio clic su `AVVIA_CONSOLE.bat`, oppure:

```powershell
email-cluster ui --project archivio_storico --db data/email_cluster.sqlite
```

Si apre su `http://127.0.0.1:8765`. Il server resta sul computer locale e non modifica MBOX o EML.

## Percorso normale

1. **Panoramica** indica la prossima azione utile.
2. **Aree** separa posta professionale, personale e automatica.
3. **Classificazione** organizza sempre Area → Classe → Insieme → Email.
4. **Insiemi** raccoglie email sulla stessa attività, cliente o pratica.
5. Nel dettaglio di un Insieme puoi confermare, rinominare o chiedere aiuto al LLM.
6. **Esportazione** controlla gli elementi ancora da verificare prima di creare HTML o CSV.

La pagina **Archivio email** permette di scansionare e aggiornare la cartella senza terminale. Il
percorso guidato offre pulsanti reali per ogni fase e indica quando il sistema aspetta una decisione.
