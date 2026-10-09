"""Prompt templates: content checks and agent wiring (fake LLM)."""
from types import SimpleNamespace

from backend import prompts
from backend.agents.player_agent import PlayerAgent
from backend.models.game_models import PersonalityType, PlayerProfile, Role, Sex


class RecordingLLM:
    def __init__(self, answer="Bob"):
        self.answer = answer
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.answer)


def make_agent(role=Role.SEER, answer="Bob"):
    agent = PlayerAgent.__new__(PlayerAgent)
    agent.profile = PlayerProfile(id="p", name="Ann", sex=Sex.FEMALE, age=30,
                                  personality=PersonalityType.INTJ, role=role)
    agent.memory = []
    agent.knowledge = []
    agent.llm = RecordingLLM(answer)
    return agent


def test_personality_behavior_covers_every_type():
    for personality in PersonalityType:
        assert prompts.personality_behavior(personality.value) != "neutral"
    assert prompts.personality_behavior("???") == "neutral"


def test_player_system_prompt_includes_persona_and_role():
    text = prompts.player_system_prompt("Ann", 30, "female", "INTJ", "Strategic.", "You are the SEER.")
    assert "You are Ann, a 30-year-old female" in text
    assert "INTJ - Strategic." in text
    assert text.count("Your Role: You are the SEER.") == 1
    assert "Your Role" not in prompts.player_system_prompt("Ann", 30, "female", "INTJ", "S.")


def test_game_context_lists_alive_players_and_action():
    text = prompts.game_context("day", 2, ["Ann", "Bob"], ["e1"], ["[Bob] hi"], "Vote now")
    assert "- Phase: day" in text and "- Day: 2" in text
    assert "Alive Players: Ann, Bob" in text
    assert "Recent Discussions:\n[Bob] hi" in text
    assert text.rstrip().endswith("Current Action: Vote now")
    assert "Recent Discussions" not in prompts.game_context("day", 2, [], [], [], "x")


def test_response_factors():
    assert prompts.response_factors("Ann", "", "") == "- No special pressure to respond"
    text = prompts.response_factors("Ann", "[Bob] Ann?\n[Cy] yes", "- hint")
    assert text.splitlines() == ["- You have been mentioned or addressed",
                                 "- Recent activity in conversation", "- hint"]


def test_discussion_and_vote_prompts():
    d = prompts.discussion_prompt("Ann", "", ["Ann", "Bob"], "seer", "STRATEGY", "FACTORS")
    assert "No one has spoken yet." in d and "You are a seer\nSTRATEGY" in d and "FACTORS" in d
    v = prompts.vote_prompt("Ann", "werewolf", "VOTING", "talk", ["Bob", "Cy"])
    assert "VOTING CANDIDATES: Bob, Cy" in v and "You are a werewolf\nVOTING" in v
    assert "No discussion took place." in prompts.vote_prompt("Ann", "x", "y", " ", ["Bob"])


def test_agent_sends_role_and_strategy_prompts_to_the_llm():
    agent = make_agent(Role.SEER)
    agent.discuss("[Bob] hello", ["Ann", "Bob"])
    system, user = agent.llm.calls[0]
    assert "Personality: INTJ - be independent and methodical" in system.content
    assert "You are a seer" in user.content
    assert agent.handler.discussion_strategy in user.content


def test_night_action_prompt_uses_system_persona_with_role():
    agent = make_agent(Role.SEER)
    agent.night_action({'valid_targets': ['Bob'], 'players': [], 'phase': 'night'})
    system, user = agent.llm.calls[0]
    assert "Your Role: You are the SEER." in system.content
    assert "from these players: Bob" in user.content
