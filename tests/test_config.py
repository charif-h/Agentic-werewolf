"""Tests for the central settings."""
import pytest

from backend.config import Settings


def make(monkeypatch, **env):
    for key in ("LLM_MODEL", "OLLAMA_HOST", "MAX_PLAYERS", "CORS_ORIGINS", "DEFAULT_PLAYERS",
                "LLM_NUM_CTX"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_defaults(monkeypatch):
    s = make(monkeypatch)
    assert s.llm_model == "gemma3:4b"
    assert s.ollama_host == "http://localhost:11434"
    assert (s.llm_num_ctx, s.llm_max_tokens, s.llm_keep_alive) == (4096, 256, "30m")
    assert (s.default_players, s.min_players, s.max_players) == (8, 4, 12)
    assert s.discussion_max_rounds == 5
    assert s.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_environment_overrides(monkeypatch):
    s = make(monkeypatch, LLM_MODEL="gemma3:1b", MAX_PLAYERS="10", OLLAMA_HOST="http://gpu-box:11434",
             CORS_ORIGINS='["https://example.com"]')
    assert s.llm_model == "gemma3:1b"
    assert s.max_players == 10
    assert s.ollama_host == "http://gpu-box:11434"
    assert s.cors_origins == ["https://example.com"]


def test_invalid_value_is_rejected(monkeypatch):
    with pytest.raises(ValueError):
        make(monkeypatch, DEFAULT_PLAYERS="0")


def test_llm_client_is_built_from_the_settings(monkeypatch):
    import backend.llm.factory as factory

    monkeypatch.setattr(factory, "get_settings",
                        lambda: make(monkeypatch, LLM_MODEL="gemma3:1b", LLM_NUM_CTX="2048"))
    factory.create_llm_client.cache_clear()
    try:
        client = factory.create_llm_client()
        assert (client.model, client.num_ctx) == ("gemma3:1b", 2048)
        assert factory.create_llm_client() is client      # one shared client
    finally:
        factory.create_llm_client.cache_clear()
