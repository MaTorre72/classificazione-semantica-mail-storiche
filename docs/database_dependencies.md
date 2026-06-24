# Dipendenze database Email Atlas

Le connessioni applicative eseguono sempre `PRAGMA foreign_keys = ON`. Le foreign key non devono essere disattivate durante reset o rebuild.

## Dipendenze Atlas dichiarate

| Tabella figlia | Colonna | Tabella padre | Classificazione |
|---|---|---|---|
| `atlas_conversation_messages` | `conversation_id` | `atlas_conversations.id` | derivata |
| `atlas_candidate_conversations` | `conversation_id` | `atlas_conversations.id` | derivata |
| `atlas_candidate_conversations` | `candidate_id` | `atlas_candidate_categories.id` | derivata |
| `atlas_entity_mentions` | `entity_id` | `atlas_entities.id` | derivata |
| `atlas_examples` | `category_id` | `atlas_categories.id` | revisione/finale |

`atlas_semantic_documents.source_id`, `atlas_embedding_cache.semantic_document_id`, `atlas_entity_mentions.conversation_id`, `atlas_categories.candidate_id` e `atlas_examples.conversation_id` sono dipendenze logiche non tutte protette da FK nello schema versione 7. Il reset deve gestirle comunque.

## Classificazione dei dati

- **Sorgente**: `source_files`, `emails`, `attachments` e file EML/MBOX. Non vengono toccati da `rebuild-derived`.
- **Derivati ricostruibili**: conversazioni e messaggi, documenti semantici, embedding Atlas, entita e menzioni, categorie candidate e associazioni.
- **Revisioni umane**: `atlas_review_decisions` e gli esempi associati alle categorie approvate.
- **Atlante finale**: `atlas_categories` e gli output finali. Non viene cancellato da `rebuild-derived`.

## Ordine di cancellazione derivati

1. `atlas_candidate_conversations`
2. `atlas_candidate_categories`
3. `atlas_embedding_cache` per i documenti del progetto
4. `atlas_semantic_documents`
5. `atlas_entity_mentions`
6. `atlas_entities`
7. `atlas_conversation_messages`
8. `atlas_conversations`

`atlas_review_decisions`, `atlas_examples` e `atlas_categories` vengono cancellati solo da `reset-project` dopo conferma esplicita e backup.

## Reset completo

`reset-project` elimina prima ogni figlio collegato a sessioni, email, cluster, contesti, tassonomie e sorgenti; elimina il record `projects` soltanto alla fine. Il backup SQLite viene creato prima dell'inizio della transazione distruttiva.
