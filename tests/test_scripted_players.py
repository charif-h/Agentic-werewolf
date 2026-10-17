"""Scripted behaviours of the fake model, and the behaviour evaluation script (no network)."""
import importlib.util
import json
from pathlib import Path

import pytest

from backend.game.game_logic import WerewolfGame
from backend.llm import FakeLLMClient, ScriptedPlayers
from backend.llm.base import Message
from backend.llm.metrics import track
from backend.models.game_models import BigFive, GamePhase, GameState, PlayerProfile, Role, Sex
from backend.agents.player_agent import PlayerAgent

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "evaluate_behaviour.py"
spec = importlib.util.spec_from_file_location("evaluate_behaviour", SCRIPT)
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)

NAMES = ["Wolf1", "Wolf2", "Bob", "Cy", "Dee", "Eli"]
ROLES = [Role.WEREWOLF, Role.WEREWOLF] + [Role.VILLAGER] * 4


def ask(script, name, text):
    return script([Message("system", f"You are {name}, playing Werewolf."), Message("user", text)])


# --- recognising the questions ------------------------------------------------------------

@pytest.mark.parametrize("text,kind", [
    ("Pack talk so far:\n...", "wolf_chat"),
    ("You are Ann. The vote is about to begin: write your plan", "plan"),
    ("You are Ann, voting to eliminate someone.", "vote"),
    ("You are Ann in the village discussion.", "say"),
    ("You are Ann, writing a quick note in your private diary", "reaction"),
    ("You are Ann, writing your private diary.", "diary"),
    ("Phase: night, day 1.\nAs a seer, choose", "night"),
    ("Something else", "other"),
])
def test_kind_of_question(text, kind):
    assert ScriptedPlayers.kind_of(text) == kind


def test_player_of_reads_the_system_message():
    assert ScriptedPlayers.player_of([Message("system", "You are Ibrahim, a 41-year-old man, playing...")]) == "Ibrahim"
    assert ScriptedPlayers.player_of([Message("system", "You are Ann, playing Werewolf.")]) == "Ann"
    assert ScriptedPlayers.player_of([]) == ""


def test_answers_are_used_in_turn_and_the_last_one_repeats():
    script = ScriptedPlayers(default="nothing").vote("Ann", "Bob", "Cy")
    question = "You are Ann, voting to eliminate someone."
    assert [ask(script, "Ann", question) for _ in range(3)] == ["Bob", "Cy", "Cy"]
    assert ask(script, "Bob", question) == "nothing"                      # not scripted: the default
    assert ask(script, "Ann", "Something else") == "nothing"


def test_a_dict_answer_is_sent_as_json():
    script = ScriptedPlayers().vote("Ann", {"target": "Bob", "reason": "r", "sacrifice_mate": True})
    assert json.loads(ask(script, "Ann", "You are Ann, voting to eliminate someone.")) == {
        "target": "Bob", "reason": "r", "sacrifice_mate": True}


# --- scripted scenarios through the real game code ------------------------------------------

def game_with(script):
    game = WerewolfGame(num_players=6, llm=FakeLLMClient(script))
    game.state = GameState(day_number=1, phase=GamePhase.NIGHT, players=[
        PlayerProfile(id=f"p{i}", name=NAMES[i], sex=Sex.MALE, age=30, personality=BigFive(extraversion=5), role=role)
        for i, role in enumerate(ROLES)])
    game.player_agents = {p.id: PlayerAgent(p, game.llm) for p in game.state.players}
    for wolf, mate in (("p0", "Wolf2"), ("p1", "Wolf1")):
        game.player_agents[wolf].write_pack([mate])
    return game


def test_scripted_wolf_proposals_decide_the_victim():
    script = ScriptedPlayers().night("Wolf1", "Bob").night("Wolf2", "Cy").wolf_chat("Wolf1", "Bob is loud.")
    game = game_with(script)
    game.state.day_number = 2                                   # the lead is Wolf2 tonight
    assert game._wolf_night().name == "Cy"
    game.state.day_number = 1                                   # the lead is Wolf1
    assert game._wolf_night().name == "Bob"


def test_a_scripted_back_reference_is_asked_again_and_counted():
    script = ScriptedPlayers().backreference("Bob", "As I said earlier, Cy lies.").say("Bob", "Who saw something?")
    game = game_with(script)
    with track(game.metrics):
        reply = game.player_agents["p2"].discuss("", NAMES)
    assert reply == "Who saw something?" and game.metrics.snapshot()["opening_backreference"] == 1


def test_a_scripted_mismatch_is_counted_and_the_plan_wins():
    script = ScriptedPlayers().mismatch("Bob", planned="Cy", voted="Dee")
    game = game_with(script)
    with track(game.metrics):
        agent = game.player_agents["p2"]
        agent.plan_vote("[Cy] hi", NAMES, step="Day 1")
        assert agent.vote("[Cy] hi", NAMES, step="Day 1") == "Cy"
    stats = game.metrics.snapshot()
    assert stats["diary_vote_mismatch"] == 1 and stats["unexplained_changes"] == 1


# --- scripts/evaluate_behaviour.py ---------------------------------------------------------

def test_summarize_computes_the_rates():
    games = [
        {"days": 2, "calls": 100, "opening_backreference": 1, "psytests": 8, "psytest_flagged": 2,
         "wolf_voted_mate_unintended": 1, "wolf_sacrificed_mate": 0, "vote_plans": 8, "diary_vote_mismatch": 2,
         "unexplained_changes": 1, "reaction_entries": 3, "missing_reasons": 0, "invalid_answers": 4,
         "villager_votes": 5, "villager_off_suspect": 1},
        {"days": 2, "calls": 60, "opening_backreference": 0, "psytests": 8, "psytest_flagged": 0,
         "wolf_voted_mate_unintended": 0, "wolf_sacrificed_mate": 1, "vote_plans": 8, "diary_vote_mismatch": 0,
         "unexplained_changes": 0, "reaction_entries": 1, "missing_reasons": 2, "invalid_answers": 0,
         "villager_votes": 5, "villager_off_suspect": 0},
    ]
    s = evaluate.summarize(games)
    assert s["opening_backreference_rate"] == 0.25 and s["psytest_pass_rate"] == 0.875
    assert s["vote_mismatch_rate"] == 0.125 and s["villager_off_suspect_rate"] == 0.1
    assert s["reactions_per_day"] == 1.0 and s["calls_per_day"] == 40
    assert s["wolf_voted_mate"] == 1 and s["wolf_sacrificed_mate"] == 1


def test_summarize_of_nothing_does_not_divide_by_zero():
    assert evaluate.summarize([])["calls_per_day"] == 0.0


def test_features_can_be_turned_off_and_on(monkeypatch):
    env = {}
    evaluate.set_features(False, env)
    assert env == {"VOTE_PLAN_ENABLED": "false", "WOLF_CHAT_ROUNDS": "0", "REACTIONS_PER_DAY": "0"}
    evaluate.set_features(True, env)
    assert env == {}


def test_the_script_plays_fake_games_and_writes_its_report(tmp_path):
    out_json, out_md = tmp_path / "r.json", tmp_path / "r.md"
    assert evaluate.main(["--fake", "--games", "2", "--players", "6", "--compare",
                          "--json", str(out_json), "--markdown", str(out_md)]) == 0
    report = json.loads(out_json.read_text(encoding="utf-8"))
    assert set(report["runs"]) == {"M7 features off", "M7 features on"}
    markdown = out_md.read_text(encoding="utf-8")
    assert "Diary/vote mismatch rate" in markdown and "M7 features off" in markdown
    off, on = (report["runs"][k]["summary"] for k in ("M7 features off", "M7 features on"))
    assert off["vote_mismatch_rate"] == 0.0 and on["calls_per_day"] > off["calls_per_day"]
