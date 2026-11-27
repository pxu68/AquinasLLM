from __future__ import annotations

import json
import logging

import httpx
import pytest
from pydantic import SecretStr

from app.embeddings.providers.openai import OpenAIEmbeddingClient

_SECRET = "sk-super-secret-do-not-log"


def test_openai_repr_hides_api_key():
    client = OpenAIEmbeddingClient(
        api_key=SecretStr(_SECRET),
        model="text-embedding-3-small",
        dimension=1536,
        batch_size=10,
        timeout_s=5.0,
    )
    assert _SECRET not in repr(client)


def test_openai_auth_failure_logs_without_secret(caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.ERROR)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid"}})

    transport = httpx.MockTransport(handler)
    client = OpenAIEmbeddingClient(
        api_key=SecretStr(_SECRET),
        model="text-embedding-3-small",
        dimension=1536,
        batch_size=10,
        timeout_s=5.0,
    )

    real_client = httpx.Client

    def client_factory(**kwargs):
        kwargs.setdefault("transport", transport)
        return real_client(**kwargs)

    import app.embeddings.providers.openai as openai_mod

    openai_mod.httpx.Client = client_factory  # type: ignore[misc]
    try:
        with pytest.raises(Exception):
            client.embed_query("test")
    finally:
        openai_mod.httpx.Client = real_client  # type: ignore[misc]

    logged = " ".join(r.message for r in caplog.records)
    assert _SECRET not in logged
    dumped = json.dumps([r.message for r in caplog.records])
    assert _SECRET not in dumped