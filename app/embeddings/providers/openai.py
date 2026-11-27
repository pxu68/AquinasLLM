from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx
from pydantic import SecretStr

from app.embeddings.errors import PermanentEmbeddingError, TransientEmbeddingError
from app.embeddings.types import EmbeddingResult, EmbeddingUsage

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_BASE_S = 0.5


class OpenAIEmbeddingClient:
    def __init__(
        self,
        *,
        api_key: SecretStr,
        model: str,
        dimension: int,
        batch_size: int,
        timeout_s: float,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._batch_size = max(1, batch_size)
        self._timeout_s = timeout_s
        self._base_url = base_url.rstrip("/")

    @property
    def provider(self) -> str:
        return "openai"

    @property
    def model(self) -> str:
        return self._model

    @property
    def version_label(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    def __repr__(self) -> str:
        return f"OpenAIEmbeddingClient(model={self._model!r}, dimension={self._dimension})"

    def embed_documents(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[],
                model=self._model,
                dimension=self._dimension,
                usage=None,
            )
        all_vectors: list[list[float]] = []
        usage_total: EmbeddingUsage | None = None
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            result = self._embed_inputs(batch)
            all_vectors.extend(result.vectors)
            usage_total = _merge_usage(usage_total, result.usage)
        return EmbeddingResult(
            vectors=all_vectors,
            model=self._model,
            dimension=self._dimension,
            usage=usage_total,
        )

    def embed_query(self, text: str) -> EmbeddingResult:
        return self._embed_inputs(text)

    def _embed_inputs(self, inputs: list[str] | str) -> EmbeddingResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "input": inputs,
            "dimensions": self._dimension,
        }
        data = self._request_json("POST", "/embeddings", payload)
        items = sorted(data["data"], key=lambda row: row["index"])
        vectors = [row["embedding"] for row in items]
        for vec in vectors:
            if len(vec) != self._dimension:
                raise PermanentEmbeddingError(
                    f"provider returned dimension {len(vec)}, expected {self._dimension}"
                )
        usage_raw = data.get("usage") or {}
        usage = EmbeddingUsage(
            prompt_tokens=usage_raw.get("prompt_tokens"),
            total_tokens=usage_raw.get("total_tokens"),
        )
        return EmbeddingResult(
            vectors=vectors,
            model=data.get("model", self._model),
            dimension=self._dimension,
            usage=usage,
        )

    def _request_json(self, method: str, path: str, json_body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                with httpx.Client(timeout=self._timeout_s) as client:
                    response = client.request(method, url, headers=headers, json=json_body)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt >= _MAX_ATTEMPTS:
                    raise TransientEmbeddingError(str(exc)) from exc
                self._sleep_backoff(attempt, None)
                continue

            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt >= _MAX_ATTEMPTS:
                    raise TransientEmbeddingError(
                        f"OpenAI embeddings HTTP {response.status_code}"
                    )
                retry_after = response.headers.get("Retry-After")
                self._sleep_backoff(attempt, retry_after)
                continue

            if response.status_code in {401, 403}:
                logger.error(
                    "openai_embeddings_auth_failed status=%s",
                    response.status_code,
                )
                raise PermanentEmbeddingError(
                    f"OpenAI embeddings HTTP {response.status_code}"
                )

            if response.status_code >= 400:
                logger.error(
                    "openai_embeddings_request_failed status=%s",
                    response.status_code,
                )
                raise PermanentEmbeddingError(
                    f"OpenAI embeddings HTTP {response.status_code}"
                )

            return response.json()

        raise TransientEmbeddingError(str(last_exc or "embedding request failed"))

    def _sleep_backoff(self, attempt: int, retry_after: str | None) -> None:
        if retry_after is not None:
            try:
                time.sleep(min(float(retry_after), 30.0))
                return
            except ValueError:
                pass
        delay = _BACKOFF_BASE_S * (2 ** (attempt - 1)) + random.uniform(0, 0.25)
        time.sleep(delay)


def _merge_usage(
    left: EmbeddingUsage | None, right: EmbeddingUsage | None
) -> EmbeddingUsage | None:
    if left is None:
        return right
    if right is None:
        return left
    pt = (left.prompt_tokens or 0) + (right.prompt_tokens or 0)
    tt = (left.total_tokens or 0) + (right.total_tokens or 0)
    return EmbeddingUsage(prompt_tokens=pt or None, total_tokens=tt or None)