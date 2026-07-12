# Classificazione

La classificazione segue quattro livelli: **Area -> Classe -> Insieme -> Email**.

La pagina **Classificazione** permette di creare, rinominare e disattivare Aree; creare Classi dentro
le Aree; creare e spostare Insiemi; aprire le singole Email. Etichette e Regole restano strumenti
avanzati e non sono livelli della struttura principale.

Una Regola cerca un valore in mittente, oggetto, testo o allegato e assegna un'Area, un'Etichetta o
un Cliente / Ente. Prima dell'applicazione viene mostrato il numero di email interessate. Soltanto
dopo conferma la Regola modifica la classificazione.

Le decisioni umane restano nel database SQLite e non modificano i file sorgente.
