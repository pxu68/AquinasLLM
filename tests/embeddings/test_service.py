from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.embeddings.errors import DimensionMismatchError
from app.embeddings.service import EmbeddingService
from app.embeddings.types import EmbeddingResult, EmbeddingUsage, EmbeddingVersionInfo


@dataclass
class _FakeClient:
    provider: str = "fake"
    model: str = "fake-model"
    version_label: str = "fake-v1"
    dimension: int = 1536
    bad_length: bool = False

    def embed_documents(self, texts: list[str]) -> EmbeddingResult:
        dim = 100 if self.bad_length else self.dimension
        return EmbeddingResult(
            vectors=[[0.0] * dim for _ in texts],
            model=self.model,
            dimension=dim,
            usage=None,
        )

    def embed_query(self, text: str) -> EmbeddingResult:
        return self.embed_documents([text])


def test_service_dimension_mismatch_raises():
    version = EmbeddingVersionInfo("fake", "fake-model", "fake-v1", 1536)
    service = EmbeddingService(_FakeClient(bad_length=True), version)
    with pytest.raises(DimensionMismatchError):
        service.embed_documents(["hello"])