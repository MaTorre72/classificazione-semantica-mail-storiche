# Guida rapida

## Il file da avviare

Fai doppio clic su **`EMAIL_ATLAS.bat`** nella cartella del progetto. E il menu principale e il
punto di ingresso consigliato.

Prepara una **copia locale** dell'archivio Thunderbird/MBOX. Non selezionare il profilo
Thunderbird attivo e non lavorare mentre Thunderbird usa quei file.

## Primo studio

1. Avvia `EMAIL_ATLAS.bat`.
2. Scegli `1. Crea o aggiorna uno studio da snapshot MBOX`.
3. Indica la cartella contenente la copia MBOX.
4. Indica un workspace diverso dalla sorgente, oppure premi Invio per `workspace_studio_email`.
5. Per una prima prova su un archivio grande rispondi `n` al testo allegati.
6. Se aggiorni un workspace già elaborato con nuove email, rispondi `s` alla ricostruzione delle
   conversazioni: viene creato prima un backup SQLite.
7. Attendi il completamento e apri `study_report.html`.

## Dal report all'Atlante

1. Controlla warning, posta inviata, conversazioni e allegati in `study_report.html`.
2. Apri `classification_workspace.csv` in Excel o LibreOffice.
3. Compila `human_decision` e, quando serve, i campi `final_*`; non rinominare le colonne.
4. Salva il CSV senza cambiarne formato o delimitatore.
5. Riapri `EMAIL_ATLAS.bat` e scegli `2. Costruisci Atlante finale`.
6. Apri `atlas_final.html` nel workspace.

## Se qualcosa non torna

Dal menu scegli prima `6. Controlla integrita workspace`. Usa `7. Ripara workspace con backup`
soltanto se il controllo lo indica. Non cancellare il database e non disattivare le foreign key.

Per i dettagli consulta la [guida completa](guida_uso_completa.md); per PowerShell consulta
[comandi](comandi.md).
