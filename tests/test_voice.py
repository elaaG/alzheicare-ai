import pytest


@pytest.fixture
def dummy_audio_bytes() -> bytes:
    return b"\x00" * 1024


class TestTranscribeRoute:
    @pytest.mark.asyncio
    async def test_transcribe_success(self, client, dev_headers, monkeypatch, dummy_audio_bytes):
        async def fake_transcribe(audio_bytes, filename, content_type, language):
            return "bonjour ceci est un test"

        monkeypatch.setattr("routers.transcribe.transcribe_audio", fake_transcribe)

        files = {"audio": ("sample.webm", dummy_audio_bytes, "audio/webm")}
        data = {"language": "fr"}
        response = await client.post(
            "/transcribe",
            headers={"X-Dev-Bypass": "true"},
            files=files,
            data=data,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["text"]
        assert payload["language_detected"] == "fr"

    @pytest.mark.asyncio
    async def test_transcribe_invalid_language(self, client, dummy_audio_bytes):
        files = {"audio": ("sample.webm", dummy_audio_bytes, "audio/webm")}
        data = {"language": "xx"}
        response = await client.post(
            "/transcribe",
            headers={"X-Dev-Bypass": "true"},
            files=files,
            data=data,
        )
        assert response.status_code == 422


class TestSpeakRoute:
    @pytest.mark.asyncio
    async def test_speak_returns_mpeg_audio(self, client, dev_headers, monkeypatch):
        async def fake_tts(_text: str) -> bytes:
            return b"fake-mp3-data"

        monkeypatch.setattr("routers.speak.synthesise_speech", fake_tts)

        response = await client.post(
            "/speak",
            headers=dev_headers,
            json={"text": "Bonjour le monde"},
        )
        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("audio/mpeg")
        assert "response.mp3" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_speak_requires_auth(self, client):
        response = await client.post("/speak", json={"text": "Hello"})
        assert response.status_code == 401
