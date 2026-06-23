# Orange Export Pack

Genera il pack con:

```powershell
email-atlas export-orange --db data/email_cluster.sqlite --project archivio_storico --output outputs/orange_pack
```

Apri `orange_conversations.csv` nel widget **File**. Usa x/y e conteggi come feature; testo, oggetto, dominio, ambito e warning come meta. Collega **Scatter Plot**, **Distributions**, **Box Plot**, **Data Table** e **Hierarchical Clustering**.

Per il testo usa il Text add-on con `semantic_text_short`. Per la rete importa `orange_nodes.csv` e `orange_edges.csv` nel Network add-on; gli stessi file funzionano in Gephi e Cytoscape.

Le coordinate possono derivare da embedding o dal fallback TF-IDF + PCA. La colonna/metadato del metodo evita di confondere una proiezione esplorativa con una verita semantica.
