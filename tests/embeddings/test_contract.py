from __future__ import annotations

import json

import httpx
import pytest
from pydantic import SecretStr

from app.embeddings.client import EmbeddingClient
from app.embeddings.providers.deterministic import DeterministicEmbeddingClient
from app.embeddings.providers.openai import OpenAIEmbeddingClient


def _assert_client_contract(client: EmbeddingClient) -> None:
    assert client.provider
    assert client.model
    assert client.version_label
    assert client.dimension > 0

    doc = client.embed_documents(["alpha", "beta"])
    assert len(doc.vectors) == 2
    assert doc.dimension == client.dimension
    for vec in doc.vectors:
        assert len(vec) == client.dimension

    qry = client.embed_query("alpha")
    assert len(qry.vectors) == 1
    assert len(qry.vectors[0]) == client.dimension


def test_deterministic_contract():
    _assert_client_contract(DeterministicEmbeddingClient())


def test_openai_contract_uses_mocked_http():
    captured_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_auth.append(request.headers.get("authorization", ""))
        body = json.loads(request.content.decode())
        inputs = body["input"]
        if isinstance(inputs, str):
            inputs = [inputs]
        data = [
            {"index": i, "embedding": [0.01] * 1536}
            for i, _ in enumerate(inputs)
        ]
        return httpx.Response(
            200,
            json={
                "data": data,
                "model": "text-embedding-3-small",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    import app.embeddings.providers.openai as openai_mod

    real_client = httpx.Client

    def client_factory(**kwargs):
        kwargs.setdefault("transport", httpx.MockTransport(handler))
        return real_client(**kwargs)

    client = OpenAIEmbeddingClient(
        api_key=SecretStr("sk-test-secret-key-12345"),
        model="text-embedding-3-small",
        dimension=1536,
        batch_size=100,
        timeout_s=5.0,
    )
    openai_mod.httpx.Client = client_factory  # type: ignore[misc]
    try:
        _assert_client_contract(client)
    finally:
        openai_mod.httpx.Client = real_client  # type: ignore[misc]

    assert captured_auth
    assert "sk-test-secret-key-12345" in captured_auth[0]


@pytest.mark.parametrize("provider", ["deterministic", "openai"])
def test_registry_builds_provider(provider: str, monkeypatch: pytest.MonkeyPatch):
    if provider == "openai":
        monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
        monkeypatch.setenv("EMBEDDING_API_KEY", "sk-test")
        monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode())
            inputs = body["input"]
            if isinstance(inputs, str):
                inputs = [inputs]
            data = [
                {"index": i, "embedding": [0.0] * 1536}
                for i, _ in enumerate(inputs)
            ]
            return httpx.Response(200, json={"data": data, "model": body["model"]})

        import httpx as httpx_mod

        real_client = httpx_mod.Client

        def client_factory(**kwargs):
            kwargs.setdefault("transport", httpx_mod.MockTransport(handler))
            return real_client(**kwargs)

        monkeypatch.setattr(
            "app.embeddings.providers.openai.httpx.Client",
            client_factory,
        )
    else:
        monkeypatch.setenv("EMBEDDING_PROVIDER", "deterministic")

    from app.config import Settings
    from app.embeddings.registry import build_embedding_client

    cfg = Settings()
    built = build_embedding_client(cfg)
    _assert_client_contract(built)