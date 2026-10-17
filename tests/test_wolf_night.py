"""The werewolves wake up together, talk in private and choose one victim (fake LLM, no network)."""
import random
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.api import serializers, state
from backend.engine import rules
from backend.game.game_logic import WerewolfGame
from backend.llm import FakeLLMClient
from backend.models.game_models import BigFive, GameState, PlayerProfile, Role, Sex
from backend.services.sessions import SessionManager


# --- rules.resolve_wolf_choice ----------------------------------------------------------

def test_the_majority_wins():
    assert rules.resolve_wolf_choice({"A": "Bob", "B": "Cy", "C": "Bob"}, lead="B") == "Bob"


def test_a_tie_goes_to_the_lead_wolfs_proposal():
    assert rules.resolve_wolf_choice({"A": "Bob", "B": "Cy"}, lead="B") == "Cy"
    assert rules.resolve_wolf_choice({"A": "Bob", "B": "Cy"}, lead="A") == "Bob"


def test_a_tie_without_a_useful_lead_is_random_among_the_tied_targets():
    rng = random.Random(1)
    seen = {rules.resolve_wolf_choice({"A": "Bob", "B": "Cy", "C": "Dee"}, lead="C", rng=rng) for _ in range(1)}
    seen |= {rules.resolve_wolf_choice({"A": "Bob", "B": "Cy", "C": None, "D": None}, lead="C",
                                       rng=random.Random(n)) for n in range(40)}
    assert seen <= {"Bob", "Cy", "Dee"} and {"Bob", "Cy"} <= seen


def test_no_valid_proposal_gives_none():
    assert rules.resolve_wolf_choice({}) is None
    assert rules.resolve_wolf_choice({"A": None, "B": None}, lead="A") is None


def test_a_single_wolf_decides():
    assert rules.resolve_wolf_choice({"A": "Bob"}, lead="A") == "Bob"


# --- the night in a game ----------------------------------------------------------------

NAMES = ["Wolf1", "Wolf2", "Wolf3", "Bob", "Cy", "Dee"]
ROLES = [Role.WEREWOLF] * 3 + [Role.VILLAGER] * 3


def scripted_game(answers):
    """Game with 3 wolves and 3 villagers; `answers(messages)` is the fake model."""
    game = WerewolfGame(num_players=6, llm=FakeLLMClient(answers))
    game.state = GameState(players=[
        PlayerProfile(id=f"p{i}", name=NAMES[i], sex=Sex.MALE, age=30,
                      personality=BigFive(), role=role) for i, role in enumerate(ROLES)])
    from backend.agents.player_agent import PlayerAgent
    game.player_agents = {p.id: PlayerAgent(p, game.llm) for p in game.state.players}
    wolves = [p.name for p in game.state.players if p.role == Role.WEREWOLF]
    for p in game.state.players:
        if p.role == Role.WEREWOLF:
            game.player_agents[p.id].write_pack([w for w in wolves if w != p.name])
    game.state.day_number = 1
    return game


def by_wolf(proposals):
    """A fake model: each wolf answers its night question with the target from `proposals`."""
    def respond(messages):
        text = messages[-1].content
        if "Pack talk so far" in text:                      # the private talk
            return "Let us pick someone quiet."
        for wolf, target in proposals.items():
            if f"You are {wolf}" in messages[0].content or wolf in messages[0].content.split("\n")[0]:
                return target
        return "Bob"
    return respond


def test_the_victim_is_the_majority_of_the_pack():
    game = scripted_game(by_wolf({"Wolf1": "Bob", "Wolf2": "Cy", "Wolf3": "Bob"}))
    assert game._wolf_night().name == "Bob"


def test_a_tie_is_broken_by_the_lead_wolf_who_rotates_each_night():
    proposals = {"Wolf1": "Bob", "Wolf2": "Cy", "Wolf3": "Dee"}
    game = scripted_game(by_wolf(proposals))
    game.state.day_number = 1                      # lead = Wolf1
    assert game._wolf_night().name == "Bob"
    game.state.day_number = 2                      # lead = Wolf2
    assert game._wolf_night().name == "Cy"
    game.state.day_number = 3                      # lead = Wolf3
    assert game._wolf_night().name == "Dee"


def test_wolves_never_target_their_mates():
    game = scripted_game(by_wolf({"Wolf1": "Wolf2", "Wolf2": "Wolf3", "Wolf3": "Wolf1"}))
    for _ in range(20):                            # unusable proposals fall back to a random villager
        assert game._wolf_night().role == Role.VILLAGER
    wolf = game.state.players[0]
    assert set(rules.valid_night_targets(game.state, wolf)) == {"Bob", "Cy", "Dee"}


def test_every_wolf_writes_the_agreed_plan_in_its_diary():
    game = scripted_game(by_wolf({"Wolf1": "Bob", "Wolf2": "Bob", "Wolf3": "Bob"}))
    game._wolf_night()
    for p in game.state.players[:3]:
        plan = game.player_agents[p.id].diary[-1]
        assert plan["kind"] == "plan" and plan["data"] == {"victim": "Bob"} and plan["step"] == "Night 1"
    assert all(not game.player_agents[p.id].diary for p in game.state.players[3:])


def test_the_pack_talk_is_private_and_reaches_the_night_question():
    game = scripted_game(by_wolf({"Wolf1": "Bob", "Wolf2": "Bob", "Wolf3": "Bob"}))
    game._wolf_night()
    assert len(game.state.wolf_log) == 3 and game.state.wolf_log[0].startswith("Night 1: [Wolf1]")
    assert not any("Let us pick someone quiet" in line for line in game.state.game_log)
    night_questions = [m[-1].content for m, _ in game.llm.calls if "private talk tonight" in m[-1].content]
    assert len(night_questions) == 3 and "[Wolf1] Let us pick someone quiet." in night_questions[-1]


def test_wolf_chat_prompts_never_reach_a_villager():
    game = scripted_game(by_wolf({"Wolf1": "Bob", "Wolf2": "Bob", "Wolf3": "Bob"}))
    game._wolf_night()
    game.player_agents["p3"].discuss("[Wolf1] hello", NAMES)       # a villager speaks afterwards
    assert "Let us pick someone quiet" not in game.llm.last_messages[-1].content
    assert "private talk" not in game.llm.last_messages[-1].content


def test_no_chat_rounds_means_no_talk(monkeypatch):
    monkeypatch.setenv("WOLF_CHAT_ROUNDS", "0")
    from backend.config import get_settings
    get_settings.cache_clear()
    try:
        game = scripted_game(by_wolf({"Wolf1": "Bob", "Wolf2": "Bob", "Wolf3": "Bob"}))
        game._wolf_night()
        assert game.state.wolf_log == []
    finally:
        get_settings.cache_clear()


def test_a_lone_wolf_still_chooses_without_a_chat():
    game = scripted_game(by_wolf({"Wolf1": "Cy"}))
    game.state.players = [p for p in game.state.players if p.name in ("Wolf1", "Bob", "Cy", "Dee")]
    assert game._wolf_night().name == "Cy" and game.state.wolf_log == []


def test_after_setup_every_wolf_has_a_pack_entry_with_exactly_its_real_mates():
    game = WerewolfGame(num_players=12, llm=FakeLLMClient("x"))
    game.setup_game()
    game.start_night()
    wolves = [p for p in game.state.players if p.role == Role.WEREWOLF]
    for wolf in wolves:
        packs = [e for e in game.player_agents[wolf.id].diary if e["kind"] == "pack"]
        assert len(packs) == 1
        assert packs[0]["data"]["mates"] == [w.name for w in wolves if w.id != wolf.id]


def test_the_whole_night_still_works_with_the_pack():
    game = WerewolfGame(num_players=12, llm=FakeLLMClient("Bob"))
    game.setup_game()
    game.start_night()
    results = game.process_night_actions()
    assert "deaths" in results


# --- API -------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(state, "sessions", SessionManager())
    with patch("backend.api.games.create_llm_client", return_value=FakeLLMClient("Bob looks odd.")):
        with TestClient(main.app) as test_client:
            yield test_client


def test_the_wolf_talk_is_not_in_the_public_state(client):
    game_id = client.post("/api/games", json={"num_players": 8}).json()["game_id"]
    client.post(f"/api/games/{game_id}/start")
    client.post(f"/api/games/{game_id}/next-phase")
    body = client.get(f"/api/games/{game_id}").json()
    assert "wolf_log" not in body
    assert not any("pack's private" in line for line in body["game_log"])


def test_the_wolf_talk_is_shown_in_spectator_mode(client, monkeypatch):
    from backend.api import games
    game_id = client.post("/api/games", json={"num_players": 8}).json()["game_id"]
    client.post(f"/api/games/{game_id}/start")
    client.post(f"/api/games/{game_id}/next-phase")
    monkeypatch.setattr(games, "get_settings", lambda: type("S", (), {"reveal_roles": True})())
    assert "wolf_log" in client.get(f"/api/games/{game_id}").json()
