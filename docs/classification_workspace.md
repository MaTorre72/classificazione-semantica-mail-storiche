# Classification Workspace

`classification_workspace.csv` e la tabella di lavoro tra esplorazione e Atlante finale. Ogni riga contiene proposta, motivazione, esempi, segnali e campi decisionali.

## Compilazione

Imposta `human_decision` a `approve` solo per categorie supportate dagli esempi. Compila `final_name`, `final_scope`, `final_theme`, `final_description` e `notes`. Lascia vuote le righe non decise; non vengono importate.

Conserva intestazioni e formato CSV UTF-8. Puoi modificarlo in Excel, LibreOffice o Orange. L'import e riavviabile:

```powershell
email-atlas import-classification --db data/email_cluster.sqlite --project archivio_storico --file outputs/study_pack/classification_workspace.csv
```
