from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingUsage:
    prompt_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dimension: int
    usage: EmbeddingUsage | None = None


@dataclass(frozen=True)
class EmbeddingVersionInfo:
    """Identity written to embeddings rows until M9 version table exists."""

    provider: str
    model: str
    version: str
    dimension: int