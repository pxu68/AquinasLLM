from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.embeddings.types import EmbeddingResult


@runtime_checkable
class EmbeddingClient(Protocol):
    """Provider-independent embedding API (query vs document split)."""

    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def version_label(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> EmbeddingResult: ...

    def embed_query(self, text: str) -> EmbeddingResult: ...