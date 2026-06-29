# Studio di uno snapshot Thunderbird/MBOX

Non usare il profilo Thunderbird attivo. Chiudi Thunderbird, copia in una cartella separata i file MBOX utili (Inbox, Sent/Posta inviata, archivi e cartelle locali) e usa quella copia come snapshot immutabile.

```powershell
email-atlas study --input "D:\snapshot_mail" --workspace "D:\studio_email"
```

I file `.msf`, cache e indici sono ignorati. I file MBOX possono avere estensione `.mbox`/`.mbx` oppure nessuna estensione. La posta inviata viene riconosciuta dai percorsi Sent/Posta inviata e serve a costruire conversazioni miste; se manca, il report segnala un risultato fragile.

## Opzioni

- `--stages list` elenca gli stage.
- `--resume/--no-resume` controlla il riuso di `state.json`.
- `--rebuild-stage build_conversations` ricostruisce i derivati con backup.
- `--no-attachments-text` censisce soltanto i metadati.
- `--with-attachments-text --max-attachment-mb 20` abilita estrazione locale limitata.
- `--embedding-provider none` mantiene il fallback locale senza embedding.

Il workspace contiene database, stato, log, dataset CSV, topic, rete, report HTML e `classification_workspace.csv`. Tutto resta sul computer.

## Revisione e Atlante

Compila `human_decision` con `approve`, `rename`, `merge`, `exclude`, `unclear` o `split_later`. Per rename e merge indica `final_name`.

```powershell
email-atlas build-atlas --workspace "D:\studio_email"
email-atlas export-orange --workspace "D:\studio_email"
```

Il primo comando produce `atlas_final.xlsx`, YAML e HTML. Orange è opzionale e riceve copie dedicate di conversazioni, topic, entità e rete.
