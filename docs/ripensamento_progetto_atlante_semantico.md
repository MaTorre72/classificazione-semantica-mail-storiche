# Ripensamento del progetto: Atlante semantico

## Stato del documento

- Fase: 0, architettura e direzione progettuale.
- Data: 22 giugno 2026.
- Ambito: analisi del repository e definizione della transizione; nessuna migrazione dati eseguita.
- Frase guida: **non costruire un classificatore di email; costruire un Atlante semantico del lavoro
  reale, fondato sulle conversazioni storiche**.

## 1. Perché il modello precedente è insufficiente

Il sistema attuale ha fatto evolvere una pipeline email-first verso raggruppamenti revisionabili. È
stato utile per migliorare parsing, pulizia e controllo umano, ma il risultato resta troppo vicino
alla domanda "dove metto questa email?". Un archivio storico richiede invece di capire quali soggetti,
attività, pratiche e temi ricorrono nel lavoro reale.

I raggruppamenti tecnici sono insufficienti come prodotto finale perché:

1. dipendono dalla granularità e dai parametri di una singola elaborazione;
2. frammentano conversazioni lunghe in messaggi semanticamente poveri come "ok" o "in allegato";
3. duplicano testo citato e firme, sovrappesando espressioni ricorrenti ma poco informative;
4. confondono somiglianza lessicale, relazione operativa e appartenenza alla stessa pratica;
5. producono categorie instabili quando arrivano nuove email;
6. non documentano abbastanza criteri, esempi, esclusioni e categorie vicine;
7. spingono la UI a gestire molti elementi anziché pochi spazi di significato aggiornabili.

I raggruppamenti automatici restano uno strumento esplorativo interno. Non devono essere il
vocabolario principale né la destinazione del prodotto.

## 2. Perché la singola email non è l'unità principale

Una email contiene spesso solo un frammento dell'informazione: una richiesta senza risposta, una
risposta breve, un allegato senza spiegazione o una citazione di messaggi precedenti. Analizzarla da
sola porta a classificazioni fragili e ripetitive.

La singola email resta necessaria come prova, elemento della timeline e risultato di ricerca. Non è
però l'unità primaria per scoprire attività e categorie. Il sistema deve evitare di assegnare un
significato definitivo a ogni messaggio quando il significato emerge soltanto dal dialogo completo.

## 3. La Conversazione come unità primaria

La **Conversazione** è una sequenza ricostruita e verificabile di email ricevute e inviate. Unisce:

- relazioni esplicite da `Message-ID`, `In-Reply-To` e `References`;
- oggetto normalizzato;
- partecipanti e direzione ricevuta/inviata;
- prossimità temporale;
- testo citato e segnali di inoltro;
- allegati e loro ricorrenza.

Ogni ricostruzione deve indicare metodo, affidabilità e warning. Una relazione esplicita vale più di
un fallback per oggetto. Oggetti generici non possono da soli unire messaggi. L'utente deve poter
ispezionare timeline e motivazione e correggere fusioni o separazioni.

Il documento semantico principale sarà costruito dalla conversazione: oggetto normalizzato, parti
nuove dei messaggi in ordine temporale, partecipanti, entità, allegati e termini tecnici. I documenti
email resteranno supporto per ricerca e diagnostica.

## 4. Output finale: Atlante aggiornabile

L'**Atlante** è una raccolta revisionata di Categorie che descrivono spazi di significato. Non sposta
email e non comanda sistemi esterni. È una base di conoscenza metodologica utilizzabile in futuro da
Virgilio o altri strumenti.

Ogni Categoria dell'Atlante deve contenere:

1. Ambito;
2. Soggetto;
3. Contesto;
4. Tema operativo;
5. descrizione;
6. segnali lessicali;
7. mittenti e domini ricorrenti;
8. allegati tipici;
9. esempi reali riferiti a Conversazioni;
10. casi da escludere;
11. Categorie vicine;
12. criterio di assegnazione;
13. affidabilità;
14. stato;
15. fonte, note e ultima revisione.

Gli stati previsti sono: candidata, approvata, da rivedere, ambigua, da fondere, esclusa, deprecata
e aggiornata. Le decisioni automatiche producono solo Categorie candidate; la promozione nell'Atlante
è una decisione umana tracciata.

## 5. Cosa resta utile del codice esistente

### Importazione e deduplica

- scanner locale per EML, MBOX e file Thunderbird senza estensione;
- hash dei file sorgente e import incrementale;
- hash univoco dei messaggi;
- isolamento degli errori per sorgente e messaggio;
- conservazione dei corpi plain, HTML ed estratti.

### Parsing e pulizia

- parser MIME basato sulle librerie standard Python;
- estrazione di mittenti, destinatari, CC, BCC, date e header grezzi;
- metadati e testo degli allegati supportati;
- conversione HTML;
- cleaning versionato;
- separazione di testo corrente, citazioni, forward, firme e disclaimer;
- classificazione pragmatica dei messaggi non operativi.

### Infrastruttura locale

- SQLite e repository applicativo;
- migrazioni additive con backup preliminare;
- configurazione YAML;
- FastAPI e CLI;
- embedding locale opzionale;
- cache LLM e output Pydantic;
- revisione umana ed eventi tracciati;
- test automatici già presenti.

Questi moduli saranno adattati e incapsulati, non riscritti senza necessità.

## 6. Cosa va messo in secondo piano

- `clustering_runs`, `email_clusters` e `clusters`: strumenti di discovery e diagnostica legacy;
- `operational_contexts`: sorgente migrabile di esempi e nomi, non modello definitivo dell'Atlante;
- Aree/Classi/Insiemi della UI corrente: compatibilità temporanea, non gerarchia finale obbligatoria;
- embedding delle singole email: supporto secondario;
- GUI Tkinter e comandi orientati al tuning: modalità avanzata;
- export di classificazioni per messaggio: diagnostica, non risultato principale.

Le vecchie tabelle restano leggibili durante la transizione. Le nuove funzioni non devono dipendere
da una loro cancellazione.

## 7. Elementi da deprecare o eliminare

### Deprecazione progressiva

- il comando `email-cluster` resta disponibile per retrocompatibilità;
- i termini tecnici spariscono dalla guida base e dalla nuova CLI `email-atlas`;
- la creazione automatica di molti Insiemi non alimenta direttamente l'Atlante;
- gli export legacy vengono marcati come diagnostici;
- il LLM non viene più proposto come classificatore di ogni email.

### Nessuna eliminazione in questa fase

Non si eliminano tabelle, email, allegati, elaborazioni o file sorgente. Una futura rimozione richiederà
backup, piano di migrazione, test di ripristino e autorizzazione esplicita.

## 8. Nuova pipeline

```text
Sorgenti locali
  -> Inventario non distruttivo
  -> Importazione e parsing versionato
  -> Pulizia e segmentazione
  -> Ricostruzione Conversazioni
  -> Indice full-text
  -> Entità e dizionari
  -> Documenti semantici di Conversazione
  -> Rappresentazioni locali opzionali
  -> Discovery di Categorie candidate
  -> Assistenza LLM locale opzionale
  -> Revisione umana
  -> Atlante semantico
  -> Export e valutazione
  -> Aggiornamento incrementale
```

### Proprietà trasversali

- ogni fase ha un `job`, checkpoint e log;
- input e output hanno versione e impronta;
- una fase riparte dal checkpoint senza duplicare risultati;
- cache per elaborazioni costose;
- modalità `--low-power` per batch lunghi;
- errori isolati, misurati e riportati;
- nessun accesso di rete predefinito;
- backup prima di migrazioni o rigenerazioni invasive.

## 9. Nuovo modello dati progressivo

Il modello sarà aggiunto accanto allo schema versione 6. I nomi sono indicativi e saranno congelati
con la Fase 1/2 prima della migrazione.

### Livello sorgente e messaggio

- `atlas_sources`: sorgenti, account, cartella logica, impronte e stato inventario;
- `atlas_raw_emails`: riferimento immutabile all'email legacy o nuova importazione;
- `atlas_email_headers`: Message-ID, relazioni, partecipanti e direzione;
- `atlas_email_bodies`: testo originale e versioni parse;
- `atlas_email_parts`: segmenti new/quoted/signature/disclaimer/forward;
- `attachments`: tabella legacy riutilizzata o vista compatibile.

### Livello Conversazione

- `conversations`: identità, intervallo, metodo, affidabilità, warning e stato revisione;
- `conversation_messages`: ordine, ruolo e motivazione dell'appartenenza;
- `conversation_summaries`: sintesi versionate, locali e opzionali;
- `conversation_features`: partecipanti, entità, segnali e statistiche;
- `conversation_review_decisions`: merge, split e correzioni umane.

### Ricerca e semantica

- `search_documents` e tabella virtuale FTS5;
- `entities`, `entity_aliases`, `entity_mentions` e dizionari YAML;
- `semantic_documents`: livello email, conversation, candidate e atlas;
- `embedding_cache`: impronta documento, modello, vettore, stato e checkpoint.

### Discovery e Atlante

- `candidate_categories`: proposte ampie, non categorie finali;
- `candidate_category_conversations`: esempi e punteggi;
- `atlas_categories`: Categoria revisionata e aggiornabile;
- `atlas_examples`, `atlas_exclusions`, `atlas_near_categories`;
- `atlas_review_sessions`, `atlas_review_decisions`.

### Operazioni lunghe e sicurezza

- `processing_jobs`, `processing_checkpoints`, `processing_logs`;
- `backups` con percorso, hash, motivo e verifica;
- `external_requests` soltanto se in futuro viene autorizzato un provider cloud.

### Strategia di compatibilità

1. migrazioni additive e schema versionato;
2. backup verificato prima della prima scrittura;
3. `legacy_email_id` collega i nuovi record alle email esistenti;
4. backfill riavviabile per header e Conversazioni;
5. dual-read temporaneo, mai dual-write indefinito;
6. report di confronto prima di promuovere il nuovo percorso;
7. rollback applicativo tramite feature flag, senza cancellare nuove tabelle.

## 10. Glossario utente

| Termine | Significato |
|---|---|
| Archivio | Insieme delle sorgenti email locali analizzate |
| Email | Singolo messaggio, conservato come prova e parte di una timeline |
| Conversazione | Sequenza ricostruita di email ricevute e inviate |
| Soggetto | Persona, cliente, ente, sito o organizzazione ricorrente |
| Contesto | Pratica, attività, sito o situazione in cui avviene il lavoro |
| Tema operativo | Argomento concreto trattato nella Conversazione |
| Categoria | Spazio di significato candidato o revisionato |
| Atlante | Raccolta aggiornata delle Categorie approvate |
| Esempio | Conversazione reale che chiarisce una Categoria |
| Caso da escludere | Conversazione simile che non appartiene alla Categoria |
| Caso ambiguo | Conversazione con evidenza insufficiente o contrastante |
| Revisione | Decisione umana tracciata |
| Affidabilità | Solidità della ricostruzione o proposta, con motivazione |
| Stato | Posizione dell'elemento nel ciclo di revisione |

I termini tecnici restano nella documentazione avanzata, non nella UI o guida base.

## 11. Roadmap tecnica

### Tratto A: fondamenta verificabili

1. **Fase 1, Inventario**: nuova CLI `email-atlas`, report HTML/JSON, nessuna classificazione.
2. **Fase 2, Parsing e pulizia**: header espliciti, segmenti versionati e report qualità.
3. **Fase 3, Conversazioni**: builder deterministico, confidence, warning e revisione.
4. **Fase 4, Ricerca**: FTS5 su email e Conversazioni.
5. **Fase 5, Entità**: dizionari modificabili ed estrazione pragmatica.

### Tratto B: spazio semantico conversation-first

6. documenti semantici di Conversazione;
7. cache, checkpoint e rappresentazioni locali;
8. discovery con vincoli anti-frammentazione;
9. LLM locale come assistente opzionale;
10. revisione umana delle Categorie candidate.

### Tratto C: prodotto Atlante

11. export YAML, JSON, CSV, Markdown e HTML, incluso `--public-safe`;
12. aggiornamento incrementale;
13. valutazione quantitativa e qualitativa;
14. fixture sintetica e smoke test end-to-end;
15. documentazione utente e roadmap futura.

Ogni fase deve consegnare codice, test, report, documentazione, limiti e fase successiva. Le fasi 1-5
non richiedono LLM né nuovi algoritmi complessi.

## 12. Criteri di accettazione architetturali

La transizione è accettabile quando:

1. la Conversazione è l'unità primaria di analisi e discovery;
2. ricevute e inviate partecipano alla stessa ricostruzione quando l'evidenza lo consente;
3. ogni Conversazione espone metodo, affidabilità e warning;
4. il sistema è interrogabile via FTS5 prima della discovery;
5. le Categorie candidate favoriscono ampiezza utile e segnalano frammentazione;
6. soltanto la revisione umana promuove una Categoria nell'Atlante;
7. l'Atlante documenta esempi, esclusioni, vicinanze e criterio;
8. il sistema funziona senza LLM;
9. il LLM locale è assistente, strutturato, cached e mai decisore automatico;
10. nessun dato esce dal computer per impostazione predefinita;
11. operazioni lunghe hanno checkpoint e resume;
12. operazioni invasive hanno backup e consenso;
13. aggiornare l'archivio non richiede ricominciare da zero;
14. gli export pubblici anonimizzano esempi e riferimenti sensibili;
15. uno smoke test sintetico dimostra la pipeline completa;
16. `email-cluster` resta disponibile durante la transizione;
17. `email-atlas` diventa l'interfaccia concettuale principale;
18. il risultato è conoscenza metodologica, non un comando di archiviazione verso Virgilio.

## 13. Inventario verificato del repository al 22 giugno 2026

### Fatti verificati

- schema SQLite corrente: versione 6;
- database locale esaminato: 4 sorgenti, 475 email, 945 allegati;
- copertura temporale rilevata: 2021-2024;
- 4.700 record di cleaning e 1.425 contesti semantici, quindi più versioni per email;
- 156 raggruppamenti operativi e 688 assegnazioni;
- 23 record nella cache LLM;
- `ParsedEmail` conserva Message-ID e header grezzi;
- il repository genera `thread_key` da References/In-Reply-To o subject normalizzato;
- nel database esistente tutti i 475 `thread_key` sono nulli: serve un backfill;
- non esistono tabelle Conversazione né indice FTS5;
- `processing_runs` esiste, ma non costituisce ancora un sistema completo di checkpoint/resume;
- migrazioni e backup additivi sono già presenti;
- i test coprono parser, cleaning, contesto, revisione, export e UI, non la ricostruzione di thread.

### Interpretazione tecnica

La pipeline dispone delle informazioni grezze necessarie, ma la relazione tra email è incompleta e
non verificabile. Il backfill degli header deve precedere il conversation builder: un `thread_key`
euristico non è sufficiente come identificatore definitivo. Le elaborazioni multiple già presenti
sono utili, ma richiedono una politica esplicita di versione "corrente" nel nuovo modello.

### Rischi

- unire per solo oggetto crea falsi thread, soprattutto con oggetti generici;
- ignorare la posta inviata impoverisce attività, decisioni e timeline;
- riusare direttamente gli Insiemi legacy perpetua frammentazione e bias della vecchia pipeline;
- un backfill monolitico su archivi più grandi non è riprendibile;
- indicizzare testo citato senza deduplica altera ricerca e discovery;
- conservare esempi sensibili negli export senza modalità sicura espone dati non necessari.

### Opportunità

- gli header grezzi permettono di recuperare In-Reply-To e References senza rileggere i file sorgente;
- il cleaning segmentato consente di costruire testo unico di Conversazione senza ripetizioni;
- allegati e domini già estratti arricchiscono entità e ricerca;
- cache, backup e versioni esistenti riducono il costo della transizione;
- gli Insiemi revisionati possono diventare esempi iniziali, non verità strutturali.

## 14. Gate per la Fase 1

La Fase 1 può iniziare senza migrare lo schema principale. Deve:

- introdurre il comando `email-atlas inventory` mantenendo `email-cluster`;
- leggere sorgenti senza modificarle;
- distinguere file trovati, messaggi osservati, parseabili, duplicati probabili ed errori;
- stimare ricevute/inviate tramite account configurabili, dichiarando l'incertezza;
- produrre `reports/inventory_report.json` e `.html`;
- usare job e log riavviabili almeno a livello di file;
- non estrarre allegati in modo invasivo durante il solo inventario;
- includere test per EML, MBOX, duplicati, malformati, cartella vuota e path invalido.

Decisioni da congelare nella Fase 1: identificazione account locali, politica per profili Thunderbird,
formato stabile del report inventario e convenzione dei job. Nessuna dipendenza pesante è necessaria.
