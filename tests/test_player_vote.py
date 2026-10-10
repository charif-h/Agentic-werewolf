"""Tests for PlayerAgent.vote and the game-level fallback vote (fake LLM, no network)."""
from backend.agents.player_agent import PlayerAgent
from backend.engine import rules
from backend.llm import FakeLLMClient
from backend.models.game_models import (
    PersonalityType, PlayerProfile, Role, Sex,
)


def make_agent(answer, role=Role.WEREWOLF):
    """PlayerAgent whose LLM returns `answer` (or raises if it is an Exception)."""
    profile = PlayerProfile(
        id="p1", name="Ann", sex=Sex.FEMALE, age=30,
        personality=PersonalityType.INTJ, role=role,
    )
    return PlayerAgent(profile, FakeLLMClient(answer))


def test_single_vote_definition():
    assert list(PlayerAgent.__dict__).count("vote") == 1


def test_vote_returns_named_candidate():
    assert make_agent("Bob").vote("talk", ["Ann", "Bob", "Cy"]) == "Bob"


def test_vote_prompt_contains_role_and_voting_strategy_and_excludes_self():
    agent = make_agent("Bob")
    agent.vote("talk", ["Ann", "Bob", "Cy"])
    prompt = agent.llm.last_messages[-1].content
    assert "Secret: you are a werewolf" in prompt
    assert "As a WEREWOLF, vote to eliminate" in prompt
    assert "Candidates: Bob, Cy" in prompt


def test_vote_never_returns_self():
    assert make_agent("Ann").vote("talk", ["Ann", "Bob", "Cy"]) in ("Bob", "Cy")


def test_unparseable_answer_falls_back_to_valid_candidate():
    for _ in range(50):
        assert make_agent("???").vote("talk", ["Ann", "Bob", "Cy"]) in ("Bob", "Cy")


def test_llm_error_falls_back_to_valid_candidate():
    assert make_agent(RuntimeError("boom")).vote("talk", ["Ann", "Bob"]) == "Bob"


def test_fallback_vote_never_targets_voter():
    seen = set()
    for _ in range(100):
        target = rules.fallback_vote_target("A", ["A", "B", "C"])
        assert target in ("B", "C")
        seen.add(target)
    assert seen == {"B", "C"}
    assert rules.fallback_vote_target("A", ["A"]) is None
