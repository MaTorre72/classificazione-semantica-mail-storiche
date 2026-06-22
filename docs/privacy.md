# Privacy e sicurezza

- Elaborazione locale e nessuna telemetria.
- Nessuna API cloud predefinita.
- Allegati mai inviati a servizi esterni.
- LLM locale opzionale e output validato.
- Nessuna modifica dei file email sorgente.
- Backup prima delle migrazioni o rigenerazioni invasive.
- Export `--public-safe` senza soggetti, contesti, mittenti o domini identificativi.

Un futuro provider cloud dovrà richiedere consenso esplicito, anonimizzare e ridurre il testo, vietare
allegati e registrare ogni richiesta. Non è implementato nella pipeline corrente.
# Procedura sicura

Lavora su una copia, limita i permessi della cartella e fai backup del database prima della revisione. Il progetto non implementa upload cloud. L'export `public-safe` passa dal modulo `atlas/privacy.py` e rimuove i principali campi identificativi, mittenti e domini; non garantisce anonimato nei testi liberi o nei nomi degli allegati. Verifica sempre il file esportato prima di condividerlo.
