# Tuning del clustering

## Stato attuale

Il comando `cluster` legge l'embedding piu' recente collegato alla versione piu' recente di
`clean_texts`, richiede `excluded_from_main_clustering = 0` e usa `semantic_text` per le etichette.
Gli embedding vengono normalizzati, ridotti con UMAP e clusterizzati con HDBSCAN. Assegnazioni,
probabilita', rumore, keyword, rappresentanti e coerenza sono salvati in SQLite.

## Limiti trovati

- La selezione non verifica esplicitamente soglia minima, `message_type` e modello richiesto.
- I parametri sono singoli blocchi globali; non esistono profili nominati o sweep.
- Le run non salvano metriche globali, warning, profilo, esclusioni a monte o random state.
- Il report non distingue esclusioni preprocessing e rumore HDBSCAN.
- Il labeling usa solo TF-IDF del testo, senza oggetti, mittenti, domini o confidence.
- Non esiste un confronto ordinato tra run e le metriche classiche non sono contestualizzate.

## Piano di modifica

1. Introdurre profili `conservative`, `balanced`, `exploratory` e una griglia sweep limitata.
2. Rendere espliciti modello, tipi ammessi e soglia nella query degli embedding.
3. Separare motore, diagnostica e labeling in moduli testabili.
4. Estendere `clustering_runs` e `clusters` con migrazioni additive SQLite.
5. Aggiungere `cluster-sweep`, `compare-runs` e `clustering-report`.
6. Calcolare warning e metriche come indicatori diagnostici, non punteggi assoluti.

## Nuovi comandi CLI

- `cluster --profile balanced`: esegue una singola configurazione nominata.
- `cluster-sweep --project NOME`: salva piu' run per combinazioni della griglia configurata.
- `compare-runs --project NOME`: ordina e confronta metriche e warning delle run.
- `clustering-report --run-id ID`: mostra parametri, metriche, distribuzione e rumore.

## Nuovi campi DB

`clustering_runs` riceve profilo, conteggi, rapporti, statistiche dimensione, metriche sklearn,
probabilita', assegnazioni a bassa confidenza, esclusioni a monte, random state e warning JSON.
`clusters` riceve oggetti ricorrenti, mittenti/domini ricorrenti, probabilita' media e confidence
dell'etichetta. Le colonne sono aggiunte in modo idempotente ai database esistenti.

## Rischi

- Silhouette, Davies-Bouldin e Calinski-Harabasz dipendono dallo spazio ridotto e non definiscono da
  sole la qualita' semantica.
- Sweep troppo ampi possono essere costosi; il numero di combinazioni sara' limitato.
- Cluster piccoli aumentano specificita' ma anche rumore; i warning renderanno visibile il compromesso.

## Test e criteri di successo

I test copriranno selezione input, uso di `semantic_text`, persistenza metriche, warning dominante e
rumore, rappresentanti, labeling e creazione/confronto di piu' run. Sul campione reale il sistema
deve produrre run ripetibili, distinguere esclusioni e rumore, evitare macrocluster non segnalati e
offrire etichette piu' specifiche e confrontabili.
