# Aquinas AI — Phase 0 & Phase 1 Summary

This document summarizes what was built in the **Aquinas AI** repository through **Phase 0** (platform skeleton) and **Phase 1** (corpus platform and retrieval foundation), aligned with the Phase 1 design brief: structured texts in PostgreSQL, ingestion with provenance, and hybrid search that returns **evidence passages only** (no generated answers / RAG answers deferred to a later phase).

---

## Architectural stance

| Decision | Choice |
|----------|--------|
| Topology | **Modular monolith** (single deploy, clear module boundaries) |
| Database | **PostgreSQL 16** + **pgvector** + full-text search |
| Structure | Generic **`document_nodes`** tree + **`node_relationships`** (e.g. objection↔reply) |
| Retrieval units | **`retrieval_units`** decoupled from canonical tree (one or more nodes per unit) |
| Embeddings | Versioned rows on **`retrieval_units`**; Phase 1 uses **deterministic hash vectors** for tests |
| Hybrid ranking | **Reciprocal Rank Fusion (RRF)** over vector + lexical rank lists |
| Ingestion | **Immutable ingestion runs**; atomic **`is_current`** cutover on success |
| ORM | **SQLModel** + repositories; hand-tuned SQL for search |
| Operator ingest | **CLI only** in Phase 1 (no `POST /v1/ingest`) |

Module rule: only **`app/repositories/`** talks to the database session for persistence; parsing never touches SQL.

---

## Phase 0 — Project skeleton (Milestone 0)

**Goal:** Runnable Postgres + pgvector, FastAPI health check, Alembic configured.

### Delivered

- **`docker-compose.yml`** — `db` (pgvector/pgvector:pg16) and `app` (FastAPI)
- **`Dockerfile`** — Python 3.12, installs package with dev deps, runs migrations on start
- **`docker-entrypoint.sh`** — `alembic upgrade head` then `uvicorn` (CRLF-safe for Windows builds via `sed` in Dockerfile)
- **`.gitattributes`** — `*.sh` line endings LF for Linux containers
- **`pyproject.toml`** — FastAPI, SQLModel, Alembic, psycopg, pgvector, pytest stack
- **`app/api/main.py`** — `GET /health` (database + `vector` extension checks)
- **`app/db/session.py`**, **`app/config.py`** — `DATABASE_URL` via env / defaults
- **Alembic** — `alembic/env.py`, `0001_extensions_only.py` (`vector`, `pg_trgm`)
- **`tests/test_health.py`** — optional integration test when `AQUINAS_TEST_DB=1`
- **`README.md`** — local Docker and venv setup

### Acceptance (Phase 0)

- `docker compose up` brings up Postgres with pgvector available
- `GET /health` → `status: ok`, `database: true`, `pgvector: true` (after migrations)
- `alembic upgrade head` succeeds on a clean database

### Operational notes discovered in Phase 0

- **`/health` degraded with `pgvector: false`** until migrations run (extensions not created in DB yet)
- **App container exit** on Windows if entrypoint script had CRLF — fixed in Dockerfile/`.gitattributes`
- **Only `db` running** → nothing on port 8000; need `docker compose up` (or `-d app`) for the API

---

## Phase 1 — Corpus platform & retrieval foundation (Milestones 1–7)

### Milestone 1 — Core schema

**Migration:** `alembic/versions/0002_initial_schema.py`

**Tables (high level):**

- Catalog: `authors`, `works`, `editions`, `source_documents`
- Ingestion: `ingestion_runs` (Postgres enum `ingestion_status`)
- Structure: `document_nodes`, `node_relationships`
- Retrieval: `retrieval_units`, `retrieval_unit_members`, `embeddings`
- Taxonomy (Phase 4–ready, unused in pipeline): `concepts`, `retrieval_unit_concepts`

**ORM:** `app/models/entities.py` — SQLModel models; `IngestionStatus` mapped to Postgres enum **by value** (`active`, not `ACTIVE`).

**Design details implemented:**

- Generated **FTS** columns on `document_nodes.text` and `retrieval_units.unit_text` (English config)
- Partial unique indexes: one **active** ingestion run per source; unique **canonical_reference** among **current** nodes per edition
- HNSW index on embeddings (`vector(1536)`) for cosine search

**Tests:** `tests/db/test_schema.py` — duplicate current canonical reference fails at DB.

---

### Milestone 2 — Parser interface + Summa parser

**Files:** `app/parsing/base.py`, `models.py`, `summa.py`, `treatise.py`

- **`Parser` ABC** → in-memory **`StructuredDocument`** (typed nodes + relationship drafts)
- **`SummaParser`** — golden **JSON** format (TEI/XML deferred); ST I, Q9, Articles 1–2 excerpt
- **`TreatiseParser`** — work root + chapters (*De Ente et Essentia* excerpt)

**Golden data:**

- `data/golden/st_i_q9_excerpt.json`
- `data/golden/dee_excerpt.json`

**Tests:** `tests/parsing/test_summa_parser.py` — 11 nodes, canonical refs, objection↔reply links.

**Parser fix:** Section **sibling ordinals** are unique per article (sequential 1…n); logical objection/reply numbers still drive canonical strings (`obj. 1`, `ad 1`).

---

### Milestone 3 — Ingestion pipeline (parse → validate → persist → activate)

**Files:** `app/ingestion/pipeline.py`, `validation.py`, `cli.py`, `retrieval_units.py`, `app/repositories/corpus.py`

**Flow:**

1. Resolve or create author → work → edition → source document (checksum-addressed raw archive under `data/raw/`)
2. Skip if same checksum already has an **active** run (idempotent re-run)
3. Parse → **validate** → persist nodes + relationships (`is_current=false`)
4. Build retrieval units → embeddings → **activate** run (flip `is_current`, supersede prior active run)

**CLI:**

```text
python -m app.ingestion.cli ingest --source ... --parser summa|treatise ...
```

**Validation rules:** parent/ordinal integrity, unique canonical refs in document, retrievable leaf text length, at least one retrievable leaf, objection/reply relationship warnings.

**Tests:** `tests/ingestion/test_pipeline.py` — idempotency, `--force` re-ingest, malformed corpus fails without activation.

**Fix:** Supersede old active run **`flush()`** before marking new run `active` (partial unique index on active run per source).

---

### Milestone 4 — Retrieval units + embeddings

- One **retrieval unit** per **retrievable leaf** (typically each Summa section with text)
- **`DeterministicEmbeddingClient`** — 1536-dim unit vectors from text hash (no external API in Phase 1)
- **`EmbeddingService`** — upsert keyed by `(retrieval_unit_id, model, version)`

**Production note:** Swap in a real `EmbeddingClient` (OpenAI, Voyage, etc.) when moving beyond test embeddings.

---

### Milestone 5 — Hybrid retrieval + search API

**Files:** `app/retrieval/vector_search.py`, `lexical_search.py`, `fusion.py`, `service.py`, `app/api/routes/search.py`

- Vector: pgvector `<=>` with metadata filters
- Lexical: `websearch_to_tsquery` + `ts_rank_cd` on `retrieval_units.fts`
- **RRF** (`k=60`) merges rank lists in Python
- **`POST /v1/search`** — returns passages + `RetrievalMethodInfo` + **provenance** (no synthesized answer)

**Tests:** `tests/retrieval/test_search.py`, `test_fusion.py`

---

### Milestone 6 — Read APIs + provenance

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | DB + pgvector status |
| POST | `/v1/search` | Hybrid search |
| GET | `/v1/passages/{id}` | Single retrieval unit + provenance |
| GET | `/v1/passages/{id}/context` | Ancestor chain (recursive CTE) |
| GET | `/v1/works` | List works |
| GET | `/v1/works/{id}` | Work + editions |
| GET | `/v1/ingestion-runs/{id}` | Run status + validation report |

**Schemas:** `app/api/schemas.py`

---

### Milestone 7 — Second genre on same schema

- Same database schema ingests **Summa** and **treatise** excerpts with no migration
- Genre-specific shape lives in **parsers** and `node_type` / `section_role` values, not separate tables

---

## Repository layout (after Phase 1)

```text
aquinas_ai/
├── app/
│   ├── api/              # FastAPI routes + Pydantic schemas
│   ├── corpus/           # (read services folded into repositories + routes)
│   ├── db/               # session, deps, Alembic
│   ├── embeddings/       # client + service
│   ├── ingestion/        # pipeline, validation, CLI
│   ├── models/           # SQLModel entities
│   ├── parsing/          # Parser ABC, Summa, Treatise
│   ├── repositories/     # all DB writes/reads
│   └── retrieval/        # vector, lexical, RRF, orchestration
├── alembic/versions/     # 0001 extensions, 0002 full schema
├── data/golden/          # hand-verified ingest fixtures
├── docs/
│   ├── PHASE1_TESTING.md
│   └── PHASE0_PHASE1_SUMMARY.md  (this file)
├── tests/                # unit + integration (Postgres)
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## Testing & quality

**Procedure:** [PHASE1_TESTING.md](./PHASE1_TESTING.md)

**Integration tests** require:

```powershell
$env:AQUINAS_TEST_DB = "1"
$env:DATABASE_URL = "postgresql+psycopg://aquinas:aquinas@localhost:5432/aquinas"
python -m pytest tests -v
```

**Current suite (10 tests):** health, schema constraint, parser, ingestion idempotency/re-ingest/failure, RRF, hybrid search + work filter.

**Test infrastructure:** `tests/conftest.py` — session-scoped `alembic upgrade head` via `python -m alembic`; per-test nested savepoints so ingestion commits roll back.

**ORM note:** `fts` generated columns are **not** mapped on SQLModel entities (avoids insert into generated columns).

---

## Issues fixed during implementation

| Symptom | Cause | Resolution |
|---------|--------|------------|
| `invalid enum ingestion_status: "ACTIVE"` | SQLAlchemy sent enum **name** not **value** | `SAEnum` with `values_callable` on `IngestionRun.status` |
| `cannot insert into column "fts"` | ORM included generated column | Removed `fts` from DocumentNode / RetrievalUnit models |
| Ingest validation failed on golden Summa | Duplicate section ordinals under one article | Sequential `tree_ord` per article in `SummaParser` |
| Re-ingest unique violation on active run | Old run still `active` when new run set `active` | `flush()` after supersede, before activate |
| `/health` degraded | Extensions not applied | Run Alembic; entrypoint runs migrations on container start |
| App container crash on Windows | CRLF in `docker-entrypoint.sh` | `sed` strip `\r`; invoke via `/bin/sh` |

---

## Explicitly out of scope (Phase 1)

- RAG / LLM-generated answers from `/v1/search`
- HTTP-triggered ingestion (`POST /v1/ingest`)
- Real embedding API (production model) wired by default
- TEI-XML / production Summa source parsers (golden JSON only)
- Latin FTS config (English `to_tsvector` on all editions; Latin leans on vector path)
- Populated **concepts** taxonomy (tables exist; pipeline does not fill them)
- Celery/queue-based ingestion (synchronous CLI + state machine)

---

## Suggested next steps (Phase 2+)

1. Wire a production **embedding provider** and re-embed corpus with versioned cutover.
2. Add **TEI or edition-specific parsers** for full *Summa* / *De Ente* works.
3. Latin (or multilingual) **FTS regconfig** per edition.
4. **RAG layer** consuming `/v1/search` evidence with strict citation boundaries.
5. **Concept tagging** and cross-author **citation** relationships (`node_relationships.cites`, etc.).

---

## Related documents

- Phase 1 design brief (original): user-provided `aquinas-ai-phase1-design.md`
- How to verify: [PHASE1_TESTING.md](./PHASE1_TESTING.md)
- Quick start: [README.md](../README.md)
