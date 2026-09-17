# Aquinas LLM (Phase 1)

Modular monolith: PostgreSQL + pgvector, structured document ingestion, hybrid retrieval (RRF).

## Local development

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
