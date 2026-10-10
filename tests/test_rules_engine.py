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
    assert counts[Role.VILLAGER] == 24 - 4 - 4
    assert Role.CUPID not in counts if hasattr(Role, 'CUPID') else True
    for special in (Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD):
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
    results = rules.resolve_night(state, {Role.WEREWOLF: by_name(state, "P1"), Role.SEER: by_name(state, "P0")})
    assert results['killed'] == "p1"
    assert results['deaths'] == ["p1"]
    assert by_name(state, "P1").status == PlayerStatus.DEAD
    assert state.eliminated_players == ["p1"]
    assert results['seer_check'] == {'player': "P0", 'role': "werewolf"}
    assert state.night_actions is results
    assert rules.describe_night(state) == "P1 was killed."


def test_resolve_night_guard_saves_victim():
    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.GUARD])
    victim = by_name(state, "P1")
    results = rules.resolve_night(state, {Role.WEREWOLF: victim, Role.GUARD: victim})
    assert victim.status == PlayerStatus.ALIVE
    assert state.eliminated_players == []
    assert results['killed'] == "p1" and results['protected'] == "p1"
    assert results['deaths'] == []
    assert rules.describe_night(state) == "No one was killed."


def test_resolve_night_guard_protecting_someone_else_does_not_save_victim():
    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.GUARD])
    rules.resolve_night(state, {Role.WEREWOLF: by_name(state, "P1"), Role.GUARD: by_name(state, "P2")})
    assert by_name(state, "P1").status == PlayerStatus.DEAD


def test_resolve_night_ignores_werewolf_victim_and_no_victim():
    state = make_state([Role.WEREWOLF, Role.WEREWOLF, Role.VILLAGER])
    assert rules.resolve_night(state, {Role.WEREWOLF: by_name(state, "P1")})['killed'] is None
    assert rules.resolve_night(state, {})['killed'] is None
    assert all(p.status == PlayerStatus.ALIVE for p in state.players)


def test_kill_player_twice_is_a_no_op():
    state = make_state([Role.WEREWOLF, Role.VILLAGER])
    victim = by_name(state, "P1")
    assert rules.kill_player(state, victim) == [victim]
    assert rules.kill_player(state, victim) == []
    assert state.eliminated_players == ["p1"]


# --- witch, hunter, guard -----------------------------------------------------

def witch_state():
    return make_state([Role.WEREWOLF, Role.WITCH, Role.VILLAGER, Role.GUARD, Role.HUNTER])


def test_witch_heal_saves_the_victim_once():
    state = witch_state()
    victim = by_name(state, "P2")
    results = rules.resolve_night(state, {Role.WEREWOLF: victim}, witch_save=True)
    assert results['witch_saved'] and results['deaths'] == []
    assert victim.status == PlayerStatus.ALIVE and state.witch_heal_used
    # the potion is gone: a second attempt does nothing
    results = rules.resolve_night(state, {Role.WEREWOLF: victim}, witch_save=True)
    assert not results['witch_saved'] and results['deaths'] == ["p2"]


def test_witch_heal_is_not_used_when_the_guard_already_protects():
    state = witch_state()
    victim = by_name(state, "P2")
    results = rules.resolve_night(state, {Role.WEREWOLF: victim, Role.GUARD: victim}, witch_save=True)
    assert not results['witch_saved'] and not state.witch_heal_used
    assert victim.status == PlayerStatus.ALIVE


def test_witch_heal_without_victim_does_nothing():
    state = witch_state()
    assert not rules.resolve_night(state, {}, witch_save=True)['witch_saved']
    assert not state.witch_heal_used


def test_witch_poison_kills_once():
    state = witch_state()
    results = rules.resolve_night(state, {}, witch_poison=by_name(state, "P2"))
    assert results['witch_killed'] == "p2" and results['deaths'] == ["p2"]
    assert state.witch_poison_used
    results = rules.resolve_night(state, {}, witch_poison=by_name(state, "P3"))
    assert results['witch_killed'] is None and by_name(state, "P3").status == PlayerStatus.ALIVE


def test_witch_poison_ignores_dead_players_and_stacks_with_the_werewolf_kill():
    state = witch_state()
    by_name(state, "P4").status = PlayerStatus.DEAD
    assert rules.resolve_night(state, {}, witch_poison=by_name(state, "P4"))['witch_killed'] is None
    assert not state.witch_poison_used
    results = rules.resolve_night(state, {Role.WEREWOLF: by_name(state, "P2")},
                                  witch_poison=by_name(state, "P3"))
    assert results['deaths'] == ["p2", "p3"]
    assert rules.describe_night(state) == "P2 was killed. P3 was killed."


def test_witch_options():
    state = witch_state()
    victim = by_name(state, "P2")
    options = rules.witch_options(state, victim)
    assert options['can_save'] and options['can_poison']
    assert "P1" not in options['poison_targets'] and "P2" in options['poison_targets']
    assert not rules.witch_options(state, None)['can_save']
    state.witch_heal_used = state.witch_poison_used = True
    options = rules.witch_options(state, victim)
    assert not options['can_save'] and not options['can_poison']


def test_guard_protection_is_remembered_for_the_next_night():
    state = witch_state()
    rules.resolve_night(state, {Role.GUARD: by_name(state, "P2")})
    assert state.guard_last_protected == "p2"
    assert "P2" not in rules.valid_night_targets(state, by_name(state, "P3"))
    rules.resolve_night(state, {})
    assert state.guard_last_protected is None


def test_hunter_death_shot():
    state = witch_state()
    hunter = by_name(state, "P4")
    results = rules.resolve_night(state, {Role.WEREWOLF: hunter})
    died = [by_name(state, pid) for pid in results['deaths']]
    assert rules.dead_hunters(died) == [hunter]
    assert rules.dead_hunters([by_name(state, "P2")]) == []
    assert "P4" not in rules.hunter_targets(state)
    victim = by_name(state, "P0")
    assert rules.hunter_shoot(state, victim) == [victim]
    assert victim.status == PlayerStatus.DEAD
    assert rules.hunter_shoot(state, victim) == []
    results['hunter_shots'].append(("p4", "p0"))
    assert rules.describe_night(state) == "P4 was killed. P4 was the hunter and shot P0."


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

def shoot_hunters(state, died, rng):
    """Every dead hunter shoots a random living player (chains included)"""
    pending = rules.dead_hunters([p for p in died if p])
    while pending:
        pending.pop(0)
        targets = rules.hunter_targets(state)
        if targets:
            pending += rules.dead_hunters(rules.hunter_shoot(state, by_name(state, rng.choice(targets))))


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
        victim = picks[Role.WEREWOLF]
        poison = None
        if any(p.role == Role.WITCH for p in rules.alive_players(state)):
            options = rules.witch_options(state, victim)
            if options['can_poison'] and rng.random() < 0.5:
                poison = by_name(state, rng.choice(options['poison_targets']))
        results = rules.resolve_night(state, picks, witch_save=rng.random() < 0.5, witch_poison=poison)
        shoot_hunters(state, [by_name(state, pid) for pid in results['deaths']], rng)
        if rules.check_win_condition(state):
            continue
        candidates = [p.name for p in rules.alive_players(state)]
        votes = {name: rules.fallback_vote_target(name, candidates, rng) for name in candidates}
        eliminated, _ = rules.resolve_vote(state, votes, rng)
        shoot_hunters(state, [eliminated], rng)
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


# --- exact role tables and invariants (issue #26) -------------------------------------------

EXPECTED_ROLES = {
    6: {Role.WEREWOLF: 2, Role.VILLAGER: 4},
    7: {Role.WEREWOLF: 2, Role.VILLAGER: 5},
    8: {Role.WEREWOLF: 2, Role.SEER: 1, Role.VILLAGER: 5},
    9: {Role.WEREWOLF: 2, Role.SEER: 1, Role.VILLAGER: 6},
    10: {Role.WEREWOLF: 2, Role.SEER: 1, Role.WITCH: 1, Role.VILLAGER: 6},
    11: {Role.WEREWOLF: 2, Role.SEER: 1, Role.WITCH: 1, Role.VILLAGER: 7},
    12: {Role.WEREWOLF: 2, Role.SEER: 1, Role.WITCH: 1, Role.HUNTER: 1, Role.VILLAGER: 7},
}


@pytest.mark.parametrize("n", sorted(EXPECTED_ROLES))
def test_role_distribution_for_6_to_12_players(n):
    assert Counter(rules.distribute_roles(n)) == Counter(EXPECTED_ROLES[n])


def test_special_roles_are_unique():
    for n in range(4, 40):
        counts = Counter(rules.distribute_roles(n))
        for role in (Role.SEER, Role.WITCH, Role.HUNTER, Role.GUARD):
            assert counts[role] <= 1


def test_the_two_teams_cannot_win_at_once():
    """Whatever the number of living werewolves and villagers, at most one team wins"""
    for wolves in range(0, 7):
        for others in range(0, 7):
            if wolves + others == 0:
                continue
            state = make_state([Role.WEREWOLF] * wolves + [Role.VILLAGER] * others)
            winner = rules.check_win_condition(state)
            assert winner in (None, rules.WEREWOLVES, rules.VILLAGERS)
            assert (winner == rules.VILLAGERS) == (wolves == 0)
            assert (winner == rules.WEREWOLVES) == (wolves > 0 and wolves >= others)


def test_ties_are_broken_uniformly():
    wins = Counter()
    for seed in range(600):
        state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.VILLAGER])
        eliminated, _ = rules.resolve_vote(state, {"P0": "P1", "P1": "P2", "P2": "P0"}, random.Random(seed))
        wins[eliminated.name] += 1
    assert set(wins) == {"P0", "P1", "P2"}
    assert min(wins.values()) > 140            # about 200 each


def test_invariants_hold_in_every_step_of_random_games():
    for seed in range(40):
        rng = random.Random(seed)
        state = make_state([None] * 12)
        rules.assign_roles(state.players, rng)
        alive_before = len(rules.alive_players(state))
        for _ in range(30):
            if rules.check_win_condition(state):
                break
            rules.start_night(state)
            wolf = next((p for p in rules.alive_players(state) if p.role == Role.WEREWOLF), None)
            names = rules.valid_night_targets(state, wolf)
            assert all(by_name(state, n).role != Role.WEREWOLF for n in names)   # wolves never target wolves
            victim = by_name(state, rng.choice(names)) if names else None
            results = rules.resolve_night(state, {Role.WEREWOLF: victim})
            candidates = [p.name for p in rules.alive_players(state)]
            if not candidates or rules.check_win_condition(state):
                continue
            votes = {n: rules.fallback_vote_target(n, candidates, rng) for n in candidates}
            rules.resolve_vote(state, {v: t for v, t in votes.items() if t}, rng)
            shoot_hunters(state, [by_name(state, pid) for pid in results['deaths']], rng)
            alive_now = len(rules.alive_players(state))
            assert alive_now <= alive_before                          # nobody comes back to life
            alive_before = alive_now
            dead_ids = {p.id for p in state.players if p.status == PlayerStatus.DEAD}
            assert set(state.eliminated_players) == dead_ids          # bookkeeping matches reality
            assert len(state.eliminated_players) == len(set(state.eliminated_players))
