# Aquinas AI (Phase 1)

Modular monolith: PostgreSQL + pgvector, structured document ingestion, hybrid retrieval (RRF).

## Local development

### Python environment (Windows)

Use a project virtualenv so dependencies are not installed into `C:\Python312` (which often fails without admin):

```powershell
cd C:\Aquinas
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:DATABASE_URL = "postgresql+psycopg://aquinas:aquinas@localhost:5432/aquinas"
```

Run the ingest CLI with the **venv active** (or prefix commands with `.\.venv\Scripts\python`).

### Docker stack

```bash
docker compose up --build
```

The app container runs `alembic upgrade head` on startup (enables `vector` + `pg_trgm`).

- API: http://localhost:8000
- Health: http://localhost:8000/health — expect `"status": "ok"` when `database` and `pgvector` are both true

Database URL (host): `postgresql+psycopg://aquinas:aquinas@localhost:5432/aquinas`

```bash
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.api.main:app --reload
```

## Phase 1 testing

See [docs/PHASE1_TESTING.md](docs/PHASE1_TESTING.md) for the full checklist, pytest commands, CLI ingest examples, and API smoke tests.

## Phase 0 & 1 summary

See [docs/PHASE0_PHASE1_SUMMARY.md](docs/PHASE0_PHASE1_SUMMARY.md) for an overview of architecture, deliverables, APIs, and known limitations.
