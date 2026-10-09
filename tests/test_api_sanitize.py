"""API hardening: hidden roles, generic errors, validation, CORS (fake LLM, no network)."""
import random
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.api import serializers, state
from backend.agents.ai_provider import AIProvider
from backend.config import Settings
from backend.models.game_models import PlayerStatus
from backend.services.sessions import SessionManager


class FakeLLM:
    def invoke(self, messages):
        return SimpleNamespace(content=random.choice(["no comment", "Hmm.", "Bob"]))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(state, "sessions", SessionManager())
    monkeypatch.setattr("backend.game.game_logic.time.sleep", lambda s: None)
    with patch.object(AIProvider, "get_llm", return_value=FakeLLM()):
        yield TestClient(main.app, raise_server_exceptions=False)


def settings(**overrides):
    return Settings(_env_file=None, **overrides)


def create(client, **body):
    response = client.post("/api/games", json=body)
    client.game_id = response.json().get("game_id")   # id of the most recent game
    return response


def game_of(client):
    return state.sessions.get(client.game_id).game


def test_roles_are_hidden_for_living_players(client):
    assert create(client, num_players=8).status_code == 200
    gid = client.game_id
    for url in (f"/api/games/{gid}", f"/api/games/{gid}/players"):
        data = client.get(url).json()
        assert all(p["role"] is None for p in data["players"]), url


def test_roles_of_dead_players_are_revealed(client):
    create(client, num_players=8)
    dead = game_of(client).state.players[0]
    dead.status = PlayerStatus.DEAD
    players = {p["id"]: p for p in client.get(f"/api/games/{client.game_id}/players").json()["players"]}
    assert players[dead.id]["role"] == dead.role.value
    assert all(p["role"] is None for pid, p in players.items() if pid != dead.id)


def test_reveal_roles_setting_shows_everything(client, monkeypatch):
    create(client, num_players=8)
    monkeypatch.setattr(serializers, "get_settings", lambda: settings(reveal_roles=True))
    assert all(p["role"] for p in client.get(f"/api/games/{client.game_id}/players").json()["players"])


def test_night_results_do_not_leak_guard_or_seer_information(client):
    create(client, num_players=10)
    gid = client.game_id
    client.post(f"/api/games/{gid}/start")
    data = client.post(f"/api/games/{gid}/next-phase").json()["data"]
    assert set(data["night_results"]) == {"deaths"}


def test_errors_do_not_expose_internal_details(client):
    with patch("backend.game.game_logic.WerewolfGame.setup_game", side_effect=RuntimeError("secret /srv/key.py")):
        response = create(client, num_players=8)
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret" not in response.text


def test_next_phase_error_is_generic(client):
    create(client, num_players=8)
    gid = client.game_id
    with patch("backend.game.game_logic.WerewolfGame.process_night_actions", side_effect=RuntimeError("secret")):
        client.post(f"/api/games/{gid}/start")
        response = client.post(f"/api/games/{gid}/next-phase")
    assert response.status_code == 500
    assert "secret" not in response.text


@pytest.mark.parametrize("bad", [0, -3, 5000, "many"])
def test_invalid_player_count_is_rejected(client, bad):
    assert create(client, num_players=bad).status_code == 422


def test_player_count_is_clamped_to_the_configured_range(client):
    assert create(client, num_players=2).json()["game_state"]["num_players"] == 4
    assert create(client, num_players=500).json()["game_state"]["num_players"] == 12


def test_cors_only_allows_configured_origins(client):
    def preflight(origin):
        return client.options("/api/games", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
        })

    assert preflight("http://localhost:3000").headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert "access-control-allow-origin" not in preflight("https://evil.example").headers
    assert "access-control-allow-credentials" not in preflight("http://localhost:3000").headers
