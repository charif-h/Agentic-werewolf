"""Tests for the central settings."""
import pytest

from backend.config import Settings


def make(monkeypatch, **env):
    for key in ("AI_PROVIDER", "MAX_PLAYERS", "OPENAI_API_KEY", "GOOGLE_API_KEY",
                "MISTRAL_API_KEY", "CORS_ORIGINS", "DEFAULT_PLAYERS"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_defaults(monkeypatch):
    s = make(monkeypatch)
    assert s.ai_provider == "openai"
    assert (s.default_players, s.min_players, s.max_players) == (8, 4, 12)
    assert s.discussion_max_rounds == 5
    assert s.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert s.openai_api_key is None


def test_environment_overrides(monkeypatch):
    s = make(monkeypatch, AI_PROVIDER="gemini", MAX_PLAYERS="10", GOOGLE_API_KEY="k",
             CORS_ORIGINS='["https://example.com"]')
    assert s.ai_provider == "gemini"
    assert s.max_players == 10
    assert s.google_api_key == "k"
    assert s.cors_origins == ["https://example.com"]


def test_invalid_value_is_rejected(monkeypatch):
    with pytest.raises(ValueError):
        make(monkeypatch, DEFAULT_PLAYERS="0")


def test_provider_factory_uses_settings(monkeypatch):
    from backend.agents.ai_provider import AIProvider
    import backend.agents.ai_provider as module

    monkeypatch.setattr(module, "get_settings", lambda: make(monkeypatch, GOOGLE_API_KEY="k"))
    assert AIProvider.get_available_providers() == ["gemini"]
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        AIProvider.get_llm()
    with pytest.raises(ValueError, match="Unknown AI provider"):
        AIProvider.get_llm(provider="nope")
