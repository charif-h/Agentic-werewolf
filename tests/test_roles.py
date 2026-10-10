"""Tests for the role registry and role handlers."""
import pytest

from backend.models.game_models import (
    GameState, PersonalityType, PlayerProfile, PlayerStatus, Role, Sex,
)
from backend.roles import (
    VILLAGERS, WEREWOLVES, RoleHandler, all_handlers, get_handler, night_handlers,
)
from backend.roles import registry


def make_state(roles):
    return GameState(players=[
        PlayerProfile(id=f"p{i}", name=f"P{i}", sex=Sex.MALE, age=30,
                      personality=PersonalityType.INTJ, role=role)
        for i, role in enumerate(roles)
    ])


@pytest.mark.parametrize("role", list(Role))
def test_every_role_has_a_handler_with_prompts(role):
    handler = get_handler(role)
    assert handler.role == role
    assert handler.description.startswith("You are")
    assert handler.discussion_strategy and handler.voting_strategy


def test_registry_has_exactly_one_handler_per_role():
    assert {h.role for h in all_handlers()} == set(Role)
    assert len(all_handlers()) == len(Role)


def test_missing_role_is_treated_as_villager():
    assert get_handler(None).role == Role.VILLAGER


def test_teams():
    assert get_handler(Role.WEREWOLF).team == WEREWOLVES
    for role in Role:
        if role != Role.WEREWOLF:
            assert get_handler(role).team == VILLAGERS


def test_night_roles_in_acting_order():
    assert [h.role for h in night_handlers()] == [Role.WEREWOLF, Role.GUARD, Role.SEER]
    assert all(h.night_instruction for h in night_handlers())
    for role in (Role.VILLAGER, Role.WITCH, Role.HUNTER):
        assert not get_handler(role).acts_at_night


def test_night_targets_per_role():
    state = make_state([Role.WEREWOLF, Role.WEREWOLF, Role.SEER, Role.GUARD, Role.VILLAGER])
    wolf, _, seer, guard, villager = state.players
    assert get_handler(Role.WEREWOLF).night_targets(state, wolf) == ["P2", "P3", "P4"]
    assert get_handler(Role.SEER).night_targets(state, seer) == ["P0", "P1", "P3", "P4"]
    assert get_handler(Role.GUARD).night_targets(state, guard) == ["P0", "P1", "P2", "P3", "P4"]
    assert get_handler(Role.VILLAGER).night_targets(state, villager) == []
    villager.status = PlayerStatus.DEAD
    assert "P4" not in get_handler(Role.WEREWOLF).night_targets(state, wolf)


def test_record_night():
    state = make_state([Role.WEREWOLF, Role.VILLAGER, Role.SEER])
    wolf, villager, seer = state.players
    results = {}
    get_handler(Role.WEREWOLF).record_night(results, villager)
    get_handler(Role.WEREWOLF).record_night(results, wolf)  # ignored: werewolves cannot kill each other
    get_handler(Role.GUARD).record_night(results, seer)
    get_handler(Role.SEER).record_night(results, wolf)
    assert results == {'killed': "p1", 'protected': "p2",
                       'seer_check': {'player': "P0", 'role': "werewolf"}}


def test_night_prompt():
    assert get_handler(Role.GUARD).night_prompt(["Bob", "Cy"]) == (
        "As the guard, choose a player to protect tonight from these players: Bob, Cy. "
        'Answer in JSON: {"target": "<name>"}.')
    assert get_handler(Role.WEREWOLF).night_prompt([]).endswith(
        'You cannot target other werewolves. Answer in JSON: {"target": "<name>"}.')


def test_hunter_has_a_death_shot():
    assert get_handler(Role.HUNTER).death_shot
    assert get_handler(Role.HUNTER).death_shot_instruction
    assert not any(get_handler(r).death_shot for r in Role if r != Role.HUNTER)


def test_guard_cannot_protect_the_same_player_twice_in_a_row():
    state = make_state([Role.GUARD, Role.VILLAGER, Role.VILLAGER])
    guard = state.players[0]
    assert get_handler(Role.GUARD).night_targets(state, guard) == ["P0", "P1", "P2"]
    state.guard_last_protected = "p1"
    assert get_handler(Role.GUARD).night_targets(state, guard) == ["P0", "P2"]


def test_werewolf_specifics():
    wolf = get_handler(Role.WEREWOLF)
    assert wolf.announce_night_choice
    assert "WEREWOLF" in wolf.voting_strategy
    assert "VILLAGE TEAM" in get_handler(Role.SEER).voting_strategy


def test_adding_a_role_is_one_registered_class():
    original = get_handler(Role.WITCH)

    @registry.register
    class NightWitch(RoleHandler):
        role = Role.WITCH
        description = "You are the WITCH (test)."
        night_order = 5
        night_instruction = "As the witch, choose someone"

        def night_targets(self, state, actor):
            return ["X"]

    try:
        assert get_handler(Role.WITCH).description == "You are the WITCH (test)."
        assert [h.role for h in night_handlers()][0] == Role.WITCH  # order 5 acts first
    finally:
        registry._HANDLERS[Role.WITCH] = original
    assert [h.role for h in night_handlers()][0] == Role.WEREWOLF
