from __future__ import annotations

from app.config import Settings, settings
from app.embeddings.client import EmbeddingClient
from app.embeddings.providers.deterministic import DeterministicEmbeddingClient
from app.embeddings.providers.openai import OpenAIEmbeddingClient
from app.embeddings.service import EmbeddingService
from app.embeddings.startup import validate_embedding_startup
from app.embeddings.types import EmbeddingVersionInfo


def version_info_from_client(client: EmbeddingClient) -> EmbeddingVersionInfo:
    return EmbeddingVersionInfo(
        provider=client.provider,
        model=client.model,
        version=client.version_label,
        dimension=client.dimension,
    )


def build_embedding_client(cfg: Settings | None = None) -> EmbeddingClient:
    cfg = cfg or settings
    provider = cfg.embedding_provider.lower()
    if provider == "deterministic":
        return DeterministicEmbeddingClient(dimension=cfg.embedding_dimension)
    if provider == "openai":
        key = cfg.embedding_api_key
        if key is None:
            raise ValueError("EMBEDDING_API_KEY is required when EMBEDDING_PROVIDER=openai")
        return OpenAIEmbeddingClient(
            api_key=key,
            model=cfg.embedding_model,
            dimension=cfg.embedding_dimension,
            batch_size=cfg.embedding_batch_size,
            timeout_s=cfg.embedding_timeout_s,
        )
    raise ValueError(f"Unknown EMBEDDING_PROVIDER: {provider!r}")


def build_embedding_service(cfg: Settings | None = None) -> EmbeddingService:
    cfg = cfg or settings
    client = build_embedding_client(cfg)
    version = version_info_from_client(client)
    return EmbeddingService(client, version, batch_size=cfg.embedding_batch_size)


def ensure_embedding_startup(cfg: Settings | None = None) -> None:
    cfg = cfg or settings
    validate_embedding_startup(cfg)