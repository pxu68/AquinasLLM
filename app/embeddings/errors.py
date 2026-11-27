from __future__ import annotations


class EmbeddingError(Exception):
    """Base class for embedding failures."""


class DimensionMismatchError(EmbeddingError):
    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(f"expected dimension {expected}, got {actual}")
        self.expected = expected
        self.actual = actual


class TransientEmbeddingError(EmbeddingError):
    """Retryable provider failure (timeout, 5xx, 429)."""


class PermanentEmbeddingError(EmbeddingError):
    """Non-retryable provider failure (auth, bad request)."""