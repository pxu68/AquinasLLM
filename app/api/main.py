from fastapi import FastAPI
from sqlalchemy import text

from app.db.session import engine

app = FastAPI(title="Aquinas AI", version="0.1.0")


@app.get("/health")
def health() -> dict:
    db_ok = False
    vector_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_ok = True
            row = conn.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            ).scalar()
            vector_ok = bool(row)
    except Exception:
        pass
    status = "ok" if db_ok and vector_ok else "degraded"
    return {
        "status": status,
        "database": db_ok,
        "pgvector": vector_ok,
    }
