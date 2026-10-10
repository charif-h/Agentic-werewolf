"""Shared test setup: no test may talk to a real Ollama server."""
import pytest

from backend.llm import FakeLLMClient


@pytest.fixture(autouse=True)
def no_real_ollama(monkeypatch):
    """Everything that builds the shared client gets a fake one (tests can still patch their own)"""
    for module in ("backend.main", "backend.api.games", "backend.api.health"):
        monkeypatch.setattr(f"{module}.create_llm_client", lambda: FakeLLMClient("no comment"))
