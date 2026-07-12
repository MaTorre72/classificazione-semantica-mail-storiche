# Consolidamento UX: classificazione e LLM locale

La superficie principale segue sempre il percorso **Area -> Insieme -> Email**. I nomi tecnici
restano nel database e negli strumenti avanzati, ma non sono necessari per controllare il lavoro.

## Modello visibile

- **Area**: categoria generale delle email.
- **Insieme**: email che parlano dello stesso argomento o pratica.
- **Etichetta**: parola o categoria applicata a email e Insiemi.
- **Argomento**: tema principale trattato.
- **Stato**: indica se una decisione deve essere controllata o è confermata.

La pagina **Classificazione** concentra Aree, Insiemi, Etichette e Regole. Le modifiche sono
reversibili o disattivabili e una regola mostra sempre il numero di email interessate prima
dell'applicazione.

## Onboarding LLM

Il percorso Ollama separa stato, istruzioni, rilevamento, scelta e test. Nessun modello viene
scaricato automaticamente. Un download parte soltanto dopo un secondo consenso esplicito e il LLM
diventa attivo solo dopo un test riuscito.
