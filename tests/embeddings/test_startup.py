import pytest

from app.config import Settings
from app.embeddings.startup import EmbeddingStartupError, validate_embedding_startup


def test_production_refuses_deterministic_by_default():
    cfg = Settings(
        APP_ENV="production",
        EMBEDDING_PROVIDER="deterministic",
        ALLOW_DETERMINISTIC_EMBEDDINGS=False,
    )
    with pytest.raises(EmbeddingStartupError):
        validate_embedding_startup(cfg)


def test_production_allows_deterministic_when_flag_set():
    cfg = Settings(
        APP_ENV="production",
        EMBEDDING_PROVIDER="deterministic",
        ALLOW_DETERMINISTIC_EMBEDDINGS=True,
    )
    validate_embedding_startup(cfg)


def test_development_allows_deterministic():
    cfg = Settings(APP_ENV="development", EMBEDDING_PROVIDER="deterministic")
    validate_embedding_startup(cfg)