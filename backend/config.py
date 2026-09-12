"""backend/config.py — Typed settings loader for VIGIL.

Uses pydantic-settings to load and validate every environment variable from
the ``.env`` file at repo root.  A single ``settings`` instance is exported
at module level and loaded once at import time.

Variable names and defaults mirror ``.env.example``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All VIGIL configuration, loaded from environment / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    SESSION_SECRET: str = ""

    # ── LLM ────────────────────────────────────────────────────────────────
    LLM_PROVIDER: Literal["ollama", "openai", "anthropic", "google", "groq"] = "ollama"
    LLM_MODEL: str = "llama3.1:8b"
    LLM_API_KEY: str = ""
    LLM_API_BASE_URL: str = ""
    OLLAMA_HOST: str = "http://localhost:11434"

    # ── Embeddings & Reranking ─────────────────────────────────────────────
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # ── ASR & STT ───────────────────────────────────────────────────────────
    ASR_MODEL: str = "small.en"
    STT_PROVIDER: str = "deepgram"
    DEEPGRAM_API_KEY: str = ""
    DEEPGRAM_MODEL: str = "nova-2"
    DEEPGRAM_LANGUAGE: str = "en"
    DEEPGRAM_API_BASE_URL: str = "https://api.deepgram.com"

    # ── Rime (voice synthesis) ─────────────────────────────────────────────
    TTS_PROVIDER: str = "rime"
    RIME_API_KEY: str = ""
    RIME_MODEL_LIVE: str = "mist-v3"
    RIME_MODEL_DEBRIEF: str = "coda"
    RIME_SPEAKER: str = "astra"
    RIME_API_BASE_URL: str = "https://users.rime.ai"


    # ── Qdrant ─────────────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_PREFIX: str = "vigil_"

    # ── SQLite ─────────────────────────────────────────────────────────────
    SQLITE_DB_PATH: str = "./backend/vigil.db"

    # ── Data simulator ─────────────────────────────────────────────────────
    SIMULATOR_MODE: str = "scripted"
    SIMULATOR_DEFAULT_SCENARIO: str = "hero_scenario"

    # ── Logging ────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "info"

    # ── Validators ─────────────────────────────────────────────────────────

    @field_validator("*", mode="before")
    @classmethod
    def _strip_inline_comments(cls, v: Any) -> Any:
        if isinstance(v, str) and "#" in v:
            return v.split("#")[0].strip()
        return v

    @field_validator("LLM_MODEL", mode="before")
    @classmethod
    def _default_llm_model_if_empty(cls, v: Any) -> Any:
        if isinstance(v, str):
            cleaned = v.split("#")[0].strip()
            if not cleaned:
                return "llama3.1:8b"
            return cleaned
        return v

    @model_validator(mode="after")
    def _require_api_key_for_hosted_providers(self) -> "Settings":
        """If ``LLM_PROVIDER`` is a hosted provider, ``LLM_API_KEY`` must be
        set — fail early with a clear message rather than deep inside a
        request handler.
        """
        if self.LLM_PROVIDER != "ollama" and not self.LLM_API_KEY:
            raise ValueError(
                "LLM_API_KEY is required when LLM_PROVIDER != 'ollama'"
            )
        return self


# Module-level singleton — loaded once at import time.
settings = Settings()


def get_settings() -> Settings:
    """Return the global Settings instance."""
    return settings

