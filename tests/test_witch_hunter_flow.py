"""Witch, hunter, seer and werewolf knowledge as played by WerewolfGame (fake agents, no LLM)."""
from unittest.mock import MagicMock

import pytest

from backend import prompts
from backend.llm import FakeLLMClient
from backend.agents.player_agent import PlayerAgent
from backend.game.game_logic import WerewolfGame
from backend.game.targets import parse_witch_answer
from backend.models.game_models import (
    GameState, PersonalityType, PlayerProfile, PlayerStatus, Role, Sex,
)

POISON_TARGETS = ["Bob", "Cy"]


# --- parsing the witch's answer ----------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("SAVE", (True, None)),
    ("save", (True, None)),
    ("PASS", (False, None)),
    ("POISON Bob", (False, "Bob")),
    ("I will poison cy.", (False, "Cy")),
    ("SAVE and POISON Bob", (True, "Bob")),
    ("POISON nobody", (False, None)),
    ("hmm, not sure", (False, None)),
    ("", (False, None)),
    (None, (False, None)),
])
def test_parse_witch_answer(text, expected):
    assert parse_witch_answer(text, True, True, POISON_TARGETS) == expected


def test_parse_witch_answer_respects_available_potions():
    assert parse_witch_answer("SAVE", False, True, POISON_TARGETS) == (False, None)
    assert parse_witch_answer("POISON Bob", True, False, POISON_TARGETS) == (False, None)


# --- helpers --------------------------------------------------------------------

def make_game(roles):
    """WerewolfGame with named players and MagicMock agents (no LLM)"""
    game = WerewolfGame.__new__(WerewolfGame)
    names = ["Wolf", "Bob", "Cy", "Dee", "Eli", "Fay", "Gus"]
    game.state = GameState(players=[
        PlayerProfile(id=f"p{i}", name=names[i], sex=Sex.MALE, age=30,
                      personality=PersonalityType.INTJ, role=role)
        for i, role in enumerate(roles)
    ])
    game.player_agents = {p.id: MagicMock() for p in game.state.players}
    for agent in game.player_agents.values():
        agent.night_action.return_value = None
    game.game_master = WerewolfGame.__init__.__globals__["GameMaster"]()
    game.state.day_number = 1
    return game


def player(game, name):
    return next(p for p in game.state.players if p.name == name)


def agent(game, name):
    return game.player_agents[player(game, name).id]


# --- witch -----------------------------------------------------------------------

def witch_game():
    return make_game([Role.WEREWOLF, Role.WITCH, Role.VILLAGER, Role.SEER, Role.WEREWOLF])


def test_witch_saves_the_victim():
    game = witch_game()
    agent(game, "Wolf").night_action.return_value = "Cy"
    agent(game, "Bob").witch_action.return_value = "SAVE"
    results = game.process_night_actions()
    assert results['witch_saved'] and results['deaths'] == []
    assert player(game, "Cy").status == PlayerStatus.ALIVE
    assert game.state.witch_heal_used
    # the witch was told who was attacked, and remembers what she did
    args = agent(game, "Bob").witch_action.call_args[0]
    assert args[1:3] == ("Cy", True)
    assert any("save Cy" in fact for fact in [c[0][0] for c in agent(game, "Bob").add_knowledge.call_args_list])


def test_witch_poisons_someone():
    game = witch_game()
    agent(game, "Wolf").night_action.return_value = "Cy"
    agent(game, "Bob").witch_action.return_value = "POISON Dee"
    results = game.process_night_actions()
    assert results['deaths'] == ["p2", "p3"]
    assert player(game, "Dee").status == PlayerStatus.DEAD
    assert game.state.witch_poison_used
    assert "Cy was killed. Dee was killed." in __import__("backend.engine.rules", fromlist=["x"]).describe_night(game.state)


def test_witch_error_or_unclear_answer_does_nothing():
    for behavior in (RuntimeError("boom"), "no idea"):
        game = witch_game()
        agent(game, "Wolf").night_action.return_value = "Cy"
        if isinstance(behavior, Exception):
            agent(game, "Bob").witch_action.side_effect = behavior
        else:
            agent(game, "Bob").witch_action.return_value = behavior
        results = game.process_night_actions()
        assert results['deaths'] == ["p2"]
        assert not game.state.witch_heal_used and not game.state.witch_poison_used


def test_witch_is_not_asked_when_both_potions_are_used():
    game = witch_game()
    game.state.witch_heal_used = game.state.witch_poison_used = True
    game.process_night_actions()
    agent(game, "Bob").witch_action.assert_not_called()


def test_dead_witch_is_not_asked():
    game = witch_game()
    player(game, "Bob").status = PlayerStatus.DEAD
    game.process_night_actions()
    agent(game, "Bob").witch_action.assert_not_called()


# --- seer and werewolves remember ---------------------------------------------------

def test_seer_learns_what_they_saw():
    game = witch_game()
    agent(game, "Wolf").night_action.return_value = "Cy"
    agent(game, "Cy").night_action.return_value = "Wolf"
    seer = next(p for p in game.state.players if p.role == Role.SEER)
    game.player_agents[seer.id].night_action.return_value = "Wolf"
    agent(game, "Bob").witch_action.return_value = "PASS"
    game.process_night_actions()
    facts = [c[0][0] for c in game.player_agents[seer.id].add_knowledge.call_args_list]
    assert facts == ["Night 1: you saw that Wolf is a werewolf."]


def test_werewolves_learn_their_teammates_at_setup():
    game = WerewolfGame(num_players=12, llm=FakeLLMClient("x"))
    game.setup_game()
    wolves = [p for p in game.state.players if p.role == Role.WEREWOLF]
    assert len(wolves) == 2
    for wolf in wolves:
        mate = next(w for w in wolves if w.id != wolf.id)
        assert game.player_agents[wolf.id].knowledge == [f"The other werewolves are: {mate.name}."]
    others = [p for p in game.state.players if p.role != Role.WEREWOLF]
    assert all(game.player_agents[p.id].knowledge == [] for p in others)


# --- hunter ------------------------------------------------------------------------

def hunter_game():
    return make_game([Role.WEREWOLF, Role.HUNTER, Role.VILLAGER, Role.VILLAGER, Role.SEER])


def test_hunter_killed_at_night_shoots():
    game = hunter_game()
    agent(game, "Wolf").night_action.return_value = "Bob"      # Bob is the hunter
    agent(game, "Bob").hunter_shot.return_value = "Wolf"
    results = game.process_night_actions()
    assert results['deaths'] == ["p1"]
    assert results['hunter_shots'] == [("p1", "p0")]
    assert player(game, "Wolf").status == PlayerStatus.DEAD
    assert "Wolf" in agent(game, "Bob").hunter_shot.call_args[0][1]
    assert "Bob" not in agent(game, "Bob").hunter_shot.call_args[0][1]
    assert any("Bob was the hunter and shoots Wolf" in line for line in game.state.game_log)
    assert "Bob was the hunter and shot Wolf" in game.start_day()


def test_hunter_shot_with_unclear_answer_picks_a_random_valid_target():
    game = hunter_game()
    agent(game, "Wolf").night_action.return_value = "Bob"
    agent(game, "Bob").hunter_shot.return_value = "dunno"
    results = game.process_night_actions()
    (_, target_id), = results['hunter_shots']
    assert target_id != "p1" and next(p for p in game.state.players if p.id == target_id).status == PlayerStatus.DEAD


def test_hunter_shot_survives_llm_error():
    game = hunter_game()
    agent(game, "Wolf").night_action.return_value = "Bob"
    agent(game, "Bob").hunter_shot.side_effect = RuntimeError("boom")
    results = game.process_night_actions()
    assert len(results['hunter_shots']) == 1


def test_hunter_voted_out_shoots(monkeypatch):
    game = hunter_game()
    for p in game.state.players:
        game.player_agents[p.id].vote.return_value = "Bob"
    game.player_agents[player(game, "Bob").id].vote.return_value = "Cy"
    agent(game, "Bob").hunter_shot.return_value = "Wolf"
    eliminated, counts = game.conduct_vote()
    assert eliminated.name == "Bob"
    assert player(game, "Wolf").status == PlayerStatus.DEAD
    assert game.check_win_condition() == "villagers"


def test_two_hunter_chain_cannot_loop_forever():
    game = make_game([Role.WEREWOLF, Role.HUNTER, Role.HUNTER, Role.VILLAGER, Role.VILLAGER])
    first, second = player(game, "Bob"), player(game, "Cy")
    for name in ("Bob", "Cy"):
        agent(game, name).hunter_shot.return_value = "Bob" if name == "Cy" else "Cy"
    from backend.engine import rules
    died = rules.kill_player(game.state, first)
    shots = []
    killed = game._resolve_hunter_shots(died, shots)
    # Bob shoots Cy; Cy then shoots too. Bob is already dead, so Cy's answer is invalid
    # and a random living player is hit instead.
    assert len(shots) == 2 and shots[0] == ("p1", "p2") and shots[1][0] == "p2"
    assert shots[1][1] not in ("p1", "p2")
    assert second.status == PlayerStatus.DEAD and killed[0] is second and len(killed) == 2


# --- prompts --------------------------------------------------------------------------

def test_knowledge_appears_in_prompts_only_when_present():
    assert prompts.knowledge_block([]) == ""
    block = prompts.knowledge_block(["a fact"])
    assert "WHAT YOU KNOW" in block and "- a fact" in block
    plain = prompts.discussion_prompt("Ann", "", ["Ann"], "seer", "S", "F")
    rich = prompts.discussion_prompt("Ann", "", ["Ann"], "seer", "S", "F", ["Cy is a werewolf."])
    assert "WHAT YOU KNOW" not in plain and "- Cy is a werewolf.\n\nRESPONSE FACTORS" in rich
    assert "- Cy is a werewolf." in prompts.vote_prompt("Ann", "seer", "V", "talk", ["Cy"], ["Cy is a werewolf."])
    assert "- Cy is a werewolf." in prompts.player_system_prompt(
        "Ann", 30, "female", "INTJ", "d", "role", ["Cy is a werewolf."])


def test_witch_and_hunter_prompts():
    text = prompts.witch_prompt("Cy", True, True, ["Bob", "Cy"])
    assert "attacked Cy" in text and "SAVE" in text and "POISON <name>" in text and "PASS" in text
    only_pass = prompts.witch_prompt(None, False, False, [])
    assert "nobody was attacked" in only_pass and "SAVE" not in only_pass and "POISON" not in only_pass
    assert prompts.hunter_prompt("Shoot", ["Bob", "Cy"]) == (
        "Shoot from these players: Bob, Cy. Respond with ONLY the player's name.")


def test_agent_remembers_facts_and_uses_them_in_every_prompt():
    profile = PlayerProfile(id="p", name="Ann", sex=Sex.FEMALE, age=30,
                            personality=PersonalityType.INTJ, role=Role.SEER)
    agent_ = PlayerAgent(profile, FakeLLMClient("Bob"))
    agent_.add_knowledge("Night 1: you saw that Bob is a werewolf.")
    agent_.discuss("[Bob] hi", ["Ann", "Bob"])
    agent_.vote("[Bob] hi", ["Ann", "Bob"])
    agent_.night_action({'valid_targets': ['Bob']})
    discussion, vote, night = (messages for messages, _ in agent_.llm.calls)
    assert "Bob is a werewolf" in discussion[-1].content
    assert "Bob is a werewolf" in vote[-1].content
    assert "Bob is a werewolf" in night[0].content   # system prompt
