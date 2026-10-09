"""Non-blocking API, live events, phase state machine and error handling (fake LLM)."""
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.llm import FakeLLMClient
from backend.api import state
from backend.game.game_logic import WerewolfGame
from backend.models.game_models import GamePhase
from backend.services.phases import TRANSITIONS, advance_phase
from backend.services.sessions import SessionManager


def talkative_llm():
    """Everybody always answers with a short sentence naming Bob"""
    return FakeLLMClient("Bob looks odd.")


class BlockingLLM:
    """Blocks every call until released, like a slow model"""
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def generate(self, messages, **options):
        self.entered.set()
        self.release.wait(10)
        return "Bob"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(state, "sessions", SessionManager())
    monkeypatch.setattr("backend.game.game_logic.time.sleep", lambda s: None)
    with patch("backend.game.game_logic.create_llm_client", return_value=talkative_llm()):
        # the context manager keeps ONE event loop for all requests, like a real server
        with TestClient(main.app) as test_client:
            yield test_client


def new_game(client, n=6):
    return client.post("/api/games", json={"num_players": n}).json()["game_id"]


# --- the server stays responsive -------------------------------------------------------

def test_server_answers_while_a_phase_is_being_played(client):
    game_id = new_game(client)
    client.post(f"/api/games/{game_id}/start")
    blocking = BlockingLLM()
    for agent in state.sessions.get(game_id).game.player_agents.values():
        agent.llm = blocking

    outcome = {}

    def play():
        outcome["response"] = client.post(f"/api/games/{game_id}/next-phase")

    worker = threading.Thread(target=play)
    worker.start()
    try:
        assert blocking.entered.wait(5), "the phase never reached the LLM"
        started = time.monotonic()
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get(f"/api/games/{game_id}").status_code == 200
        assert client.post(f"/api/games/{game_id}/next-phase").status_code == 409
        assert time.monotonic() - started < 2     # nothing waited for the slow LLM
        assert worker.is_alive()                   # the phase is still running
    finally:
        blocking.release.set()
        worker.join(10)
    assert outcome["response"].status_code == 200
    assert outcome["response"].json()["data"]["phase"] == "day"
    assert not state.sessions.get(game_id).lock.locked()


# --- live events --------------------------------------------------------------------------

def collect_until_phase_change(ws, limit=200):
    messages = []
    for _ in range(limit):
        message = ws.receive_json()
        messages.append(message)
        if message["type"] == "phase_change":
            return messages
    pytest.fail("no phase_change event")


def test_player_spoke_events_stream_during_the_discussion(client):
    game_id = new_game(client)
    client.post(f"/api/games/{game_id}/start")
    client.post(f"/api/games/{game_id}/next-phase")            # night -> day
    with client.websocket_connect(f"/ws/{game_id}") as ws:
        response = client.post(f"/api/games/{game_id}/next-phase")   # day -> discussion
        assert response.json()["data"]["phase"] == "discussion"
        events = collect_until_phase_change(ws)
    spoke = [m for m in events if m["type"] == "player_spoke"]
    assert spoke and all(set(m["data"]) == {"sender", "content"} for m in spoke)
    assert len(spoke) == len(response.json()["data"]["messages"])
    assert events[-1]["type"] == "phase_change"


def test_vote_cast_events_stream_during_the_vote(client):
    game_id = new_game(client)
    client.post(f"/api/games/{game_id}/start")
    client.post(f"/api/games/{game_id}/next-phase")
    client.post(f"/api/games/{game_id}/next-phase")            # discussion
    alive = sum(p["status"] == "alive" for p in client.get(f"/api/games/{game_id}").json()["players"])
    with client.websocket_connect(f"/ws/{game_id}") as ws:
        client.post(f"/api/games/{game_id}/next-phase")        # vote
        events = collect_until_phase_change(ws)
    votes = [m for m in events if m["type"] == "vote_cast"]
    assert len(votes) == alive
    assert all(set(m["data"]) == {"voter", "target"} and m["data"]["voter"] != m["data"]["target"]
               for m in votes)


def test_background_phase_answers_202_and_reports_on_the_websocket(client):
    game_id = new_game(client)
    client.post(f"/api/games/{game_id}/start")
    with client.websocket_connect(f"/ws/{game_id}") as ws:
        response = client.post(f"/api/games/{game_id}/next-phase?background=true")
        assert response.status_code == 202 and response.json() == {"status": "started"}
        events = collect_until_phase_change(ws)
    final = events[-1]["data"]
    assert final["phase"] == "day" and set(final["night_results"]) == {"deaths"}
    for _ in range(100):                                       # the lock is released right after
        if not state.sessions.get(game_id).lock.locked():
            break
        time.sleep(0.05)
    assert not state.sessions.get(game_id).lock.locked()


def test_background_phase_failure_is_reported_and_unlocks_the_game(client):
    game_id = new_game(client)
    client.post(f"/api/games/{game_id}/start")
    with client.websocket_connect(f"/ws/{game_id}") as ws:
        with patch("backend.game.game_logic.WerewolfGame.process_night_actions",
                   side_effect=RuntimeError("secret")):
            assert client.post(f"/api/games/{game_id}/next-phase?background=true").status_code == 202
            message = ws.receive_json()
    assert message == {"type": "error", "data": "Failed to progress to the next phase"}
    for _ in range(100):
        if not state.sessions.get(game_id).lock.locked():
            break
        time.sleep(0.05)
    assert not state.sessions.get(game_id).lock.locked()


# --- errors and health ----------------------------------------------------------------------

def test_unexpected_errors_become_a_generic_500(client):
    game_id = new_game(client)
    client.post(f"/api/games/{game_id}/start")
    quiet = TestClient(main.app, raise_server_exceptions=False)
    with patch("backend.game.game_logic.WerewolfGame.process_night_actions",
               side_effect=RuntimeError("secret /srv/key.py")):
        response = quiet.post(f"/api/games/{game_id}/next-phase")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert not state.sessions.get(game_id).lock.locked()


def test_health_counts_games(client):
    assert client.get("/api/health").json() == {"status": "ok", "games": 0}
    new_game(client)
    assert client.get("/api/health").json()["games"] == 1
    assert client.get("/").json()["status"] == "running"


# --- phase state machine -------------------------------------------------------------------------

def fake_game(phase, winner=None):
    game = MagicMock()
    game.state.phase = phase
    game.check_win_condition.return_value = winner
    game.conduct_vote.return_value = (SimpleNamespace(name="Bob"), {"Bob": 2})
    game.process_night_actions.return_value = {"deaths": []}
    return game


def test_every_playable_phase_has_a_transition():
    assert set(TRANSITIONS) == {GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING}


def test_night_leads_to_day():
    game = fake_game(GamePhase.NIGHT)
    result = advance_phase(game)
    assert result["phase"] == "day" and result["night_results"] == {"deaths": []}
    game.process_night_actions.assert_called_once()
    game.start_day.assert_called_once()


def test_day_leads_to_discussion():
    game = fake_game(GamePhase.DAY)
    game.conduct_discussion.return_value = ["[A] hi"]
    assert advance_phase(game) == {"phase": "discussion", "messages": ["[A] hi"]}


def test_discussion_leads_to_vote_then_next_night():
    game = fake_game(GamePhase.DISCUSSION)
    result = advance_phase(game)
    assert result["phase"] == "voting" and result["eliminated"] == "Bob" and result["votes"] == {"Bob": 2}
    assert result["next_phase"] == "night"
    game.start_night.assert_called_once()
    game.end_game.assert_not_called()


def test_discussion_leads_to_vote_then_end():
    game = fake_game(GamePhase.DISCUSSION, winner="villagers")
    result = advance_phase(game)
    assert result["game_ended"] and result["winner"] == "villagers"
    game.end_game.assert_called_once_with("villagers")
    game.start_night.assert_not_called()


def test_voting_phase_resumes_to_night_or_end():
    assert advance_phase(fake_game(GamePhase.VOTING))["phase"] == "night"
    ended = advance_phase(fake_game(GamePhase.VOTING, winner="werewolves"))
    assert ended["phase"] == "ended" and ended["winner"] == "werewolves"


@pytest.mark.parametrize("phase", [GamePhase.SETUP, GamePhase.ENDED])
def test_setup_and_ended_phases_are_not_advanced(phase):
    assert advance_phase(fake_game(phase)) == {"error": f"Unknown phase: {phase.value}"}


# --- game events ----------------------------------------------------------------------------------

def test_game_reports_events_and_survives_a_failing_listener():
    game = WerewolfGame.__new__(WerewolfGame)
    seen = []
    game.on_event = lambda kind, data: seen.append((kind, data))
    game._emit("player_spoke", {"sender": "A"})
    assert seen == [("player_spoke", {"sender": "A"})]

    def broken(kind, data):
        raise RuntimeError("listener bug")

    game.on_event = broken
    game._emit("player_spoke", {})          # must not raise
    del game.on_event
    game._emit("player_spoke", {})          # no listener attribute at all: also fine


def test_full_game_with_events_enabled(client):
    game_id = new_game(client, 6)
    client.post(f"/api/games/{game_id}/start")
    for _ in range(60):
        data = client.post(f"/api/games/{game_id}/next-phase").json()["data"]
        if data.get("game_ended"):
            return
    pytest.fail("game did not end")
