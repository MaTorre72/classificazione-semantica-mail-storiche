# Aggiornamento periodico

```powershell
email-atlas update --input mail --db data/email_cluster.sqlite --project archivio_storico
```

L'update importa solo messaggi nuovi, riusa la deduplica, aggiorna pulizia, Conversazioni, indice,
entità, documenti e proposte. Gli embedding hanno cache separata e vengono calcolati solo quando
cambia l'impronta del documento. Le Categorie approvate non vengono cancellate.
# Procedura consigliata

1. Esegui il backup del database.
2. Aggiungi i nuovi file senza rinominare quelli già acquisiti.
3. Esegui inventario e confronta i conteggi.
4. Avvia aggiornamento, poi verifica errori di parsing e nuove conversazioni.
5. Revisiona solo le nuove proposte e riesporta l'Atlante.

Duplicati e file invariati devono risultare saltati. Se i conteggi calano o cambiano in modo inatteso, interrompi la revisione e confronta inventario e backup.
