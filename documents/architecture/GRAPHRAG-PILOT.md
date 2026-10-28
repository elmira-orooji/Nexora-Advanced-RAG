# GraphRAG pilot

Nexora's existing vector and BM25 retrieval remains the default. The optional
graph path adds organization-scoped entities and relations extracted from
document chunks. It is designed for a measured pilot, not as a replacement for
the current retriever.

## Enable the feature

1. Approve the additional model processing and indexing cost. Graph extraction
   sends chunk text to the configured language model when a document is indexed.
2. Set `GRAPH_RAG_ENABLED=true` in the backend environment.
3. Run `alembic upgrade head` from `backend`.
4. Start the API and document worker. New uploads and connector updates will
   build graph facts after ordinary indexing succeeds.
5. For already indexed documents, run `python -m scripts.reindex_graph` from
   `backend`. To limit the backfill to one organization, pass
   `--organization-id <organization UUID>`.

If graph extraction fails, vector/BM25 retrieval remains available. The extractor
accepts a relation only when it includes an exact supporting excerpt from one of
the supplied chunks. Queries return source chunks, never graph statements alone.

## Compare against the baseline

Open a knowledge set's Retriever comparison and use the same query and document
scope in both configurations. Leave GraphRAG off in one variant and enable it in
the other. Start with questions that explicitly ask about relationships,
dependencies, effects, comparisons, or connections across documents. Include
ordinary single-fact questions as controls.

For each variant, inspect the retrieved source chunks, citations, answer
faithfulness, latency, and usage cost. Record results in a small set of real
organization questions with their expected relevant chunk IDs. Keep graph
augmentation enabled only if it improves evidence recall and answer quality
without an unacceptable increase in latency, cost, or unsupported relations.

## Scope and safeguards

- Entities are keyed by organization; facts retain the exact source chunk that
  supports them.
- Retrieval filters evidence to the already-authorized active document IDs and
  checks organization scope again in the database query.
- Graph lookup is limited to one or two relationship hops, with two as the
  default.
- If a graph query fails, the request falls back to the existing hybrid results.
- Existing document text, vector search, reranking, and citation generation stay
  in place.
