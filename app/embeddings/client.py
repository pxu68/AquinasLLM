from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod


class EmbeddingClient(ABC):
    model: str
    version: str
    dimensions: int = 1536

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


class DeterministicEmbeddingClient(EmbeddingClient):
    """Test-friendly embeddings: stable pseudo-vectors from text hash."""

    model = "deterministic-hash"
    version = "1.0.0"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._vectorize(t) for t in texts]

    def _vectorize(self, text: str) -> list[float]:
        seed = hashlib.sha256(text.encode("utf-8")).digest()
        out: list[float] = []
        i = 0
        while len(out) < self.dimensions:
            chunk = seed[i % len(seed) : (i % len(seed)) + 4]
            if len(chunk) < 4:
                chunk = (chunk + seed)[:4]
            val = int.from_bytes(chunk[:4], "big") / 2**32
            out.append(val * 2 - 1)
            i += 4
        norm = math.sqrt(sum(x * x for x in out)) or 1.0
        return [x / norm for x in out]
