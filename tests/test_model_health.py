"""Model readiness check: startup log, 503 on game creation, compose files (no Ollama needed)."""
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.api import state
from backend.llm import FakeLLMClient
from backend.llm.health import check_model
from backend.services.sessions import SessionManager

ROOT = Path(__file__).resolve().parent.parent


class StatusClient(FakeLLMClient):
    def __init__(self, **status):
        super().__init__("x")
        self._status = {"model": "gemma3:4b", "host": "http://ollama:11434", "reachable": True,
                        "installed": True, "size_bytes": 3_400_000_000, **status}

    def status(self):
        return self._status


def test_ready_model():
    ready, message = check_model(StatusClient())
    assert ready and "gemma3:4b" in message and "3.4 GB" in message


def test_server_down_message_says_what_to_do():
    ready, message = check_model(StatusClient(reachable=False, installed=False))
    assert not ready and "not running at http://ollama:11434" in message


def test_missing_model_message_has_the_pull_command():
    ready, message = check_model(StatusClient(installed=False))
    assert not ready and "ollama pull gemma3:4b" in message


def test_clients_without_status_are_assumed_ready():
    assert check_model(FakeLLMClient())[0]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(state, "sessions", SessionManager())
    return TestClient(main.app, raise_server_exceptions=False)


def test_game_creation_answers_503_when_the_model_is_not_ready(client):
    with patch("backend.api.games.create_llm_client", return_value=StatusClient(installed=False)):
        response = client.post("/api/games", json={"num_players": 6})
    assert response.status_code == 503
    assert "ollama pull gemma3:4b" in response.json()["detail"]
    assert len(state.sessions) == 0


def test_game_creation_works_when_the_model_is_ready(client):
    with patch("backend.api.games.create_llm_client", return_value=StatusClient()):
        assert client.post("/api/games", json={"num_players": 6}).status_code == 200


def test_startup_logs_the_model_status(caplog):
    with patch("backend.main.create_llm_client", return_value=StatusClient(reachable=False)):
        with caplog.at_level(logging.INFO, logger="backend.main"):
            with TestClient(main.app):
                pass
    assert any(r.levelno == logging.ERROR and "not running" in r.message for r in caplog.records)

    caplog.clear()
    with patch("backend.main.create_llm_client", return_value=StatusClient()):
        with caplog.at_level(logging.INFO, logger="backend.main"):
            with TestClient(main.app):
                pass
    assert any(r.levelno == logging.INFO and "installed" in r.message for r in caplog.records)


def test_the_server_starts_even_if_the_model_is_missing():
    with patch("backend.main.create_llm_client", return_value=StatusClient(reachable=False)):
        with TestClient(main.app) as app_client:
            assert app_client.get("/api/health").status_code == 200


def test_compose_has_ollama_model_pull_and_backend_wiring():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for needle in ("ollama/ollama", "ollama-models:/root/.ollama", "OLLAMA_HOST=http://ollama:11434",
                   "service_healthy", "service_completed_successfully", "ollama pull ${LLM_MODEL:-gemma3:4b}"):
        assert needle in compose, needle
    gpu = (ROOT / "docker-compose.gpu.yml").read_text(encoding="utf-8")
    assert "driver: nvidia" in gpu and "capabilities: [gpu]" in gpu


def test_pull_scripts_exist_and_default_to_the_configured_model():
    sh = (ROOT / "scripts" / "pull_model.sh").read_text(encoding="utf-8")
    ps = (ROOT / "scripts" / "pull_model.ps1").read_text(encoding="utf-8")
    assert "gemma3:4b" in sh and "ollama pull" in sh and "LLM_MODEL" in sh
    assert "gemma3:4b" in ps and "ollama pull" in ps and "LLM_MODEL" in ps
