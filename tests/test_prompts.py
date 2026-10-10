"""Prompt templates: content checks and agent wiring (fake LLM)."""

import pytest

from backend import prompts
from backend.agents.player_agent import PlayerAgent
from backend.llm import FakeLLMClient
from backend.models.game_models import PersonalityType, PlayerProfile, Role, Sex


def make_agent(role=Role.SEER, answer="Bob"):
    profile = PlayerProfile(id="p", name="Ann", sex=Sex.FEMALE, age=30,
                            personality=PersonalityType.INTJ, role=role)
    return PlayerAgent(profile, FakeLLMClient(answer))


def test_personality_behavior_covers_every_type():
    for personality in PersonalityType:
        assert prompts.personality_behavior(personality.value) != "neutral"
    assert prompts.personality_behavior("???") == "neutral"


def test_player_system_prompt_is_short_and_has_persona_and_role():
    text = prompts.player_system_prompt("Ann", 30, "female", "INTJ", "Strategic.", "You are the SEER.")
    assert "You are Ann, a 30-year-old female" in text
    assert "Personality (INTJ): Strategic." in text
    assert text.count("Your role: You are the SEER.") == 1
    assert "Never reveal your own role" in text
    assert "Your role" not in prompts.player_system_prompt("Ann", 30, "female", "INTJ", "S.")
    assert len(text.splitlines()) <= 4          # persona in a few lines (small model)


def test_game_context_lists_alive_players_and_ends_with_the_action():
    text = prompts.game_context("day", 2, ["Ann", "Bob"], ["e1"], ["[Bob] hi"], "Vote now")
    assert "Phase: day, day 2." in text
    assert "Alive players: Ann, Bob." in text
    assert "Recent discussion:\n[Bob] hi" in text
    assert text.rstrip().endswith("Vote now")
    assert "Recent discussion" not in prompts.game_context("day", 2, [], [], [], "x")


def test_response_factors():
    assert prompts.response_factors("Ann", "", "") == "- No special pressure to respond"
    text = prompts.response_factors("Ann", "[Bob] Ann?\n[Cy] yes", "- hint")
    assert text.splitlines() == ["- You have been mentioned or addressed",
                                 "- Recent activity in conversation", "- hint"]


def test_discussion_prompt_asks_for_speech_not_for_permission():
    d = prompts.discussion_prompt("Ann", "", ["Ann", "Bob"], "seer", "STRATEGY", "FACTORS")
    assert "Nobody has spoken yet." in d and "Secret: you are a seer. STRATEGY" in d and "FACTORS" in d
    assert "Good replies look like this" in d and d.count('- "') == 3          # few-shot examples
    assert d.rstrip().endswith("answer exactly: no comment")
    assert "Do you want to" not in d       # a yes/no question made small models answer "Yes, please."


def test_vote_prompt_ends_with_the_instruction():
    v = prompts.vote_prompt("Ann", "werewolf", "VOTING", "talk", ["Bob", "Cy"])
    assert "Candidates: Bob, Cy" in v and "Secret: you are a werewolf. VOTING" in v
    assert v.rstrip().endswith("Answer with ONLY one name from the candidates.")
    assert "Nobody spoke." in prompts.vote_prompt("Ann", "x", "y", " ", ["Bob"])


@pytest.mark.parametrize("text,role,leak", [
    ("I am the seer and I saw Bob.", "seer", True),
    ("As a hunter I will not go down alone", "hunter", True),
    ("I'm a werewolf, ha ha", "werewolf", True),
    ("My role is secret", "witch", True),
    ("I think Bob is a werewolf.", "villager", False),     # accusing is normal play
    ("Cy is acting like the seer, suspicious.", "villager", False),
    ("I am sure Dee is lying.", "seer", False),
    ("As the seer? No way, Eli is lying", "villager", False),
])
def test_leaks_own_role(text, role, leak):
    assert prompts.leaks_own_role(text, role) is leak


def test_agent_sends_role_and_strategy_prompts_to_the_llm():
    agent = make_agent(Role.SEER)
    agent.discuss("[Bob] hello", ["Ann", "Bob"])
    system, user = agent.llm.last_messages
    assert "Personality (INTJ): independent and methodical" in system.content
    assert "Secret: you are a seer" in user.content
    assert agent.handler.discussion_strategy in user.content


def test_night_action_prompt_uses_system_persona_with_role():
    agent = make_agent(Role.SEER)
    agent.night_action({'valid_targets': ['Bob'], 'players': [], 'phase': 'night'})
    system, user = agent.llm.last_messages
    assert "Your role: You are the SEER." in system.content
    assert "from these players: Bob" in user.content


# --- discussion replies -------------------------------------------------------------

def test_discussion_reply_is_cleaned():
    assert make_agent(answer='  "Bob, why so quiet?"  ').discuss("", ["Ann", "Bob"]) == "Bob, why so quiet?"
    assert make_agent(answer="No comment.").discuss("", ["Ann", "Bob"]) == "no comment"
    assert make_agent(answer="   ").discuss("", ["Ann", "Bob"]) == "no comment"


def test_a_reply_that_reveals_the_role_is_asked_again_once():
    agent = make_agent(Role.SEER, answer=["I am the seer, trust me.", "Trust me, I know Dee is lying."])
    assert agent.discuss("[Bob] hi", ["Ann", "Bob"]) == "Trust me, I know Dee is lying."
    assert len(agent.llm.calls) == 2
    assert agent.llm.last_messages[-1].content.endswith(prompts.LEAK_REMINDER.strip())


def test_a_second_leak_means_staying_silent():
    agent = make_agent(Role.SEER, answer="I am the seer.")
    assert agent.discuss("[Bob] hi", ["Ann", "Bob"]) == "no comment"
    assert len(agent.llm.calls) == 2


def test_accusing_someone_of_being_a_werewolf_is_not_a_leak():
    agent = make_agent(Role.VILLAGER, answer="I think Bob is a werewolf.")
    assert agent.discuss("", ["Ann", "Bob"]) == "I think Bob is a werewolf."
    assert len(agent.llm.calls) == 1


# --- context budget and memory ---------------------------------------------------------

def test_long_conversations_are_cut_to_the_token_budget(monkeypatch):
    from backend.config import Settings
    monkeypatch.setattr("backend.agents.player_agent.get_settings",
                        lambda: Settings(_env_file=None, conversation_token_budget=100))
    agent = make_agent(answer="Bob")
    conversation = "\n".join(f"[Bob] message number {i} " + "x" * 40 for i in range(200))
    agent.discuss(conversation, ["Ann", "Bob"])
    prompt = agent.llm.last_messages[-1].content
    assert "[earlier messages omitted]" in prompt
    assert "message number 199" in prompt and "message number 0 " not in prompt
    assert len(prompt) < 2500

    agent.vote(conversation, ["Ann", "Bob", "Cy"])
    assert "[earlier messages omitted]" in agent.llm.last_messages[-1].content


def test_memory_keeps_short_records_and_forgets_old_ones():
    agent = make_agent(Role.SEER, answer="Bob")
    state = {'phase': 'night', 'day_number': 1, 'players': [], 'valid_targets': ['Bob']}
    for _ in range(5):
        agent.night_action(state)
    assert len(agent.memory) == 4                                  # MEMORY_MESSAGES
    assert all(len(m.content) < 200 for m in agent.memory)         # the question, not the whole state
    assert [m.role for m in agent.memory] == ["user", "assistant", "user", "assistant"]
