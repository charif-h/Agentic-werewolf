"""Player diaries: the model's answer, when entries are written, and who may read them."""
import json
import random
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.agents.player_agent import PlayerAgent
from backend.api import serializers, state
from backend.game.game_logic import WerewolfGame
from backend.llm import FakeLLMClient, schemas
from backend.models.game_models import BigFive, PlayerProfile, Role, Sex
from backend.services.phases import advance_phase
from backend.services.sessions import SessionManager

OTHERS = ["Bob", "Cy"]


def make_agent(responses, **kwargs):
    profile = PlayerProfile(id="p", name="Ann", sex=Sex.FEMALE, age=30,
                            personality=BigFive(extraversion=2), role=Role.VILLAGER)
    return PlayerAgent(profile, FakeLLMClient(responses, **kwargs))


def answer(*opinions, summary="A tense day."):
    return json.dumps({"summary": summary, "opinions": [
        {"player": p, "guess": g, "confidence": c, "reason": r} for p, g, c, r in opinions]})


# --- parser ----------------------------------------------------------------------------

def test_parse_diary_keeps_valid_opinions_in_clean_form():
    text = answer(("bob ", "werewolf", "high", " He never talks. "), ("Cy", "unsure", "low", "No idea."))
    entry = schemas.parse_diary(text, OTHERS)
    assert entry["summary"] == "A tense day."
    assert entry["opinions"][0] == {"player": "Bob", "guess": "werewolf", "confidence": "high",
                                    "reason": "He never talks."}
    assert [o["player"] for o in entry["opinions"]] == ["Bob", "Cy"]


def test_parse_diary_drops_unknown_players_duplicates_and_bad_values():
    text = answer(("Zed", "werewolf", "high", "?"), ("Bob", "werewolf", "high", "a"),
                  ("Bob", "villager", "low", "b"), ("Cy", "maybe", "low", "c"))
    entry = schemas.parse_diary(text, OTHERS)
    assert entry["opinions"] == [{"player": "Bob", "guess": "werewolf", "confidence": "high", "reason": "a"}]


@pytest.mark.parametrize("text", [None, "", "no", "{}", '{"summary": "x", "opinions": []}',
                                  '{"summary": 1, "opinions": []}', answer(("Zed", "werewolf", "low", "x"))])
def test_parse_diary_rejects_unusable_answers(text):
    assert schemas.parse_diary(text, OTHERS) is None


def test_diary_schema_restricts_players_to_the_given_names():
    schema = schemas.diary_schema(OTHERS)
    assert schema["properties"]["opinions"]["items"]["properties"]["player"]["enum"] == OTHERS


# --- agent -----------------------------------------------------------------------------

def test_write_diary_stores_the_entry_and_remembers_the_step():
    agent = make_agent(answer(("Bob", "werewolf", "high", "Suspicious."), ("Cy", "villager", "medium", "Fine.")))
    entry = agent.write_diary("Day 1", "[Bob] I am innocent", OTHERS)
    assert entry["step"] == "Day 1"
    assert agent.diary == [entry]
    prompt = agent.llm.last_messages[-1].content
    assert "Day 1" in prompt and "[Bob] I am innocent" in prompt and "Bob, Cy" in prompt


def test_next_entry_reminds_the_player_of_the_previous_one():
    agent = make_agent(answer(("Bob", "werewolf", "high", "x"), ("Cy", "unsure", "low", "y"),
                              summary="First thoughts."))
    agent.write_diary("Night 1", "", OTHERS)
    agent.write_diary("Day 1", "", OTHERS)
    assert "First thoughts." in agent.llm.last_messages[-1].content


def test_write_diary_without_a_valid_answer_gives_no_entry():
    agent = make_agent("I think Bob is a wolf.", wrap_json=False)
    assert agent.write_diary("Day 1", "", OTHERS) is None
    assert agent.diary == []
    assert make_agent("x").write_diary("Day 1", "", []) is None


def test_write_diary_survives_a_model_failure():
    agent = make_agent(RuntimeError("down"))
    assert agent.write_diary("Day 1", "", OTHERS) is None


def test_the_reason_comes_before_the_label_in_the_schema():
    keys = list(schemas.diary_schema(OTHERS)["properties"]["opinions"]["items"]["properties"])
    assert keys.index("reason") < keys.index("guess")


def test_the_vote_and_the_discussion_follow_the_latest_diary_entry():
    agent = make_agent(answer(("Bob", "werewolf", "high", "He deflects."), ("Cy", "villager", "low", "Honest.")))
    agent.write_diary("Night 1", "", OTHERS)
    agent.vote("[Bob] hi", ["Ann", "Bob", "Cy"])
    prompt = agent.llm.last_messages[-1].content
    assert "you suspect Bob (high confidence): He deflects." in prompt
    assert "you trust Cy (low confidence)" in prompt
    agent.discuss("[Bob] hi", ["Ann", "Bob", "Cy"])
    assert "you suspect Bob" in agent.llm.last_messages[-1].content


def test_the_day_entry_knows_how_the_player_voted():
    agent = make_agent(answer(("Bob", "werewolf", "high", "x"), ("Cy", "unsure", "low", "y")))
    agent.last_vote = "Bob"
    agent.write_diary("Day 1", "", OTHERS)
    assert "You voted to eliminate Bob" in agent.llm.last_messages[-1].content
    agent.write_diary("Night 2", "", OTHERS)
    assert "You voted" not in agent.llm.last_messages[-1].content


# --- game ------------------------------------------------------------------------------

def new_game(n=6):
    game = WerewolfGame(num_players=n, llm=FakeLLMClient("Bob looks odd."))
    game.setup_game()
    return game


def steps(agent):
    """Steps of the night and day summaries (the role card and the pack come first)"""
    return [e["step"] for e in agent.diary if e["kind"] in ("night_summary", "day_summary")]


def living_agents(game):
    return [a for a in game.player_agents.values() if a.profile.status.value == "alive"]


def test_every_living_player_gets_a_night_and_a_day_entry():
    game = new_game()
    game.start_night()
    advance_phase(game)                         # night -> day
    assert living_agents(game)
    assert all(steps(a) == ["Night 1"] for a in living_agents(game))
    advance_phase(game)                         # discussion
    result = advance_phase(game)                # vote
    if not result.get("game_ended"):
        assert all(steps(a) == ["Night 1", "Day 1"] for a in living_agents(game))
    for agent in game.player_agents.values():
        for entry in agent.diary:               # a player never has an opinion about themselves
            assert agent.profile.name not in [o["player"] for o in entry["data"].get("opinions", [])]


def test_diaries_can_be_turned_off(monkeypatch):
    monkeypatch.setattr("backend.game.game_logic.get_settings",
                        lambda: type("S", (), {"diary_enabled": False, "psytest_enabled": False})())
    game = new_game()
    game.start_night()
    game.start_day()
    calls = len(game.llm.calls)
    game.write_diaries(night=True)
    assert len(game.llm.calls) == calls
    assert all(not steps(a) for a in game.player_agents.values())


def test_a_failing_diary_does_not_stop_the_game():
    game = new_game()
    for agent in game.player_agents.values():
        agent.write_diary = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    game.start_night()
    game.start_day()
    game.write_diaries(night=True)             # no exception


# --- API -------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(state, "sessions", SessionManager())
    def chatty(messages):
        return random.choice(["Bob looks odd.", "I trust Cy.", "no comment"])

    with patch("backend.api.games.create_llm_client", return_value=FakeLLMClient(chatty)):
        with TestClient(main.app) as test_client:
            yield test_client


def first_night(client):
    game_id = client.post("/api/games", json={"num_players": 6}).json()["game_id"]
    client.post(f"/api/games/{game_id}/start")
    client.post(f"/api/games/{game_id}/next-phase")
    players = client.get(f"/api/games/{game_id}/players").json()["players"]
    return game_id, players


def test_the_diary_of_a_living_player_is_secret_by_default(client):
    game_id, players = first_night(client)
    alive = next(p for p in players if p["status"] == "alive")
    assert client.get(f"/api/games/{game_id}/players/{alive['id']}/diary").status_code == 403


def test_the_diary_is_readable_in_spectator_mode(client, monkeypatch):
    monkeypatch.setattr(serializers, "get_settings", lambda: type("S", (), {"reveal_roles": True})())
    game_id, players = first_night(client)
    alive = next(p for p in players if p["status"] == "alive")
    body = client.get(f"/api/games/{game_id}/players/{alive['id']}/diary").json()
    assert body["player"] == alive["name"]
    assert body["entries"][0]["kind"] == "role_card"
    summary = body["entries"][-1]
    assert summary["step"] == "Night 1" and summary["kind"] == "night_summary"
    assert summary["opinions"] and summary["summary"] == summary["text"]      # old fields stay


def test_the_diary_of_a_dead_player_is_public(client):
    game_id, players = first_night(client)
    dead = [p for p in players if p["status"] == "dead"]
    if not dead:
        pytest.skip("nobody died tonight")
    assert client.get(f"/api/games/{game_id}/players/{dead[0]['id']}/diary").status_code == 200


def test_an_unknown_player_has_no_diary(client):
    game_id, _ = first_night(client)
    assert client.get(f"/api/games/{game_id}/players/nobody/diary").status_code == 404


# --- typed entries ---------------------------------------------------------------------

def test_make_entry_has_the_typed_shape_and_rejects_unknown_kinds():
    from backend.models.diary import DIARY_KINDS, make_entry
    entry = make_entry(3, "Day 1", "reaction", "John accuses me.", {"about": "John"})
    assert entry == {"id": 3, "step": "Day 1", "kind": "reaction", "text": "John accuses me.",
                     "data": {"about": "John"}}
    summary = make_entry(4, "Night 1", "night_summary", "Quiet.", {"opinions": [{"player": "Bob"}]})
    assert summary["summary"] == "Quiet." and summary["opinions"] == [{"player": "Bob"}]
    assert set(DIARY_KINDS) == {"role_card", "pack", "reaction", "decision", "plan", "night_summary", "day_summary"}
    with pytest.raises(ValueError):
        make_entry(1, "x", "poem", "x")


def test_the_first_diary_entry_of_every_player_is_the_role_card():
    game = new_game()
    for agent in game.player_agents.values():
        first = agent.diary[0]
        assert first["kind"] == "role_card" and first["id"] == 1
        assert first["data"] == {"role": agent.profile.role.value}
        assert first["text"] == f"I am a {agent.profile.role.value}."


def test_werewolves_note_their_pack_right_after_the_role_card():
    game = new_game(12)
    wolves = [a for a in game.player_agents.values() if a.profile.role == Role.WEREWOLF]
    assert wolves
    for wolf in wolves:
        mates = [w.profile.name for w in wolves if w is not wolf]
        assert [e["kind"] for e in wolf.diary] == ["role_card", "pack"]
        assert wolf.diary[1]["data"] == {"mates": mates}
    villager = next(a for a in game.player_agents.values() if a.profile.role == Role.VILLAGER)
    assert [e["kind"] for e in villager.diary] == ["role_card"]


def test_the_header_survives_when_the_older_entries_are_cut(monkeypatch):
    agent = make_agent("x")
    agent.write_role_card()
    agent.write_pack(["Bob"])
    for day in range(1, 8):
        agent._add_entry(f"Day {day}", "reaction", f"Thought number {day} " + "blah " * 40)
    monkeypatch.setattr("backend.agents.player_agent.get_settings",
                        lambda: type("S", (), {"diary_prompt_entries": 6, "diary_token_budget": 200})())
    lines = agent._knowledge_with_notes()
    assert "Your diary, first page: I am a villager." in lines
    assert "Your diary, first page: My fellow werewolves are Bob." in lines
    shown = [line for line in lines if line.startswith("Day ")]
    assert shown and shown[0].startswith("Day 7") and len(shown) < 6          # newest first, oldest cut


def test_only_the_latest_entries_are_shown_newest_first(monkeypatch):
    agent = make_agent("x")
    for day in range(1, 5):
        agent._add_entry(f"Day {day}", "reaction", f"thought {day}")
    monkeypatch.setattr("backend.agents.player_agent.get_settings",
                        lambda: type("S", (), {"diary_prompt_entries": 2, "diary_token_budget": 300})())
    lines = agent._knowledge_with_notes()
    assert lines == ["Your private diary, newest entry first:", "Day 4: thought 4", "Day 3: thought 3"]
