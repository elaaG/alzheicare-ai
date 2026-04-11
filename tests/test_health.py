import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture(scope="function")
async def client():
    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


class TestHealth:

    @pytest.mark.asyncio
    async def test_ping_always_200(self, client):
        response = await client.get("/health/ping")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_has_required_fields(self, client):
        response = await client.get("/health")
        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "environment" in data
        assert "dependencies" in data

    @pytest.mark.asyncio
    async def test_health_dependencies_structure(self, client):
        response = await client.get("/health")
        data = response.json()
        deps = data.get("dependencies", {})
        # These four must always be present
        for dep in ["groq", "redis", "tavily", "fallback"]:
            assert dep in deps, f"Missing dependency: {dep}"
            assert "status" in deps[dep]

    @pytest.mark.asyncio
    async def test_health_correlation_id_in_response(self, client):
        response = await client.get(
            "/health/ping",
            headers={"X-Correlation-ID": "test-abc-123"},
        )
        assert response.headers.get("X-Correlation-ID") == "test-abc-123"