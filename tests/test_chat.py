import pytest
import json
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def dev_headers():
    return {
        "X-Dev-Bypass": "true",
        "Content-Type": "application/json",
    }


@pytest.fixture(scope="function")
async def client():
    from main import app
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c



class TestChatStream:

    @pytest.mark.asyncio
    async def test_stream_returns_sse_response(self, client, dev_headers):
        response = await client.post(
            "/chat/stream",
            headers=dev_headers,
            json={"message": "Qu'est-ce que la maladie d'Alzheimer?"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_stream_contains_done_signal(self, client, dev_headers):
        response = await client.post(
            "/chat/stream",
            headers=dev_headers,
            json={"message": "Bonjour"},
        )
        assert "[DONE]" in response.text

    @pytest.mark.asyncio
    async def test_empty_message_rejected(self, client, dev_headers):
        for bad_message in ["", "   ", "\n\n"]:
            response = await client.post(
                "/chat/stream",
                headers=dev_headers,
                json={"message": bad_message},
            )
            assert response.status_code in (422, 400), \
                f"Expected 4xx for message '{repr(bad_message)}', got {response.status_code}"

    @pytest.mark.asyncio
    async def test_no_auth_rejected(self, client):
        response = await client.post(
            "/chat/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_message_too_long_truncated(self, client, dev_headers):
        long_message = "A" * 3000
        response = await client.post(
            "/chat/stream",
            headers=dev_headers,
            json={"message": long_message},
        )
        assert response.status_code == 200



class TestChatSync:

    @pytest.mark.asyncio
    async def test_sync_returns_reply(self, client, dev_headers):
        response = await client.post(
            "/chat",
            headers=dev_headers,
            json={"message": "Qu'est-ce que le stade modéré?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert len(data["reply"]) > 0

    @pytest.mark.asyncio
    async def test_sync_used_search_field(self, client, dev_headers):
        response = await client.post(
            "/chat",
            headers=dev_headers,
            json={"message": "Quels sont les derniers traitements approuvés?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "used_search" in data
        assert isinstance(data["used_search"], bool)



class TestChatHistory:

    @pytest.mark.asyncio
    async def test_clear_history_endpoint(self, client, dev_headers):
        response = await client.delete(
            "/chat/history",
            headers=dev_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data



class TestValidation:

    @pytest.mark.asyncio
    async def test_missing_message_field(self, client, dev_headers):
        response = await client.post(
            "/chat",
            headers=dev_headers,
            json={},  
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_error_response_has_correlation_id(self, client):
        response = await client.post(
            "/chat",
            json={"message": "test"},  
        )
        data = response.json()
        assert "correlation_id" in data