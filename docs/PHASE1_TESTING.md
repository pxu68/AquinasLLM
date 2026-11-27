# Phase 1 testing procedure

Phase 1 covers Milestones 0–7 from the design doc: schema, parsers, ingestion, embeddings, hybrid search (RRF), and read APIs.

## Prerequisites

- Docker Desktop running (recommended), **or** local PostgreSQL 16 with [pgvector](https://github.com/pgvector/pgvector)
- Python 3.11+

## 1. Start infrastructure

```powershell
cd C:\Aquinas
docker compose up --build -d
```

Verify Milestone 0:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Expect `"status": "ok"`, `"database": true`, `"pgvector": true`.

Migrations run automatically on app container start. To run manually:

```powershell
docker compose exec app alembic upgrade head
```

## 2. Install dev dependencies (host)

```powershell
cd C:\Aquinas
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:DATABASE_URL = "postgresql+psycopg://aquinas:aquinas@localhost:5432/aquinas"
```

If `pip install -e ".[dev]"` fails on system Python with `WinError 2` under `Scripts\`, use the venv above instead of global `python`.

## 3. Automated test suite

### Unit tests (no database)

```powershell
pytest tests/parsing tests/retrieval/test_fusion.py -v
```

### Integration tests (PostgreSQL required)

```powershell
$env:AQUINAS_TEST_DB = "1"
$env:DATABASE_URL = "postgresql+psycopg://aquinas:aquinas@localhost:5432/aquinas"
pytest tests -v
```

| Test module | What it verifies |
|---------------|------------------|
| `tests/test_health.py` | `/health` and pgvector |
| `tests/parsing/test_summa_parser.py` | ST I q.9 excerpt structure, references, objection↔reply |
| `tests/db/test_schema.py` | Unique `canonical_reference` among current nodes |
| `tests/ingestion/test_pipeline.py` | Idempotent ingest, force re-ingest, failed validation |
| `tests/retrieval/test_search.py` | Hybrid search + work filter |
| `tests/retrieval/test_fusion.py` | RRF scoring |

## 4. Manual ingestion (CLI)

Ingest golden Summa excerpt:

```powershell
python -m app.ingestion.cli ingest `
  --source data/golden/st_i_q9_excerpt.json `
  --parser summa `
  --author "Thomas Aquinas" `
  --author-display "St. Thomas Aquinas" `
  --work-title "Summa Theologiae" `
  --work-code ST `
  --genre summa `
  --edition-label "Golden English (test)" `
  --edition-language en `
  --translation `
  --corpus-version v0.1.0
```

Ingest treatise excerpt (second genre):

```powershell
python -m app.ingestion.cli ingest `
  --source data/golden/dee_excerpt.json `
  --parser treatise `
  --author "Thomas Aquinas" `
  --work-title "De Ente et Essentia" `
  --work-code DEE `
  --genre treatise `
  --edition-label "Golden Latin (test)" `
  --edition-language la `
  --corpus-version v0.1.0
```

Run the same command again → should print that an active ingestion already exists (idempotent).

Re-ingest with new corpus tag:

```powershell
python -m app.ingestion.cli ingest ... --force --corpus-version v0.2.0
```

## 5. Manual API checks

Search (evidence only, no generated answer):

```powershell
$body = @{ query = "Why does Aquinas think God cannot change?"; limit = 5 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/search -Body $body -ContentType "application/json"
```

Filter by work:

```powershell
$body = @{ query = "immutability"; works = @("Summa Theologiae") } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/search -Body $body -ContentType "application/json"
```

List works:

```powershell
Invoke-RestMethod http://localhost:8000/v1/works
```

Use a `retrieval_unit_id` from search results:

```powershell
Invoke-RestMethod http://localhost:8000/v1/works
Invoke-RestMethod "http://localhost:8000/v1/passages/{id}/context"
Invoke-RestMethod "http://localhost:8000/v1/ingestion-runs/{run_id}"
```

## 6. Acceptance checklist (Phase 1)

- [ ] `alembic upgrade head` on clean DB succeeds
- [ ] Golden Summa JSON parses with expected node count (11) and `ST I, q.9, a.1, respondeo`
- [ ] Duplicate ingest on unchanged checksum skips (no duplicate active tree)
- [ ] `--force` re-ingest supersedes prior run
- [ ] Invalid `{}` source fails with `ingestion_runs.status = failed`
- [ ] Every current retrievable leaf has a retrieval unit + embedding
- [ ] Search returns ST I q.9 respondeo in top 3 for immutability query
- [ ] `works` filter excludes other titles
- [ ] Passage + context + ingestion-run endpoints return provenance fields

## 7. Embeddings note

Phase 1 tests use **deterministic hash embeddings** (no external API). Production can swap in OpenAI/Voyage by implementing `EmbeddingClient` and wiring it in `IngestionPipeline` / `RetrievalService`.
