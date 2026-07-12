# Comandi Email Atlas

`EMAIL_ATLAS.bat` e consigliato per l'uso normale. Questi sono gli equivalenti PowerShell per
automazione, log e archivi grandi. Eseguili dalla cartella del progetto.

## Verifica installazione

```powershell
.\.venv\Scripts\email-atlas.exe --help
```

Se manca: `.\.venv\Scripts\python.exe -m pip install -e ".[ui,attachments]"`.

## Crea o aggiorna uno studio

```powershell
.\.venv\Scripts\email-atlas.exe study `
  --input "D:\EmailAtlas\snapshot" `
  --workspace "D:\EmailAtlas\studio" `
  --no-attachments-text
```

Per gli allegati usa `--with-attachments-text`. Il rilancio e incrementale. Filtri facoltativi:
`--date-from YYYY-MM-DD`, `--date-to YYYY-MM-DD`, `--source-folder NOME` (ripetibile),
`--limit-messages N` e `--limit-conversations N`.

## Controlla e ripara

```powershell
.\.venv\Scripts\email-atlas.exe doctor-workspace --workspace "D:\EmailAtlas\studio"
.\.venv\Scripts\email-atlas.exe repair-workspace --workspace "D:\EmailAtlas\studio"
```

Ripara solo dopo il doctor: il comando crea un backup e si ferma sulle violazioni foreign key.

## Atlante e Orange

```powershell
.\.venv\Scripts\email-atlas.exe build-atlas --workspace "D:\EmailAtlas\studio"
.\.venv\Scripts\email-atlas.exe export-orange --workspace "D:\EmailAtlas\studio"
```

## Launcher Windows

| File | Uso |
|---|---|
| `EMAIL_ATLAS.bat` | Menu principale consigliato. |
| `CREA_STUDIO.bat` | Crea o aggiorna lo studio. |
| `CONTROLLO_WORKSPACE.bat` | Diagnosi conservativa. |
| `RIPARA_WORKSPACE.bat` | Riparazione con conferma e backup. |
| `COSTRUISCI_ATLANTE.bat` | Atlante dalle decisioni revisionate. |
| `ESPORTA_ORANGE.bat` | Export Orange facoltativo. |
| `AVVIA_CONSOLE.bat` | GUI minima facoltativa. |

Il vecchio `start_gui.bat` della GUI Tkinter è conservato in `archive/windows-launchers/` e non
fa parte dei comandi operativi correnti.

I comandi `email-cluster` restano disponibili per workflow precedenti, ricerca e clustering, ma
non sono necessari per un nuovo studio Email Atlas.
