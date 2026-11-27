from __future__ import annotations

import uuid

from app.embeddings.client import EmbeddingClient
from app.embeddings.errors import DimensionMismatchError, EmbeddingError
from app.embeddings.types import EmbeddingResult, EmbeddingVersionInfo
from app.repositories.corpus import CorpusRepository


class EmbeddingService:
    def __init__(
        self,
        client: EmbeddingClient,
        version: EmbeddingVersionInfo,
        *,
        batch_size: int = 100,
    ) -> None:
        self._client = client
        self._version = version
        self._batch_size = max(1, batch_size)

    @property
    def version(self) -> EmbeddingVersionInfo:
        return self._version

    @property
    def client(self) -> EmbeddingClient:
        return self._client

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            try:
                result = self._client.embed_documents(batch)
            except EmbeddingError:
                raise
            except Exception as exc:
                raise EmbeddingError(str(exc)) from exc
            self._validate_result(result, expected_count=len(batch))
            vectors.extend(result.vectors)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        try:
            result = self._client.embed_query(text)
        except EmbeddingError:
            raise
        except Exception as exc:
            raise EmbeddingError(str(exc)) from exc
        self._validate_result(result, expected_count=1)
        return result.vectors[0]

    def embed_retrieval_units(
        self,
        repo: CorpusRepository,
        unit_ids: list[uuid.UUID],
        texts: list[str],
    ) -> None:
        vectors = self.embed_documents(texts)
        for uid, vec in zip(unit_ids, vectors, strict=True):
            repo.upsert_embedding(
                uid,
                self._version.model,
                self._version.version,
                vec,
            )

    def _validate_result(self, result: EmbeddingResult, *, expected_count: int) -> None:
        if len(result.vectors) != expected_count:
            raise EmbeddingError(
                f"expected {expected_count} vectors, provider returned {len(result.vectors)}"
            )
        if result.dimension != self._version.dimension:
            raise DimensionMismatchError(self._version.dimension, result.dimension)
        for vec in result.vectors:
            if len(vec) != self._version.dimension:
                raise DimensionMismatchError(self._version.dimension, len(vec))