from __future__ import annotations

import uuid

from app.embeddings.client import EmbeddingClient
from app.repositories.corpus import CorpusRepository


class EmbeddingService:
    def __init__(self, repo: CorpusRepository, client: EmbeddingClient):
        self.repo = repo
        self.client = client

    def embed_retrieval_units(self, unit_ids: list[uuid.UUID], texts: list[str]) -> None:
        vectors = self.client.embed_texts(texts)
        for uid, vec in zip(unit_ids, vectors, strict=True):
            self.repo.upsert_embedding(
                uid,
                self.client.model,
                self.client.version,
                vec,
            )
