"""
Central configuration, read from environment variables and the project's `.env` file.

Every value can be overridden with an environment variable of the same name
(case-insensitive), e.g. `MAX_PLAYERS=10` or `AI_PROVIDER=gemini`.
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8",
                                      extra="ignore")

    # --- AI providers -----------------------------------------------------
    ai_provider: str = "openai"
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    openai_model: str = "gpt-4"
    gemini_model: str = "gemini-2.5-pro"
    mistral_model: str = "mistral-small-latest"
    player_temperature: float = Field(0.8, ge=0.0, le=2.0)

    # --- Game -------------------------------------------------------------
    default_players: int = Field(8, ge=1)
    min_players: int = Field(4, ge=1)
    max_players: int = Field(12, ge=1)
    discussion_max_rounds: int = Field(5, ge=1)
    memory_messages: int = Field(4, ge=0)          # past messages kept per player
    discussion_context_messages: int = Field(10, ge=0)  # discussion lines shown in a prompt

    # Pauses (seconds) between LLM calls; meant for cloud rate limits
    discussion_delay: float = Field(0.3, ge=0.0)
    round_delay: float = Field(0.5, ge=0.0)
    vote_delay: float = Field(0.5, ge=0.0)
    rate_limit_delay: float = Field(1.0, ge=0.0)  # extra pause after a 429

    # Show every player's role in the API (debug / spectator). Off: roles are
    # only visible for eliminated players.
    reveal_roles: bool = False

    # Several games can run at once; idle ones are removed
    max_sessions: int = Field(20, ge=1)
    session_ttl_minutes: float = Field(120, gt=0)

    # --- Server -----------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache
def get_settings() -> Settings:
    """Shared settings instance (read once per process)"""
    return Settings()
