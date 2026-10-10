"""Shared test setup: no test may talk to a real Ollama server by accident."""
import pytest

from backend.llm import FakeLLMClient


def pytest_addoption(parser):
    parser.addoption("--run-realmodel", action="store_true", default=False,
                     help="also run tests marked 'realmodel' (need Ollama and the model)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-realmodel"):
        return
    skip = pytest.mark.skip(reason="needs Ollama; run with --run-realmodel")
    for item in items:
        if "realmodel" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def no_real_ollama(monkeypatch, request):
    """Everything that builds the shared client gets a fake one (tests can still patch their own)"""
    if "realmodel" in request.keywords:
        return
    for module in ("backend.main", "backend.api.games", "backend.api.health"):
        monkeypatch.setattr(f"{module}.create_llm_client", lambda: FakeLLMClient("no comment"))
