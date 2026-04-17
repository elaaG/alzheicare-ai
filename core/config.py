from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    groq_api_key: str
    groq_chat_model: str = "llama-3.3-70b-versatile"
    groq_stt_model: str = "whisper-large-v3"
    groq_tts_model: str = "canopylabs/orpheus-v1-english"
    groq_tts_voice: str = "diana"
   

    openrouter_api_key: str = ""          
    tavily_api_key: str = ""              

    redis_url: str = "redis://localhost:6379"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    internal_api_key: str = ""

    app_env: str = "development"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    rate_limit_per_minute: int = 20
    rate_limit_burst: int = 5

    max_audio_size_mb: int = 25
    max_history_messages: int = 20
    max_tokens: int = 800
    temperature: float = 0.4
    request_timeout_seconds: int = 30
    rag_enabled: bool = True
    rag_docs_path: str = "knowledge_base"
    rag_top_k: int = 4
    rag_chunk_size: int = 900
    rag_chunk_overlap: int = 150

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"app_env must be one of {allowed}")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def search_enabled(self) -> bool:
        return bool(self.tavily_api_key)

    @property
    def fallback_enabled(self) -> bool:
        return bool(self.openrouter_api_key)

    model_config = {"env_file": ".env", "case_sensitive": False}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
