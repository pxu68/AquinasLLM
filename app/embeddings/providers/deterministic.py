from __future__ import annotations

import hashlib
import math

from app.embeddings.types import EmbeddingResult, EmbeddingUsage


def vectorize_text(text: str, *, dimension: int = 1536) -> list[float]:
    """Stable pseudo-vectors from text hash (Phase 1 algorithm, byte-identical at dim 1536)."""
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    out: list[float] = []
    i = 0
    while len(out) < dimension:
        chunk = seed[i % len(seed) : (i % len(seed)) + 4]
        if len(chunk) < 4:
            chunk = (chunk + seed)[:4]
        val = int.from_bytes(chunk[:4], "big") / 2**32
        out.append(val * 2 - 1)
        i += 4
    norm = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / norm for x in out]


class DeterministicEmbeddingClient:
    """Test-friendly embeddings: stable pseudo-vectors from text hash."""

    def __init__(self, *, dimension: int = 1536) -> None:
        if dimension != 1536:
            raise ValueError("deterministic provider only supports dimension 1536")
        self._dimension = dimension

    @property
    def provider(self) -> str:
        return "deterministic"

    @property
    def model(self) -> str:
        return "hash-1536"

    @property
    def version_label(self) -> str:
        return "test-v1"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> EmbeddingResult:
        vectors = [vectorize_text(t, dimension=self._dimension) for t in texts]
        return EmbeddingResult(
            vectors=vectors,
            model=self.model,
            dimension=self._dimension,
            usage=None,
        )

    def embed_query(self, text: str) -> EmbeddingResult:
        return EmbeddingResult(
            vectors=[vectorize_text(text, dimension=self._dimension)],
            model=self.model,
            dimension=self._dimension,
            usage=None,
        )