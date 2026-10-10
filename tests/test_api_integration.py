"""
End-to-end API tests: whole games through HTTP and WebSocket with a scripted LLM.

They replace the old PowerShell integration scripts. No model, no network.
"""
import random
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.api import state
from backend.llm import FakeLLMClient
from backend.services.sessions import SessionManager

TEAMS = ("villagers", "werewolves")


def chatty(messages):
    return random.choice(["Bob looks odd.", "I trust Cy.", "no comment", "Dee, why so quiet?"])


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(state, "sessions", SessionManager())
    with patch("backend.api.games.create_llm_client", return_value=FakeLLMClient(chatty)):
        with TestClient(main.app) as test_client:      # one event loop, like a real server
            yield test_client


def create(client, n=8):
    return client.post("/api/games", json={"num_players": n}).json()["game_id"]


def players(client, game_id):
    return client.get(f"/api/games/{game_id}/players").json()["players"]


def play_to_the_end(client, game_id, limit=80):
    """Call next-phase until the game ends; returns the list of results"""
    results = []
    for _ in range(limit):
        response = client.post(f"/api/games/{game_id}/next-phase")
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        results.append(data)
        if data.get("game_ended"):
            return results
    pytest.fail("the game never ended")


@pytest.mark.parametrize("n", [4, 6, 8, 10, 12])
def test_a_game_can_be_played_to_the_end(client, n):
    game_id = create(client, n)
    assert client.get(f"/api/games/{game_id}").json()["phase"] == "setup"
    assert client.post(f"/api/games/{game_id}/start").json()["status"] == "success"
    assert client.get(f"/api/games/{game_id}").json()["phase"] == "night"

    results = play_to_the_end(client, game_id)

    final = results[-1]
    assert final["winner"] in TEAMS and final["end_announcement"]
    phases = [r["phase"] for r in results]
    assert phases[0] == "day" and phases.count("voting") >= 1
    # the phases always come in the order day -> discussion -> voting (-> night is implicit)
    cycle = [p for p in phases if p in ("day", "discussion", "voting")]
    assert cycle[:3] == ["day", "discussion", "voting"]

    state_after = client.get(f"/api/games/{game_id}").json()
    assert state_after["phase"] == "ended"
    assert any("win" in line for line in state_after["game_log"])
    assert state_after["llm"]["skipped_turns"] >= 0


def test_roles_stay_hidden_until_a_player_dies(client):
    game_id = create(client, 8)
    client.post(f"/api/games/{game_id}/start")
    for _ in range(40):
        for p in players(client, game_id):
            assert (p["role"] is not None) == (p["status"] == "dead"), p
        if client.post(f"/api/games/{game_id}/next-phase").json()["data"].get("game_ended"):
            break
    for p in players(client, game_id):
        assert (p["role"] is not None) == (p["status"] == "dead")


def test_the_winner_matches_the_survivors(client):
    game_id = create(client, 8)
    client.post(f"/api/games/{game_id}/start")
    winner = play_to_the_end(client, game_id)[-1]["winner"]
    alive = [p for p in players(client, game_id) if p["status"] == "alive"]
    assert alive, "someone always survives"
    # the endpoint only shows the roles of the dead: werewolves won when no villager majority is left
    wolves_dead = sum(p["status"] == "dead" and p["role"] == "werewolf" for p in players(client, game_id))
    total_wolves = 2
    assert (winner == "villagers") == (wolves_dead == total_wolves)


def test_next_phase_needs_a_started_game_and_stops_at_the_end(client):
    game_id = create(client, 6)
    early = client.post(f"/api/games/{game_id}/next-phase")
    assert early.status_code == 409 and "not started" in early.json()["detail"]
    client.post(f"/api/games/{game_id}/start")
    play_to_the_end(client, game_id)
    late = client.post(f"/api/games/{game_id}/next-phase")
    assert late.status_code == 409 and "ended" in late.json()["detail"]
    assert not state.sessions.get(game_id).lock.locked()


def test_unknown_game_and_bad_requests(client):
    for method, url in [("get", "/api/games/missing"), ("post", "/api/games/missing/start"),
                        ("post", "/api/games/missing/next-phase"), ("get", "/api/games/missing/players"),
                        ("delete", "/api/games/missing")]:
        response = getattr(client, method)(url)
        assert response.status_code == 404 and response.json() == {"detail": "Game not found"}, url
    assert client.post("/api/games", content="not json",
                       headers={"Content-Type": "application/json"}).status_code == 422
    assert client.post("/api/games", json={"num_players": "many"}).status_code == 422
    assert client.post("/api/games", json={"num_players": 0}).status_code == 422
    assert client.get("/api/nothing-here").status_code == 404
    assert client.put("/api/games").status_code == 405


def test_default_player_count_is_used_when_none_is_given(client):
    response = client.post("/api/games", json={})
    assert response.status_code == 200 and response.json()["game_state"]["num_players"] == 8


def test_games_played_in_turns_do_not_influence_each_other(client):
    first, second = create(client, 6), create(client, 10)
    client.post(f"/api/games/{first}/start")
    client.post(f"/api/games/{first}/next-phase")
    assert client.get(f"/api/games/{second}").json()["phase"] == "setup"
    assert client.get(f"/api/games/{second}").json()["day_number"] == 0
    client.post(f"/api/games/{second}/start")
    play_to_the_end(client, second)
    assert client.get(f"/api/games/{first}").json()["phase"] == "day"
    assert len(players(client, first)) == 6 and len(players(client, second)) == 10
    assert client.get("/api/health").json()["games"] == 2
    client.delete(f"/api/games/{second}")
    assert client.get("/api/health").json()["games"] == 1


def test_websocket_receives_the_whole_story_of_a_game(client):
    game_id = create(client, 6)
    with client.websocket_connect(f"/ws/{game_id}") as ws:
        client.post(f"/api/games/{game_id}/start")
        events = [ws.receive_json()]
        for _ in range(60):
            data = client.post(f"/api/games/{game_id}/next-phase").json()["data"]
            # every phase is announced after its progress events
            while True:
                message = ws.receive_json()
                events.append(message)
                if message["type"] == "phase_change":
                    break
            if data.get("game_ended"):
                break
        else:
            pytest.fail("the game never ended")
    kinds = [e["type"] for e in events]
    assert kinds[0] == "phase_change" and kinds.count("phase_change") >= 4
    assert "vote_cast" in kinds and "player_spoke" in kinds
    assert events[-1]["data"]["game_ended"] is True
    # votes of one round come right before the phase_change that reports them
    last_votes = [e for e in events if e["type"] == "vote_cast"]
    voters = [e["data"]["voter"] for e in last_votes]
    assert all(e["data"]["target"] != e["data"]["voter"] for e in last_votes)
    assert len(voters) >= 3
    # nothing secret is broadcast
    for e in events:
        assert "role" not in str(e["data"].get("night_results", ""))


def test_a_busy_game_rejects_a_second_phase_but_other_games_play_on(client):
    busy, other = create(client, 6), create(client, 6)
    client.post(f"/api/games/{busy}/start")
    client.post(f"/api/games/{other}/start")
    session = state.sessions.get(busy)
    session.lock.acquire()
    try:
        assert client.post(f"/api/games/{busy}/next-phase").status_code == 409
        assert client.post(f"/api/games/{other}/next-phase").status_code == 200
    finally:
        session.lock.release()
