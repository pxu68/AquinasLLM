from __future__ import annotations

from app.config import Settings


class EmbeddingStartupError(RuntimeError):
    pass


def validate_embedding_startup(cfg: Settings) -> None:
    """Refuse deterministic embeddings in production unless explicitly allowed."""
    if cfg.app_env.lower() != "production":
        return
    if cfg.embedding_provider.lower() != "deterministic":
        return
    if cfg.allow_deterministic_embeddings:
        return
    raise EmbeddingStartupError(
        "EMBEDDING_PROVIDER=deterministic is not allowed when APP_ENV=production. "
        "Set ALLOW_DETERMINISTIC_EMBEDDINGS=true to override, or use a real provider."
    )