"""
Central configuration, read from environment variables and the project's `.env` file.

Every value can be overridden with an environment variable of the same name
(case-insensitive), e.g. `MAX_PLAYERS=10` or `LLM_MODEL=gemma3:1b`.
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

    # --- Local language model (Ollama) -------------------------------------
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "gemma3:4b"
    llm_temperature: float = Field(0.8, ge=0.0, le=2.0)
    llm_max_tokens: Optional[int] = Field(256, ge=1)   # longest answer
    llm_num_ctx: int = Field(4096, ge=512)             # context window in tokens
    llm_keep_alive: str = "30m"                        # how long the model stays loaded
    llm_timeout: float = Field(120.0, gt=0)            # seconds per answer

    # --- Game -------------------------------------------------------------
    default_players: int = Field(8, ge=1)
    min_players: int = Field(4, ge=1)
    max_players: int = Field(12, ge=1)
    discussion_max_rounds: int = Field(5, ge=1)
    memory_messages: int = Field(4, ge=0)          # past messages kept per player
    discussion_context_messages: int = Field(10, ge=0)  # discussion lines shown in a prompt
    conversation_token_budget: int = Field(1200, ge=100)  # most tokens of conversation in one prompt

    # Show every player's role in the API (debug / spectator). Off: roles are
    # only visible for eliminated players.
    reveal_roles: bool = False

    # Several games can run at once; idle ones are removed
    max_sessions: int = Field(20, ge=1)
    session_ttl_minutes: float = Field(120, gt=0)

    # --- Server -----------------------------------------------------------
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache
def get_settings() -> Settings:
    """Shared settings instance (read once per process)"""
    return Settings()
