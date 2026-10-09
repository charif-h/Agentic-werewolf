"""Tests for the pure rules engine: no LLM, no network, no sleeping."""
import random
from collections import Counter

import pytest

from backend.engine import rules
from backend.models.game_models import (
    GamePhase, GameState, PersonalityType, PlayerProfile, PlayerStatus, Role, Sex,
)


def make_state(roles):
    """GameState with players P0..Pn holding the given roles"""
    players = [
        PlayerProfile(id=f"p{i}", name=f"P{i}", sex=Sex.MALE, age=30,
                      personality=PersonalityType.INTJ, role=role)
        for i, role in enumerate(roles)
    ]
    return GameState(players=players)


def by_name(state, name):
    return rules.find_player_by_name(state, name)


# --- roles -------------------------------------------------------------------

@pytest.mark.parametrize("n", range(4, 25))
def test_distribute_roles_has_right_size_and_at_least_two_werewolves(n):
    roles = rules.distribute_roles(n)
    assert len(roles) == n
    assert roles.count(Role.WEREWOLF) == max(2, n // 6)


def test_distribute_roles_24_players():
    counts = Counter(rules.distribute_roles(24))
    assert counts[Role.WEREWOLF] == 4
    assert counts[Role.VILLAGER] == 24 - 4 - 5
    for special in (Role.SEER, Role.WITCH, Role.HUNTER, Role.CUPID, Role.GUARD):
        assert counts[special] == 1


def test_special_roles_unlock_with_player_count():
    assert Role.SEER not in rules.distribute_roles(7)
    assert Role.SEER in rules.distribute_roles(8)
    assert Role.WITCH in rules.distribute_roles(10)
    assert Role.HUNTER in rules.distribute_roles(12)
    assert Role.GUARD not in rules.distribute_roles(15)
    assert Role.GUARD in rules.distribute_roles(16)


def test_assign_roles_is_reproducible_with_a_seed():
    def roles(seed):
        state = make_state([None] * 10)
        rules.assign_roles(state.players, random.Random(seed))
        return [p.role for p in state.players]

    assert roles(1) == roles(1)
    assert Counter(roles(1)) == Counter(rules.distribute_roles(10))


# --- night -------------------------------------------------------------------

def test_valid_night_targets_per_role():
    state = make_state([Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.GUARD, Role.VILLAGER])
    wolf, _, seer, guard, villager = state.players
    assert rules.valid_night_targets(state, wolf) == ["P2", "P3", "P4"]
    assert rules.valid_night_targets(state, seer) == ["P0", "P1", "P3", "P4"]
    assert rules.valid_night_targets(state, guard) == ["P0", "P1", "P2", "P3", "P4"]
    assert rules.valid_night_targets(state, villager) == []
    villager.status = PlayerStatus.DEAD
    assert "P4" not in rules.valid_night_targets(state, wolf)


def test_start_night_increments_day_and_clears_actions():
    state = make_state([Role.WEREWOLF, Role.VILLAGER])
    state.night_actions = {"killed": "x"}
    rules.start_night(state)
    assert (state.day_number, state.phase, state.night_actions) == (1, GamePhase.NIGHT, {})
    rules.start_night(state)
    assert state.day_number == 2


def test_resolve_night_kills_victim():
    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.SEER])
    results = rules.resolve_night(state, by_name(state, "P1"), None, by_name(state, "P0"))
    assert results['killed'] == "p1"
    assert by_name(state, "P1").status == PlayerStatus.DEAD
    assert state.eliminated_players == ["p1"]
    assert results['seer_check'] == {'player': "P0", 'role': "werewolf"}
    assert state.night_actions is results
    assert rules.describe_night(state) == "P1 was killed."


def test_resolve_night_guard_saves_victim():
    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.GUARD])
    victim = by_name(state, "P1")
    results = rules.resolve_night(state, victim, victim, None)
    assert victim.status == PlayerStatus.ALIVE
    assert state.eliminated_players == []
    assert results['killed'] == "p1" and results['protected'] == "p1"
    assert rules.describe_night(state) == "No one was killed."


def test_resolve_night_guard_protecting_someone_else_does_not_save_victim():
    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.GUARD])
    rules.resolve_night(state, by_name(state, "P1"), by_name(state, "P2"), None)
    assert by_name(state, "P1").status == PlayerStatus.DEAD


def test_resolve_night_ignores_werewolf_victim_and_no_victim():
    state = make_state([Role.WEREWOLF, Role.WEREWOLF, Role.VILLAGER])
    assert rules.resolve_night(state, by_name(state, "P1"), None, None)['killed'] is None
    assert rules.resolve_night(state, None, None, None)['killed'] is None
    assert all(p.status == PlayerStatus.ALIVE for p in state.players)


def test_lovers_die_together():
    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER, Role.SEER])
    by_name(state, "P1").in_love_with = "p2"
    by_name(state, "P2").in_love_with = "p1"
    results = rules.resolve_night(state, by_name(state, "P1"), None, None)
    assert results['lover_died'] == "p2"
    assert by_name(state, "P2").status == PlayerStatus.DEAD
    assert rules.describe_night(state) == "P1 was killed. P2 died of heartbreak."


def test_kill_player_twice_is_a_no_op():
    state = make_state([Role.WEREWOLF, Role.VILLAGER])
    victim = by_name(state, "P1")
    assert rules.kill_player(state, victim) == [victim]
    assert rules.kill_player(state, victim) == []
    assert state.eliminated_players == ["p1"]


# --- voting ------------------------------------------------------------------

def test_resolve_vote_eliminates_most_voted():
    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER, Role.SEER])
    votes = {"P0": "P1", "P2": "P1", "P3": "P0", "P1": "P0"}
    eliminated, counts = rules.resolve_vote(state, votes, random.Random(0))
    assert counts == {"P0": 2, "P1": 2, "P2": 0, "P3": 0}
    assert eliminated.name in ("P0", "P1")  # tie
    assert eliminated.status == PlayerStatus.DEAD

    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER, Role.SEER])
    eliminated, counts = rules.resolve_vote(state, {"P0": "P1", "P2": "P1", "P3": "P0"})
    assert eliminated.name == "P1" and counts["P1"] == 2


def test_resolve_vote_tie_break_is_random_and_seedable():
    def winner(seed):
        state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER])
        return rules.resolve_vote(state, {"P0": "P1", "P1": "P0"}, random.Random(seed))[0].name

    assert winner(3) == winner(3)
    assert {winner(s) for s in range(30)} == {"P0", "P1"}


def test_resolve_vote_ignores_unknown_targets_and_no_votes():
    state = make_state([Role.WEREWOLF, Role.VILLAGER])
    eliminated, counts = rules.resolve_vote(state, {"P0": "Nobody"})
    assert sum(counts.values()) == 0
    assert eliminated is not None  # everyone tied at zero: still one elimination


def test_resolve_vote_with_nobody_alive():
    state = make_state([Role.VILLAGER])
    state.players[0].status = PlayerStatus.DEAD
    assert rules.resolve_vote(state, {}) == (None, {})


# --- win conditions ----------------------------------------------------------

@pytest.mark.parametrize("roles,dead,expected", [
    ([Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER], [], None),
    ([Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER], [0], "villagers"),
    ([Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER], [1], "werewolves"),   # 1 wolf vs 1 villager
    ([Role.WEREWOLF, Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER, Role.SEER], [], None),
    ([Role.WEREWOLF, Role.WEREWOLF, Role.VILLAGER, Role.SEER], [], "werewolves"),
])
def test_check_win_condition(roles, dead, expected):
    state = make_state(roles)
    for i in dead:
        state.players[i].status = PlayerStatus.DEAD
    assert rules.check_win_condition(state) == expected


def test_end_game_returns_survivors():
    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER])
    state.players[1].status = PlayerStatus.DEAD
    assert rules.end_game(state) == ["P0", "P2"]
    assert state.phase == GamePhase.ENDED


# --- whole games without any LLM ----------------------------------------------

def play_random_game(num_players, seed):
    """Play a complete game using only the engine and random decisions"""
    rng = random.Random(seed)
    state = make_state([None] * num_players)
    rules.assign_roles(state.players, rng)
    for _ in range(num_players * 2):  # a game cannot last longer than that
        winner = rules.check_win_condition(state)
        if winner:
            return state, winner
        rules.start_night(state)
        actors = {role: next((p for p in rules.alive_players(state) if p.role == role), None)
                  for role in (Role.WEREWOLF, Role.GUARD, Role.SEER)}
        picks = {}
        for role, actor in actors.items():
            names = rules.valid_night_targets(state, actor) if actor else []
            picks[role] = by_name(state, rng.choice(names)) if names else None
        rules.resolve_night(state, picks[Role.WEREWOLF], picks[Role.GUARD], picks[Role.SEER])
        if rules.check_win_condition(state):
            continue
        candidates = [p.name for p in rules.alive_players(state)]
        votes = {name: rules.fallback_vote_target(name, candidates, rng) for name in candidates}
        rules.resolve_vote(state, votes, rng)
    raise AssertionError("game did not terminate")


@pytest.mark.parametrize("num_players", [4, 6, 8, 12, 16, 24])
def test_random_games_always_terminate_with_a_winner(num_players):
    for seed in range(25):
        state, winner = play_random_game(num_players, seed)
        assert winner in (rules.WEREWOLVES, rules.VILLAGERS)
        alive = rules.alive_players(state)
        wolves = [p for p in alive if p.role == Role.WEREWOLF]
        if winner == rules.VILLAGERS:
            assert not wolves
        else:
            assert len(wolves) >= len(alive) - len(wolves)
        assert len(state.eliminated_players) == num_players - len(alive)
        assert len(set(state.eliminated_players)) == len(state.eliminated_players)


def test_engine_is_deterministic_for_a_seed():
    a, b = play_random_game(12, 7), play_random_game(12, 7)
    assert a[1] == b[1]
    assert a[0].eliminated_players == b[0].eliminated_players


def test_engine_module_does_no_io():
    import inspect
    source = inspect.getsource(rules)
    for forbidden in ("print(", "time.sleep", "import time", "langchain", "requests", "open("):
        assert forbidden not in source
