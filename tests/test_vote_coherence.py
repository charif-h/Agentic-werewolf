"""The vote follows the plan written before it, or explains the change (fake LLM, no network)."""
import json

from backend.agents.player_agent import PlayerAgent
from backend.game.game_logic import WerewolfGame
from backend.llm import FakeLLMClient
from backend.llm.metrics import LLMMetrics, track
from backend.models.game_models import BigFive, PlayerProfile, Role, Sex

NAMES = ["Ann", "Bob", "Cy", "Dee", "Eli"]


def agent_for(role, answers, name="Ann"):
    profile = PlayerProfile(id="p1", name=name, sex=Sex.FEMALE, age=30, personality=BigFive(), role=role)
    return PlayerAgent(profile, FakeLLMClient(answers))


def plan_answer(target, reason="He dodges every question."):
    return json.dumps({"reason": reason, "target": target})


def vote_answer(target, reason="He seems odd."):
    return json.dumps({"reason": reason, "target": target,
                       "not_chosen": {"player": "Eli" if target != "Eli" else "Dee", "why_not": "Less odd."},
                       "sacrifice_mate": False})


def suspect_bob(agent, confidence="high"):
    agent._add_entry("Night 1", "night_summary", "A night.", {"opinions": [
        {"player": "Bob", "guess": "werewolf", "confidence": confidence, "reason": "He lies."},
        {"player": "Cy", "guess": "werewolf", "confidence": "low", "reason": "Quiet."}]})


# --- the plan ---------------------------------------------------------------------------

def test_the_plan_is_written_in_the_diary_before_the_vote():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy"), vote_answer("Cy")])
    plan = agent.plan_vote("[Bob] hi", NAMES, step="Day 1")
    assert plan == {"target": "Cy", "reason": "He dodges every question.", "step": "Day 1"}
    entry = agent.diary[-1]
    assert entry["kind"] == "plan" and entry["step"] == "Day 1"
    assert entry["text"] == "Today I will vote against Cy because He dodges every question."
    assert entry["data"]["vote"] is True


def test_the_plan_is_the_main_input_of_the_vote():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy"), vote_answer("Cy")])
    agent.plan_vote("[Bob] hi", NAMES, step="Day 1")
    agent.vote("[Bob] hi", NAMES, step="Day 1")
    prompt = agent.llm.last_messages[-1].content
    assert "YOUR PLAN, written before the vote: vote against Cy because He dodges every question." in prompt


def test_a_plan_of_another_day_is_not_used():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy"), vote_answer("Bob")])
    agent.plan_vote("[Bob] hi", NAMES, step="Day 1")
    agent.vote("[Bob] hi", NAMES, step="Day 2")
    assert "YOUR PLAN" not in agent.llm.last_messages[-1].content


def test_planning_can_be_turned_off(monkeypatch):
    agent = agent_for(Role.VILLAGER, vote_answer("Bob"))
    monkeypatch.setattr("backend.agents.player_agent.get_settings",
                        lambda: type("S", (), {"vote_plan_enabled": False})())
    assert agent.plan_vote("x", NAMES) is None and agent.llm.calls == []


def test_a_villager_plans_against_the_top_suspect_of_the_diary():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy"), plan_answer("Bob")])
    suspect_bob(agent)
    plan = agent.plan_vote("x", NAMES, step="Day 1")
    assert plan["target"] == "Bob"                                  # asked again: the notes say Bob
    assert "top suspect is Bob" in agent.llm.calls[0][0][-1].content
    assert len(agent.llm.calls) == 2


def test_a_villager_may_plan_against_someone_else_if_the_change_is_explained():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy", "Cy just accused me."), plan_answer("Cy", "Cy lied today.")])
    suspect_bob(agent)
    assert agent.plan_vote("x", NAMES, step="Day 1")["target"] == "Cy"


def test_a_wolf_never_plans_against_a_mate():
    agent = agent_for(Role.WEREWOLF, [json.dumps({"reason": "r", "target": "Bob", "sacrifice_mate": False}),
                                       json.dumps({"reason": "r", "target": "Cy", "sacrifice_mate": False})])
    agent.write_pack(["Bob"])
    assert agent.plan_vote("x", NAMES, step="Day 1")["target"] == "Cy"


# --- the check after the vote -----------------------------------------------------------

def test_a_vote_that_matches_the_plan_costs_nothing_more():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy"), vote_answer("Cy")])
    agent.plan_vote("x", NAMES, step="Day 1")
    metrics = LLMMetrics()
    with track(metrics):
        assert agent.vote("x", NAMES, step="Day 1") == "Cy"
    assert len(agent.llm.calls) == 2 and metrics.snapshot()["diary_vote_mismatch"] == 0


def test_a_mismatching_vote_triggers_one_retry_that_can_fix_it():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy"), vote_answer("Bob"), vote_answer("Cy")])
    agent.plan_vote("x", NAMES, step="Day 1")
    metrics = LLMMetrics()
    with track(metrics):
        assert agent.vote("x", NAMES, step="Day 1") == "Cy"
    assert len(agent.llm.calls) == 3
    assert "Your notes say you will vote against Cy" in agent.llm.last_messages[-1].content
    assert metrics.snapshot()["diary_vote_mismatch"] == 1 and metrics.snapshot()["unexplained_changes"] == 0


def test_a_justified_change_is_kept_and_logged():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy"), vote_answer("Bob"),
                                       vote_answer("Bob", "Bob just claimed to be the seer and lied.")])
    agent.plan_vote("x", NAMES, step="Day 1")
    metrics = LLMMetrics()
    with track(metrics):
        assert agent.vote("x", NAMES, step="Day 1") == "Bob"
    assert metrics.snapshot()["diary_vote_mismatch"] == 1 and metrics.snapshot()["unexplained_changes"] == 0
    entry = [e for e in agent.diary if e["kind"] == "decision"][-1]
    assert entry["data"]["target"] == "Bob" and entry["data"]["tag"] == "plan_change"
    assert "claimed to be the seer" in entry["text"]


def test_an_unexplained_change_gives_the_plan_back():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy"), vote_answer("Bob"), vote_answer("Bob", "")])
    agent.plan_vote("x", NAMES, step="Day 1")
    metrics = LLMMetrics()
    with track(metrics):
        assert agent.vote("x", NAMES, step="Day 1") == "Cy"
    assert metrics.snapshot()["unexplained_changes"] == 1
    assert [e for e in agent.diary if e["kind"] == "decision"][-1]["data"]["tag"] == "plan_restored"


def test_without_a_plan_the_vote_is_not_checked():
    agent = agent_for(Role.VILLAGER, vote_answer("Bob"))
    metrics = LLMMetrics()
    with track(metrics):
        assert agent.vote("x", NAMES, step="Day 1") == "Bob"
    assert len(agent.llm.calls) == 1 and metrics.snapshot()["diary_vote_mismatch"] == 0


# --- the diary remembers the plan -----------------------------------------------------------

def test_the_day_diary_asks_what_changed_between_plan_and_vote():
    agent = agent_for(Role.VILLAGER, [plan_answer("Cy"), vote_answer("Bob", "Bob lied."), vote_answer("Bob", "Bob lied."),
                                       vote_answer("Bob", "Bob lied.")])
    agent.plan_vote("x", NAMES, step="Day 1")
    agent.vote("x", NAMES, step="Day 1")
    agent.write_diary("Day 1", "", ["Bob", "Cy"])
    prompt = agent.llm.last_messages[-1].content
    assert "Your plan before the vote was to vote against Cy because He dodges every question." in prompt
    assert "You voted for Bob instead: say what changed and why." in prompt


def test_a_game_plans_before_the_votes():
    def first_candidate(messages):
        text = messages[-1].content
        return text.split("Candidates: ")[1].split("\n")[0].split(", ")[0] if "Candidates: " in text else "no comment"

    game = WerewolfGame(num_players=8, llm=FakeLLMClient(first_candidate))
    game.setup_game()
    game.start_night()
    game.process_night_actions()
    game.start_day()
    game.conduct_discussion()
    with track(game.metrics):
        game.conduct_vote()
    assert game.metrics.snapshot()["vote_plans"] >= 1
    for agent in game.player_agents.values():
        plans = [e for e in agent.diary if e["kind"] == "plan" and e["data"].get("vote")]
        assert len(plans) <= 1
