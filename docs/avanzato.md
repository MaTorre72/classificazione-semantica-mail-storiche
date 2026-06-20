# Comandi avanzati

Questi comandi restano disponibili per sviluppo, tuning e diagnosi, ma non servono nel workflow normale.

## Pipeline e debug

`init-db`, `import`, `clean`, `prepare-context`, `embed`, `cluster`, `cluster-sweep`, `compare-runs`,
`reset-stage`, `status`, `import-status`, `cleaning-report`, `context-report`, `attachment-report`.

## Cluster e run

`clusters`, `show-cluster`, `clustering-report`, `review-clusters`, `set-label`, `suggest-splits`,
`suggest-merges`, `apply-split`.

## Revisione V3 tecnica

`review-start`, `review-dashboard`, `review-next`, `review-cluster`, `approve-cluster`,
`rename-cluster`, `reject-cluster`, `mark-cluster-mixed`, `mark-cluster-split`, `merge-clusters`,
`move-email`, `exclude-email`, `set-email-label`.

## Tassonomia e active learning

`add-taxonomy-label`, `add-label-example`, `add-label-rule`, `suggest-from-examples`,
`apply-label-rules`.

## LLM

`llm-check`, `llm-label-clusters`, `llm-triage-emails`, `llm-suggest-taxonomy`,
`llm-review-report`. Tutti operano localmente e richiedono configurazione esplicita.

## Export tecnico

`export`, `report`, `export-review`, `export-final-dataset`, `final-classification-report`.
