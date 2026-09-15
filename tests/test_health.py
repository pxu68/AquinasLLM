import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app

requires_db = pytest.mark.skipif(
    os.getenv("AQUINAS_TEST_DB") != "1",
    reason="Set AQUINAS_TEST_DB=1 with Postgres running to run integration test",
)


@requires_db
@pytest.mark.asyncio
async def test_health_ok():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] is True
    assert body["pgvector"] is True
