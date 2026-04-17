import pytest
import sys
import os
from httpx import AsyncClient, ASGITransport

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture(autouse=True)
def mock_llm(monkeypatch):
    async def fake_completion(messages):
        return "Mocked Alzheimer response"

    async def fake_stream(messages):
        yield "data: Hello "
        yield "data: world "
        yield "data: [DONE]\n\n"

    monkeypatch.setattr(
        "routers.chat.get_completion",
        fake_completion
    )

    monkeypatch.setattr(
        "routers.chat.stream_completion",
        fake_stream
    )
os.environ.setdefault("GROQ_API_KEY",    "test-groq-key-not-real")
os.environ.setdefault("JWT_SECRET",      "test-jwt-secret-for-testing-only")
os.environ.setdefault("REDIS_URL",       "redis://localhost:6379")
os.environ.setdefault("APP_ENV",         "development")
os.environ.setdefault("TAVILY_API_KEY",  "")             
os.environ.setdefault("OPENROUTER_API_KEY", "")          


@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture
def mock_groq_response():
    return "Voici une réponse de test sur la maladie d'Alzheimer."


@pytest.fixture
def sample_patient_context():
    return {
        "patient_name": "Ahmed Ben Ali",
        "patient_age": 75,
        "patient_stage": 1,
        "user_role": "caregiver",
        "user_id": "test-user-001",
    }


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