# Revisione umana assistita

## Perché serve

Il clustering raggruppa testi simili, ma non conosce clienti, pratiche e priorità professionali. La V3
usa quindi i cluster come bozze: l'utente approva o corregge, e il sistema conserva la decisione senza
riscrivere la run originale.

Il LLM locale può proporre label, sintesi e cluster misti. Non approva, non sposta email e non crea una
verità definitiva. È opzionale e non invia dati fuori dal computer.

## Workflow consigliato

```powershell
email-cluster run --input mail --project archivio_storico --db data/email_cluster.sqlite
email-cluster review-start --project archivio_storico --run latest --db data/email_cluster.sqlite
email-cluster llm-label-clusters --project archivio_storico --run latest --db data/email_cluster.sqlite
email-cluster review-dashboard --session 1 --db data/email_cluster.sqlite
email-cluster review-next --session 1 --db data/email_cluster.sqlite
```

Se il LLM è disabilitato, il terzo comando produce fallback/errori tracciati e tutto il resto funziona.

## Revisionare cluster

```powershell
email-cluster review-cluster --session 1 --cluster 3 --db data/email_cluster.sqlite
email-cluster approve-cluster --session 1 --cluster 3 --db data/email_cluster.sqlite
email-cluster rename-cluster --session 1 --cluster 3 --label "Emissioni e camini" --db data/email_cluster.sqlite
email-cluster mark-cluster-mixed --session 1 --cluster 3 --db data/email_cluster.sqlite
email-cluster mark-cluster-split --session 1 --cluster 3 --db data/email_cluster.sqlite
email-cluster merge-clusters --session 1 --clusters 3,7 --label "Pratica AUA" --db data/email_cluster.sqlite
```

Split e merge sono decisioni di revisione, non modifiche distruttive alla run.

## Revisionare email e tassonomia

```powershell
email-cluster move-email --session 1 --email-id 123 --to-cluster 7 --db data/email_cluster.sqlite
email-cluster exclude-email --session 1 --email-id 123 --reason "Notifica personale" --db data/email_cluster.sqlite
email-cluster add-taxonomy-label --project archivio_storico --label "Emissioni" --type tema_tecnico --db data/email_cluster.sqlite
email-cluster add-label-example --label "Emissioni" --email-id 123 --type positive --db data/email_cluster.sqlite
email-cluster add-label-rule --project archivio_storico --label "Emissioni" --type sender_domain --pattern tenax.it --db data/email_cluster.sqlite
```

Esempi positivi/negativi alimentano suggerimenti per similarità; le regole restano leggibili e
modificabili. Nessun training pesante viene eseguito.

## LLM locale

`llm-check` verifica configurazione e backend. Ollama è accettato esclusivamente su localhost;
llama.cpp richiede un GGUF locale. Output e errori sono salvati in cache e validati. Per questa
installazione il LLM è disabilitato finché non viene autorizzata installazione/configurazione.

## UI ed export

```powershell
email-cluster review-ui --project archivio_storico --db data/email_cluster.sqlite
email-cluster final-classification-report --session 1 --output data/output/final.html --db data/email_cluster.sqlite
email-cluster export-final-dataset --session 1 --format csv --output data/output/final.csv --db data/email_cluster.sqlite
```

La GUI permette dashboard, prossimo elemento, dettaglio cluster, approvazione, rinomina, cluster misto,
tassonomia ed export. Il dataset finale mantiene separati cluster automatico, proposta LLM e decisione
umana.
