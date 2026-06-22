# Pipeline

1. Inventario read-only delle sorgenti.
2. Importazione incrementale e deduplica.
3. Parsing e pulizia versionata.
4. Ricostruzione verificabile delle Conversazioni.
5. Indice locale FTS5.
6. Entità e dizionari modificabili.
7. Documenti semantici conversation-first.
8. Rappresentazioni locali opzionali e cached.
9. Discovery di Categorie candidate.
10. Revisione umana, export ed evaluation.

Le fasi sono idempotenti dove possibile. Le tabelle legacy restano disponibili. Operazioni invasive
richiedono backup e consenso; i batch embedding supportano cache, batch e `--low-power`.
# Contratto delle fasi

Ogni fase legge i risultati della precedente e produce dati nel database o un report, senza modificare EML/MBOX. Inventario misura; parsing estrae e pulisce; conversazioni collega con header e fallback prudente; indice abilita la ricerca; entita e documenti semantici preparano evidenze; discovery propone categorie euristiche; revisione registra decisioni; export pubblica l'Atlante; evaluate segnala frammentazione. Gli embedding memorizzati non guidano oggi la discovery.

Un risultato tecnicamente riuscito non equivale a un risultato corretto: controlla warning, esempi di conversazioni lunghe, categorie fragili e rapporto categorie/conversazioni.
