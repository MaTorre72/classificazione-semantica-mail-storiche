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
