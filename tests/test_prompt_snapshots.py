"""
Snapshot tests: the exact text of every prompt the game sends.

If you change a prompt on purpose, regenerate the files and review the diff:

    UPDATE_SNAPSHOTS=1 python -m pytest tests/test_prompt_snapshots.py

Any other failure means a prompt changed by accident.
"""
import os
from pathlib import Path

import pytest

from backend.agents.player_agent import PlayerAgent
from backend.llm import FakeLLMClient, to_alternating
from backend.models.game_models import PersonalityType, PlayerProfile, Role, Sex
from backend.roles import all_handlers

SNAPSHOTS = Path(__file__).parent / "snapshots"
SEPARATOR = "\n\n" + "=" * 70 + "\n"

CONVERSATION = ("[Bob] I slept badly. Does anyone know what happened to Hal?\n"
                "[Cy] Hal was killed. Ann, you were awake last night.\n"
                "[Dee] Eli has been very quiet since the start.")
NAMES = ["Ann", "Bob", "Cy", "Dee", "Eli"]
GAME_STATE = {
    "phase": "night", "day_number": 2,
    "players": [{"name": n, "status": "alive"} for n in NAMES],
    "recent_events": ["Hal was killed."], "discussion_history": ["[Bob] hello"],
    "valid_targets": ["Bob", "Cy", "Dee", "Eli"],
}


def make_agent(role: Role, knowledge=None) -> PlayerAgent:
    profile = PlayerProfile(id="p0", name="Ann", sex=Sex.FEMALE, age=34,
                            personality=PersonalityType.ENFP, role=role)
    agent = PlayerAgent(profile, FakeLLMClient("Bob"))
    for fact in knowledge or []:
        agent.add_knowledge(fact)
    return agent


def sent(agent: PlayerAgent) -> str:
    """What the model really receives for the last call: the alternating chat after formatting"""
    return "\n---\n".join(f"[{m.role}]\n{m.content}" for m in to_alternating(agent.llm.last_messages))


def roles():
    return sorted((h.role for h in all_handlers()), key=lambda r: r.value)


def build_system_prompts() -> str:
    return SEPARATOR.join(f"### {role.value}\n{make_agent(role)._build_system_prompt()}" for role in roles())


def build_discussion_prompts() -> str:
    parts = []
    for role in roles():
        agent = make_agent(role)
        agent.discuss(CONVERSATION, NAMES)
        parts.append(f"### {role.value}\n{sent(agent)}")
    return SEPARATOR.join(parts)


def build_vote_prompts() -> str:
    parts = []
    for role in roles():
        agent = make_agent(role)
        agent.vote(CONVERSATION, NAMES)
        parts.append(f"### {role.value}\n{sent(agent)}")
    return SEPARATOR.join(parts)


def build_night_prompts() -> str:
    parts = []
    for role in roles():
        agent = make_agent(role)
        if agent.night_action(GAME_STATE) is None and not agent.handler.acts_at_night:
            continue
        parts.append(f"### {role.value}\n{sent(agent)}")
    return SEPARATOR.join(parts)


def build_special_prompts() -> str:
    witch = make_agent(Role.WITCH, ["Night 1: you used your healing potion to save Cy."])
    witch.witch_action(GAME_STATE, "Dee", False, True, ["Bob", "Cy", "Dee", "Eli"])
    hunter = make_agent(Role.HUNTER)
    hunter.hunter_shot(GAME_STATE, ["Bob", "Cy", "Dee", "Eli"])
    seer = make_agent(Role.SEER, ["Night 1: you saw that Cy is a werewolf."])
    seer.discuss(CONVERSATION, NAMES)
    return SEPARATOR.join([f"### witch with one potion left\n{sent(witch)}",
                           f"### hunter's last shot\n{sent(hunter)}",
                           f"### seer who knows something (discussion)\n{sent(seer)}"])


SNAPSHOT_BUILDERS = {
    "system_prompts.txt": build_system_prompts,
    "discussion_prompts.txt": build_discussion_prompts,
    "vote_prompts.txt": build_vote_prompts,
    "night_prompts.txt": build_night_prompts,
    "special_prompts.txt": build_special_prompts,
}


@pytest.mark.parametrize("filename", sorted(SNAPSHOT_BUILDERS))
def test_prompt_snapshot(filename):
    actual = SNAPSHOT_BUILDERS[filename]().replace("\r\n", "\n").rstrip() + "\n"
    path = SNAPSHOTS / filename
    if os.environ.get("UPDATE_SNAPSHOTS"):
        SNAPSHOTS.mkdir(exist_ok=True)
        path.write_text(actual, encoding="utf-8", newline="\n")
        pytest.skip(f"snapshot {filename} updated")
    assert path.exists(), f"missing snapshot {filename}: run with UPDATE_SNAPSHOTS=1"
    expected = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert actual == expected, (f"The prompts in {filename} changed. If that is intended, run "
                                "UPDATE_SNAPSHOTS=1 python -m pytest tests/test_prompt_snapshots.py "
                                "and review the diff.")


def test_snapshots_cover_every_role():
    text = build_system_prompts()
    for role in roles():
        assert f"### {role.value}" in text


def test_every_snapshot_file_has_a_builder():
    assert {p.name for p in SNAPSHOTS.glob("*.txt")} == set(SNAPSHOT_BUILDERS)
