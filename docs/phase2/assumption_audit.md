# Phase 2 — Section 2 assumption audit (M8 Step 0)

Audited against the repo at M8 kickoff. Design reference: `docs/PHASE2_DESIGN.md` §2 and §14.

---

## 1. Embedding column type, dimension, and index

| Item | Finding |
|------|---------|
| **Column** | `embeddings.vector` is `vector(1536) NOT NULL` (Alembic `0002_initial_schema.py`, SQLModel `Embedding.vector` via `pgvector.sqlalchemy.Vector(1536)`). |
| **Dimension** | Fixed **1536** in schema and in `DeterministicEmbeddingClient.dimensions = 1536`. |
| **Model fields** | `embedding_model TEXT`, `embedding_version TEXT`, `is_current BOOLEAN` (no `embedding_version_id` / `embedding_versions` table yet — M9). |
| **Index** | `idx_embeddings_vector_hnsw` — **HNSW** on `vector` with **`vector_cosine_ops`**, partial **`WHERE is_current`**. Secondary index `idx_embeddings_unit` on `retrieval_unit_id`. |

**Design note (§14, M9):** Future cutover expects unconstrained `vector`, per-version partial HNSW on `embedding_version_id`, and `len(vec) == version.dimension` enforced in service. None of that is in the DB yet; M8 stays on the Phase 1 column.

---

## 2. Does `SearchResponse` expose per-leg scores?

**Yes — matches the assumption.**

- `SearchResultItem.retrieval` is `RetrievalMethodInfo` with `vector_rank`, `vector_distance`, `lexical_rank`, `lexical_score`, and `fused_score` (`app/api/schemas.py`).
- `RetrievalService` fills these from RRF fusion metadata (`app/retrieval/fusion.py`, `app/retrieval/service.py`).
- **Vector leg:** `vector_distance` is pgvector **cosine distance** (`<=>` with `vector_cosine_ops`), not a separate “cosine similarity” field.
- **Lexical leg:** rank is pool order (1…50); `lexical_score` is `ts_rank_cd`.

**Optional clarity (non-blocking):** Document in API docs that `vector_distance` is cosine distance (lower = closer). No schema change required for M8.

---

## 3. Can retrieval be scoped to a node subtree or work?

**Partial — work/author/node-type only; no subtree scope.**

| Filter | Supported? | Where |
|--------|------------|--------|
| Work (title) | Yes | `SearchRequest.works` → `work_titles` in `vector_search` / `lexical_search` |
| Author (canonical name) | Yes | `SearchRequest.authors` |
| Node type | Yes | `SearchRequest.node_types` |
| **Subtree under a `document_nodes` root** | **No** | Not on `SearchRequest` or retrieval SQL |
| Work by ID / edition scope | No | Only title string match |

**Smallest additive fix (later milestone, not M8):** Add optional `scope_node_id: UUID | None` to `SearchRequest` and both search queries — restrict units whose `primary_node_id` is the node or a descendant via recursive CTE on `document_nodes.parent_id` (nodes already have `parent_id`, `depth`, `ordinal`).

**Smallest additive fix for “work” without title ambiguity:** Optional `work_ids: list[UUID]` filter joining `works w ON w.id = ed.work_id` (parallel to existing title filter).

---

## 4. `node_relationships` objection ↔ reply and locator convention

**Matches the assumption.**

**Relationships (Summa ingestion):**

- Reply → objection: `relationship_type = "replies_to"` (`source_node_id` = reply section, `target_node_id` = objection section).
- Inverse: `relationship_type = "objects_to"` (objection → reply).
- Parsed in `app/parsing/summa.py`; persisted via `CorpusRepository.persist_tree`; validated in `app/ingestion/validation.py`.

**Locator convention:**

- Stored on `document_nodes.canonical_reference` (human-readable string, not a separate locator table).
- Summa pattern (`app/parsing/summa.py`, `_canonical`):
  - Part: `ST {I|II|…}`
  - Question: `ST I, q.{n}`
  - Article: `ST I, q.{n}, a.{m}`
  - Section suffixes: `obj. {n}`, `ad {n}`, `sed contra`, `respondeo`
- Example: `ST I, q.9, a.1, obj. 1`

**No deviation** for Phase 2 analysis/selection that resolves locations via regex + DB lookup on `canonical_reference`.

---

## 5. Sessions and repositories: sync or async?

**Synchronous — matches the assumption.**

- `app/db/session.py`: sync `create_engine`, `sessionmaker`, generator `get_session()`.
- `CorpusRepository` and routes use `sqlalchemy.orm.Session` directly (sync `session.execute`, `session.query`, commits in ingestion).
- No `AsyncSession` / async FastAPI DB deps in the codebase.

---

## Deviations from design assumptions and M8 target state

| # | Topic | Assumption / M8 target | Current repo | Smallest additive fix |
|---|--------|------------------------|--------------|------------------------|
| A | Subtree retrieval | Scoped retrieval for `source_faithful` | Not implemented | Optional `scope_node_id` + recursive CTE in `vector_search` / `lexical_search` + `SearchRequest` field (post-M8 retrieval milestone). |
| B | Embedding API | `Protocol`: `embed_documents` / `embed_query` → `EmbeddingResult` | ABC + single `embed_texts()` | Replace/refactor `app/embeddings/client.py` per M8 spec; keep backward-compatible wrapper or update call sites (`RetrievalService` uses query path). |
| C | Provider layout | `providers/deterministic.py`, `providers/openai.py`, `registry.py` | Monolithic `client.py` with `DeterministicEmbeddingClient` only | Add provider modules + registry; move hash logic to `deterministic.py` (byte-identical output). |
| D | Settings | `EMBEDDING_*`, `APP_ENV`, `ALLOW_DETERMINISTIC_EMBEDDINGS`, secrets as `SecretStr` | `Settings` only has `database_url` | Extend `app/config.py` + `.env.example` (M8). |
| E | `EmbeddingService` | `(client, version)` with batching, dim check, error mapping | `(repo, client)` calling `embed_texts` with no batching/dim guard | Refactor service per M8; ingestion passes version metadata from client/registry. |
| F | Active embedding version | DB state (`embedding_versions`, pin per request) | String pair on `embeddings` row + `is_current`; no versions table | **M9** migration + retrieval pin; M8 does not add migrations. |
| G | Startup guard | Refuse deterministic **active version** in production | No guard; no `embedding_versions` | M8: guard on **configured provider** (`EMBEDDING_PROVIDER=deterministic`) when `APP_ENV=production` unless `ALLOW_DETERMINISTIC_EMBEDDINGS=true`; extend to DB active row in M9. |
| H | Query vs document embed | Mandatory split for asymmetric providers | Query path uses same `embed_texts([query])` as documents | Route retrieval through `embed_query`, ingestion through `embed_documents` (deterministic may delegate to same impl). |
| I | Index / column (§14 long-term) | Unconstrained vector + per-version HNSW | Fixed `vector(1536)` + `is_current` partial index | **M9** Alembic; out of scope for M8. |
| J | Degraded lexical-only search | Query embed failure → lexical-only, `degraded=true` | Vector embed always attempted; no degraded flag on search API | Additive retrieval/RAG gateway work (post-M8); not required to pass Phase 1 suite. |
| K | Version pinning on search | Pin active embedding version per request | Join `embeddings … AND emb.is_current` only | **M9** + optional retrieval parameter; M8 ingestion still writes `is_current` rows via existing `upsert_embedding`. |

---

## M8 implementation readiness summary

- **Assumptions §2.1, 2.2, 2.4, 2.5:** Satisfied as-is.
- **Assumption §2.3:** Not satisfied; fix is additive retrieval scope (defer until after M8 embedding layer unless explicitly pulled forward).
- **§14 embedding layer:** Substantially **not** implemented; partial stubs (`client.py`, minimal `service.py`) need full M8 deliverables without changing retrieval algorithms, parsing, or corpus.

**Next step (after review):** Implement M8 embedding abstraction, providers, registry, service, config, startup guard, ingestion wiring, and contract tests — no DB migrations.
