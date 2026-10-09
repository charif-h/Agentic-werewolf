"""Tests for free-text target parsing and night-action target selection (fake LLM)."""
from unittest.mock import MagicMock

from backend.game.game_logic import WerewolfGame
from backend.game.targets import match_player_name, pick_target
from backend.models.game_models import (
    GameState, PersonalityType, PlayerProfile, PlayerStatus, Role, Sex,
)

NAMES = ["Ann", "Bob", "Joanna"]


def test_match_exact_ignores_case_and_punctuation():
    assert match_player_name("bob", NAMES) == "Bob"
    assert match_player_name("  \"Bob.\"\n", NAMES) == "Bob"


def test_match_inside_sentence():
    assert match_player_name("I choose Bob tonight, he is suspicious.", NAMES) == "Bob"


def test_match_uses_whole_words_only():
    # "Ann" is a substring of "Joanna" but must not match it
    assert match_player_name("Joanna", NAMES) == "Joanna"
    assert match_player_name("Joanna seems odd", ["Ann", "Joanna"]) == "Joanna"
    assert match_player_name("Hannah", ["Ann"]) is None


def test_match_first_mentioned_wins():
    assert match_player_name("Bob, not Ann", NAMES) == "Bob"


def test_match_none_and_empty():
    assert match_player_name(None, NAMES) is None
    assert match_player_name("   ", NAMES) is None
    assert match_player_name("nobody", NAMES) is None


def test_pick_target_random_fallback_covers_all_candidates():
    seen = {pick_target("???", NAMES) for _ in range(200)}
    assert seen == set(NAMES)  # not biased to the first name
    assert pick_target(None, []) is None


def make_game():
    game = WerewolfGame.__new__(WerewolfGame)
    game.state = GameState()
    game.state.players = [
        PlayerProfile(id=f"p{i}", name=n, sex=Sex.MALE, age=30,
                      personality=PersonalityType.INTJ, role=r)
        for i, (n, r) in enumerate([("Wolf", Role.WEREWOLF), ("Bob", Role.VILLAGER),
                                    ("Cy", Role.SEER)])
    ]
    game.player_agents = {}
    return game


def agent_returning(answer):
    agent = MagicMock()
    if isinstance(answer, Exception):
        agent.night_action.side_effect = answer
    else:
        agent.night_action.return_value = answer
    return agent


def test_choose_night_target_handles_none_answer():
    game = make_game()
    wolf = game.state.players[0]
    game.player_agents[wolf.id] = agent_returning(None)  # used to crash on None.lower()
    assert game._choose_night_target(wolf).name in ("Bob", "Cy")


def test_choose_night_target_parses_sentence():
    game = make_game()
    wolf = game.state.players[0]
    game.player_agents[wolf.id] = agent_returning("I will eliminate Cy.")
    assert game._choose_night_target(wolf).name == "Cy"


def test_choose_night_target_rejects_invalid_name():
    game = make_game()
    wolf = game.state.players[0]
    game.player_agents[wolf.id] = agent_returning("Wolf")  # a werewolf is not a valid target
    for _ in range(50):
        assert game._choose_night_target(wolf).name in ("Bob", "Cy")


def test_choose_night_target_survives_llm_error():
    game = make_game()
    wolf = game.state.players[0]
    game.player_agents[wolf.id] = agent_returning(RuntimeError("boom"))
    assert game._choose_night_target(wolf).name in ("Bob", "Cy")


def test_choose_night_target_no_valid_names():
    game = make_game()
    for p in game.state.players[1:]:
        p.status = PlayerStatus.DEAD
    assert game._choose_night_target(game.state.players[0]) is None
    assert game._choose_night_target(None) is None


def test_seer_prompt_lists_valid_targets_without_self():
    game = make_game()
    seer = game.state.players[2]
    agent = agent_returning("Bob")
    game.player_agents[seer.id] = agent
    assert game._choose_night_target(seer).name == "Bob"
    assert agent.night_action.call_args[0][0]['valid_targets'] == ["Wolf", "Bob"]
