"""Game sessions: several independent games, ids, expiry, per-game WebSocket (fake LLM)."""
import random
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.api import state
from backend.llm import FakeLLMClient
from backend.services.sessions import SessionManager, SessionNotFound


def fake_llm():
    return FakeLLMClient(lambda messages: random.choice(["no comment", "Hmm.", "Bob"]))


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


# --- SessionManager ------------------------------------------------------------

def test_sessions_get_unique_unguessable_ids():
    manager = SessionManager()
    ids = {manager.create(MagicMock()).id for _ in range(50)}
    assert len(ids) == 50 and all(len(i) == 32 for i in ids)


def test_get_and_delete():
    manager = SessionManager()
    session = manager.create(MagicMock())
    assert manager.get(session.id) is session
    assert manager.delete(session.id) is True
    assert manager.delete(session.id) is False
    with pytest.raises(SessionNotFound):
        manager.get(session.id)
    assert manager.find("nope") is None


def test_idle_sessions_expire():
    clock = Clock()
    manager = SessionManager(ttl_seconds=100, clock=clock)
    old, fresh = manager.create(MagicMock()), None
    clock.now = 60
    fresh = manager.create(MagicMock())
    clock.now = 130              # old idle 130s, fresh idle 70s
    assert manager.cleanup() == 1
    assert manager.find(old.id) is None and manager.find(fresh.id) is fresh


def test_using_a_session_keeps_it_alive():
    clock = Clock()
    manager = SessionManager(ttl_seconds=100, clock=clock)
    session = manager.create(MagicMock())
    clock.now = 90
    manager.get(session.id)
    clock.now = 150
    assert manager.cleanup() == 0


def test_a_running_session_is_not_expired():
    clock = Clock()
    manager = SessionManager(ttl_seconds=10, clock=clock)
    session = manager.create(MagicMock())
    session.lock.acquire()
    clock.now = 1000
    assert manager.cleanup() == 0
    session.lock.release()
    assert manager.cleanup() == 1


def test_least_recently_used_session_is_dropped_when_full():
    clock = Clock()
    manager = SessionManager(max_sessions=2, clock=clock)
    first = manager.create(MagicMock())
    clock.now = 1
    second = manager.create(MagicMock())
    clock.now = 2
    manager.get(first.id)                # first is now more recent than second
    clock.now = 3
    third = manager.create(MagicMock())
    assert len(manager) == 2
    assert manager.find(second.id) is None
    assert manager.find(first.id) and manager.find(third.id)


# --- HTTP API ---------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(state, "sessions", SessionManager())
    with patch("backend.game.game_logic.create_llm_client", return_value=fake_llm()):
        yield TestClient(main.app, raise_server_exceptions=False)


def new_game(client, n=8):
    return client.post("/api/games", json={"num_players": n}).json()["game_id"]


def test_two_games_are_independent(client):
    a, b = new_game(client, 6), new_game(client, 10)
    assert a != b
    assert len(client.get(f"/api/games/{a}").json()["players"]) == 6
    assert len(client.get(f"/api/games/{b}").json()["players"]) == 10
    client.post(f"/api/games/{a}/start")
    assert client.get(f"/api/games/{a}").json()["phase"] == "night"
    assert client.get(f"/api/games/{b}").json()["phase"] == "setup"
    names_a = {p["name"] for p in client.get(f"/api/games/{a}/players").json()["players"]}
    assert client.get(f"/api/games/{b}/players").json()["players"][0]["name"] is not None
    assert len(names_a) == 6


def test_unknown_game_is_404_everywhere(client):
    for method, url in [("get", "/api/games/nope"), ("post", "/api/games/nope/start"),
                        ("post", "/api/games/nope/next-phase"), ("get", "/api/games/nope/players"),
                        ("delete", "/api/games/nope")]:
        assert getattr(client, method)(url).status_code == 404, url


def test_delete_game(client):
    game_id = new_game(client)
    assert client.delete(f"/api/games/{game_id}").status_code == 200
    assert client.get(f"/api/games/{game_id}").status_code == 404


def test_old_global_endpoints_are_gone(client):
    assert client.post("/api/game/create", json={}).status_code == 404
    assert client.get("/api/game/state").status_code == 404


def test_busy_game_answers_409_instead_of_running_twice(client):
    game_id = new_game(client)
    session = state.sessions.get(game_id)
    client.post(f"/api/games/{game_id}/start")
    session.lock.acquire()               # a phase is "running"
    try:
        assert client.post(f"/api/games/{game_id}/next-phase").status_code == 409
        assert client.post(f"/api/games/{game_id}/start").status_code == 409
    finally:
        session.lock.release()
    assert client.post(f"/api/games/{game_id}/next-phase").status_code == 200


def test_lock_is_released_after_an_error(client):
    game_id = new_game(client)
    client.post(f"/api/games/{game_id}/start")
    with patch("backend.game.game_logic.WerewolfGame.process_night_actions", side_effect=RuntimeError("x")):
        assert client.post(f"/api/games/{game_id}/next-phase").status_code == 500
    assert not state.sessions.get(game_id).lock.locked()


def test_a_full_game_can_be_played_through_the_api(client):
    game_id = new_game(client, 6)
    client.post(f"/api/games/{game_id}/start")
    for _ in range(60):
        data = client.post(f"/api/games/{game_id}/next-phase").json()["data"]
        if data.get("game_ended"):
            assert data["winner"] in ("villagers", "werewolves")
            return
    pytest.fail("game did not end")


# --- WebSocket ----------------------------------------------------------------------

def test_websocket_receives_events_of_its_own_game_only(client):
    a, b = new_game(client), new_game(client)
    with client.websocket_connect(f"/ws/{a}") as ws_a, client.websocket_connect(f"/ws/{b}") as ws_b:
        client.post(f"/api/games/{a}/start")
        message = ws_a.receive_json()
        assert message["type"] == "phase_change" and message["data"]["phase"] == "night"
        ws_b.send_json({"ping": 1})                   # nothing from game a is queued for b
        assert ws_b.receive_json() == {"type": "echo", "data": {"ping": 1}}


def test_websocket_for_unknown_game_is_refused(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/nope"):
            pass


def test_websocket_survives_invalid_json(client):
    game_id = new_game(client)
    with client.websocket_connect(f"/ws/{game_id}") as ws:
        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"
        ws.send_json({"ok": True})
        assert ws.receive_json()["type"] == "echo"
