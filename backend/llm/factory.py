"""Build the LLM client from the settings"""
from functools import lru_cache

from backend.config import get_settings
from backend.llm.ollama_client import OllamaClient


@lru_cache
def create_llm_client() -> OllamaClient:
    """
    The Ollama client described by the settings.

    It is created once and shared by every game, because there is one model on
    one machine.
    """
    settings = get_settings()
    return OllamaClient(
        settings.ollama_host, settings.llm_model,
        temperature=settings.llm_temperature, max_tokens=settings.llm_max_tokens,
        num_ctx=settings.llm_num_ctx, keep_alive=settings.llm_keep_alive,
        timeout=settings.llm_timeout,
    )
