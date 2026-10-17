"""Every decision comes with a reason, written in the diary at once (fake LLM, no network)."""
import json

import pytest

from backend.agents.player_agent import PlayerAgent
from backend.llm import FakeLLMClient, schemas
from backend.llm.metrics import LLMMetrics, track
from backend.models.game_models import BigFive, PlayerProfile, Role, Sex

NAMES = ["Ann", "Bob", "Cy", "Dee"]
STATE = {"phase": "night", "day_number": 2, "players": [], "valid_targets": ["Bob", "Cy", "Dee"]}


def make_agent(role, answers, **kwargs):
    profile = PlayerProfile(id="p1", name="Ann", sex=Sex.FEMALE, age=30,
                            personality=BigFive(extraversion=2), role=role)
    return PlayerAgent(profile, FakeLLMClient(answers, **kwargs))


def decisions(agent):
    return [e for e in agent.diary if e["kind"] == "decision"]


def answer(**fields):
    return json.dumps(fields)


# --- parsers ------------------------------------------------------------------------------

def test_the_vote_schema_asks_for_the_reason_first_then_the_runner_up():
    schema = schemas.target_schema(["Bob", "Cy"], vote=True)
    assert list(schema["properties"]) == ["reason", "target", "not_chosen"]
    assert schema["required"] == ["reason", "target", "not_chosen"]
    assert "not_chosen" not in schemas.target_schema(["Bob"], vote=True)["properties"]    # nobody to compare


def test_parse_decision_reads_target_reason_and_runner_up():
    text = answer(reason=" He lies. ", target="bob", not_chosen={"player": "cy", "why_not": " Honest. "})
    assert schemas.parse_decision(text, NAMES) == {
        "target": "Bob", "reason": "He lies.", "not_chosen": {"player": "Cy", "why_not": "Honest."},
        "sacrifice_mate": False}


def test_parse_decision_drops_a_runner_up_that_makes_no_sense():
    for runner_up in ({"player": "Bob", "why_not": "x"}, {"player": "Zed", "why_not": "x"}, {"player": "Cy"}, "Cy"):
        decision = schemas.parse_decision(answer(reason="r", target="Bob", not_chosen=runner_up), NAMES)
        assert decision["target"] == "Bob" and decision["not_chosen"] is None


def test_parse_decision_without_a_reason_gives_an_empty_reason():
    assert schemas.parse_decision(answer(target="Bob"), NAMES)["reason"] == ""
    assert schemas.parse_decision(answer(reason="r", target="Zed"), NAMES) is None


# --- the five decision paths ------------------------------------------------------------

def test_night_action_writes_a_decision_entry():
    agent = make_agent(Role.SEER, answer(reason="He is quiet.", target="Bob"), wrap_json=False)
    assert agent.night_action(STATE) == "Bob"
    entry = decisions(agent)[0]
    assert entry["step"] == "Night 2" and "He is quiet." in entry["text"] and "Bob" in entry["text"]
    assert entry["data"]["decision"] == "night" and entry["data"]["target"] == "Bob"


def test_vote_writes_a_decision_with_the_why_not_line():
    agent = make_agent(Role.VILLAGER, answer(reason="He dodges.", target="Bob",
                                             not_chosen={"player": "Cy", "why_not": "He helped me."}), wrap_json=False)
    assert agent.vote("[Bob] hi", NAMES, step="Day 2") == "Bob"
    entry = decisions(agent)[0]
    assert entry["step"] == "Day 2" and entry["data"]["decision"] == "vote"
    assert "Why: He dodges." in entry["text"] and "Why not Cy: He helped me." in entry["text"]


def test_witch_writes_a_decision_entry():
    agent = make_agent(Role.WITCH, answer(reason="Save the seer.", save=True, poison="none"), wrap_json=False)
    assert agent.witch_action(STATE, "Bob", True, True, ["Bob", "Cy"]) == "SAVE"
    entry = decisions(agent)[0]
    assert entry["data"]["decision"] == "witch" and "SAVE" in entry["text"] and "Save the seer." in entry["text"]


def test_hunter_writes_a_decision_entry():
    agent = make_agent(Role.HUNTER, answer(reason="He was suspicious.", target="Cy"), wrap_json=False)
    assert agent.hunter_shot({**STATE, "phase": "day"}, ["Bob", "Cy"]) == "Cy"
    entry = decisions(agent)[0]
    assert entry["step"] == "Day 2" and entry["data"]["decision"] == "hunter"


def test_a_line_that_names_a_player_writes_its_private_reason():
    spoken = answer(reason="Make them nervous.", speak=True, message="Bob, where were you?")
    agent = make_agent(Role.WEREWOLF, spoken, wrap_json=False)
    assert agent.discuss("[Cy] hi", NAMES, step="Day 1") == "Bob, where were you?"
    entry = decisions(agent)[0]
    assert entry["data"]["decision"] == "speech" and "Make them nervous." in entry["text"]
    assert "Bob, where were you?" in entry["text"]


def test_a_line_that_names_nobody_writes_nothing():
    agent = make_agent(Role.VILLAGER, answer(reason="r", speak=True, message="I saw nothing."), wrap_json=False)
    assert agent.discuss("[Cy] hi", NAMES) == "I saw nothing."
    assert decisions(agent) == []


def test_no_entries_when_the_diary_is_off(monkeypatch):
    monkeypatch.setattr("backend.agents.player_agent.get_settings",
                        lambda: type("S", (), {"diary_enabled": False, "memory_messages": 4,
                                               "diary_prompt_entries": 4, "diary_token_budget": 300,
                                               "discussion_context_messages": 10})())
    agent = make_agent(Role.SEER, answer(reason="r", target="Bob"), wrap_json=False)
    assert agent.night_action(STATE) == "Bob" and agent.diary == []


# --- empty reasons and unusable answers: asked once more -----------------------------------

def test_an_empty_reason_is_asked_again_once():
    agent = make_agent(Role.SEER, [answer(target="Bob"), answer(reason="Now with a reason.", target="Cy")],
                       wrap_json=False)
    assert agent.night_action(STATE) == "Cy"
    assert len(agent.llm.calls) == 2 and "fill in the reason" in agent.llm.last_messages[-1].content
    assert "Now with a reason." in decisions(agent)[0]["text"]


def test_a_decision_that_stays_without_reason_is_kept_and_counted():
    agent = make_agent(Role.SEER, answer(target="Bob"), wrap_json=False)
    metrics = LLMMetrics()
    with track(metrics):
        assert agent.night_action(STATE) == "Bob"
    assert len(agent.llm.calls) == 2
    assert metrics.snapshot()["missing_reasons"] == 1
    assert "no reason given" in decisions(agent)[0]["text"]


def test_an_unusable_answer_is_asked_again_and_a_good_second_answer_is_used():
    agent = make_agent(Role.SEER, ["nonsense", answer(reason="r", target="Dee")], wrap_json=False)
    assert agent.night_action(STATE) == "Dee"


def test_two_unusable_answers_give_none_and_count_one_invalid_answer():
    agent = make_agent(Role.SEER, "nonsense", wrap_json=False)
    metrics = LLMMetrics()
    with track(metrics):
        assert agent.night_action(STATE) is None
    assert metrics.snapshot()["invalid_answers"] == 1 and len(agent.llm.calls) == 2


def test_a_good_first_answer_costs_one_call():
    agent = make_agent(Role.SEER, answer(reason="r", target="Bob"), wrap_json=False)
    agent.night_action(STATE)
    assert len(agent.llm.calls) == 1


@pytest.mark.parametrize("speech", [answer(speak=True, message="Hi"),
                                    '{"reason": "r", "speak": true, "message": "Bob, hi”}'])
def test_speech_without_a_reason_or_with_broken_quotes_still_works(speech):
    agent = make_agent(Role.VILLAGER, speech, wrap_json=False)
    assert agent.discuss("[Cy] hi", NAMES).startswith(("Hi", "Bob, hi"))
