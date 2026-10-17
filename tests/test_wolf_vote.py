"""Werewolves know their pack in the diary and the vote, and may sacrifice a mate on purpose (fake LLM)."""
import json
import random

from backend.agents.player_agent import PlayerAgent
from backend.llm import FakeLLMClient, schemas
from backend.llm.metrics import LLMMetrics, track
from backend.models.game_models import BigFive, PlayerProfile, Role, Sex

NAMES = ["Ann", "Bob", "Cy", "Dee", "Eli"]       # Ann is the wolf, Bob her mate


def wolf(answers, **kwargs):
    profile = PlayerProfile(id="p1", name="Ann", sex=Sex.FEMALE, age=30, personality=BigFive(), role=Role.WEREWOLF)
    agent = PlayerAgent(profile, FakeLLMClient(answers, **kwargs))
    agent.write_role_card()
    agent.write_pack(["Bob"])
    return agent


def vote_answer(target, reason="He is dangerous.", sacrifice=False):
    return json.dumps({"reason": reason, "target": target,
                       "not_chosen": {"player": "Eli" if target != "Eli" else "Dee", "why_not": "Less dangerous."},
                       "sacrifice_mate": sacrifice})


# --- diary -------------------------------------------------------------------------------

def test_a_wolfs_diary_prompt_states_the_pack_and_does_not_ask_about_it():
    agent = wolf("A quiet day.")
    agent.write_diary("Day 1", "[Cy] hi", ["Bob", "Cy", "Dee", "Eli"])
    prompt = agent.llm.last_messages[-1].content
    assert "Your pack, all werewolves, you know it for sure: Bob." in prompt
    assert "EACH of these players: Cy, Dee, Eli." in prompt            # no Bob
    schema = agent.llm.calls[-1][1]["json_schema"]
    assert schema["properties"]["opinions"]["items"]["properties"]["player"]["enum"] == ["Cy", "Dee", "Eli"]
    assert "plan" in schema["properties"]["opinions"]["items"]["properties"]
    assert "guess" not in schema["properties"]["opinions"]["items"]["properties"]


def test_a_wolfs_diary_entry_holds_plans_not_guesses():
    agent = wolf("A quiet day.")
    entry = agent.write_diary("Day 1", "", ["Bob", "Cy", "Dee"])
    assert [o["player"] for o in entry["data"]["opinions"]] == ["Cy", "Dee"]
    assert all(o["plan"] == "ignore" and "guess" not in o for o in entry["data"]["opinions"])


def test_the_wolf_diary_is_not_told_that_its_vote_is_what_it_believes():
    agent = wolf("x")
    agent.last_vote = "Cy"
    agent.write_diary("Day 1", "", ["Bob", "Cy"])
    prompt = agent.llm.last_messages[-1].content
    assert "so you suspect Cy" not in prompt and "a move for the pack, not a belief" in prompt


def test_a_villager_diary_keeps_the_suspicion_form():
    profile = PlayerProfile(id="p2", name="Cy", sex=Sex.MALE, age=30, personality=BigFive(), role=Role.VILLAGER)
    agent = PlayerAgent(profile, FakeLLMClient("x"))
    entry = agent.write_diary("Day 1", "", ["Ann", "Bob"])
    assert entry["data"]["opinions"][0]["guess"] == "unsure"


def test_parse_diary_for_a_wolf_reads_plans():
    text = json.dumps({"summary": "s", "opinions": [
        {"player": "cy", "reason": "A threat.", "plan": "frame"},
        {"player": "Dee", "reason": "?", "plan": "kill"},
        {"player": "Zed", "reason": "?", "plan": "ally"}]})
    entry = schemas.parse_diary(text, ["Cy", "Dee"], wolf=True)
    assert entry["opinions"] == [{"player": "Cy", "plan": "frame", "reason": "A threat."}]


def test_the_plans_feed_the_next_prompts():
    agent = wolf("x")
    agent.write_diary("Day 1", "", ["Bob", "Cy"])
    notes = agent._knowledge_with_notes()
    assert any("you plan to leave alone Cy" in line for line in notes)


# --- vote prompt and candidates ---------------------------------------------------------

def test_the_wolf_vote_prompt_deceives_and_leaves_the_pack_out_of_the_candidates():
    agent = wolf(vote_answer("Cy"), wrap_json=False)
    agent.vote("[Cy] hi", NAMES)
    prompt = agent.llm.last_messages[-1].content
    assert "Deceive the village".lower() in prompt.lower()
    assert "Your pack, all werewolves, you know it for sure: Bob." in prompt
    assert "Candidates: Cy, Dee, Eli" in prompt and "Bob," not in prompt.split("Candidates:")[1].split("\n")[0]
    assert "most suspicious" not in prompt


def test_a_villager_vote_prompt_is_unchanged():
    profile = PlayerProfile(id="p2", name="Cy", sex=Sex.MALE, age=30, personality=BigFive(), role=Role.VILLAGER)
    agent = PlayerAgent(profile, FakeLLMClient("Bob"))
    agent.vote("[Bob] hi", NAMES)
    prompt = agent.llm.last_messages[-1].content
    assert "most suspicious" in prompt and "pack" not in prompt


# --- the guard ----------------------------------------------------------------------

def test_100_wolf_votes_without_sacrifice_never_target_a_mate():
    rng = random.Random(7)

    def respond(messages):                      # a careless model: any name, never a sacrifice
        names = ["Bob", "Cy", "Dee", "Eli"]
        return vote_answer(rng.choice(names))

    agent = wolf(respond, wrap_json=False)
    metrics = LLMMetrics()
    with track(metrics):
        votes = [agent.vote("[Cy] hi", NAMES) for _ in range(100)]
    assert "Bob" not in votes
    assert metrics.snapshot()["wolf_sacrificed_mate"] == 0
    assert all(e["data"].get("tag") != "intentional_sacrifice" for e in agent.diary)


def test_a_careful_wolf_never_triggers_the_guard():
    agent = wolf(vote_answer("Cy"), wrap_json=False)
    metrics = LLMMetrics()
    with track(metrics):
        votes = {agent.vote("[Cy] hi", NAMES) for _ in range(100)}
    assert votes == {"Cy"} and metrics.snapshot()["wolf_voted_mate_unintended"] == 0


def test_a_mistaken_vote_on_a_mate_is_asked_again_and_counted():
    agent = wolf([vote_answer("Bob"), vote_answer("Cy")], wrap_json=False)
    metrics = LLMMetrics()
    with track(metrics):
        assert agent.vote("[Cy] hi", NAMES) == "Cy"
    assert metrics.snapshot()["wolf_voted_mate_unintended"] == 1
    assert "pack" in agent.llm.last_messages[-1].content and len(agent.llm.calls) == 2


def test_a_second_mistake_falls_back_to_a_non_mate():
    agent = wolf(vote_answer("Bob"), wrap_json=False)
    for _ in range(30):
        assert agent.vote("[Cy] hi", NAMES) in ("Cy", "Dee", "Eli")


def test_a_sacrifice_is_accepted_and_traced_in_the_diary():
    agent = wolf(vote_answer("Bob", reason="Voting Bob makes me look innocent.", sacrifice=True), wrap_json=False)
    metrics = LLMMetrics()
    with track(metrics):
        assert agent.vote("[Cy] hi", NAMES) == "Bob"
    assert metrics.snapshot()["wolf_sacrificed_mate"] == 1 and metrics.snapshot()["wolf_voted_mate_unintended"] == 0
    entry = [e for e in agent.diary if e["kind"] == "decision"][0]
    assert entry["data"]["tag"] == "intentional_sacrifice" and entry["data"]["target"] == "Bob"
    assert "look innocent" in entry["text"]


def test_a_sacrifice_without_a_reason_is_a_mistake():
    agent = wolf([vote_answer("Bob", reason="", sacrifice=True), vote_answer("Bob", reason="", sacrifice=True)],
                 wrap_json=False)
    assert agent.vote("[Cy] hi", NAMES) in ("Cy", "Dee", "Eli")


def test_the_vote_schema_of_a_wolf_allows_a_mate_only_through_sacrifice_mate():
    agent = wolf(vote_answer("Cy"), wrap_json=False)
    agent.vote("[Cy] hi", NAMES)
    schema = agent.llm.calls[0][1]["json_schema"]
    assert "Bob" in schema["properties"]["target"]["enum"] and "sacrifice_mate" in schema["properties"]


def test_the_pack_comes_from_the_structured_entry_not_from_free_text():
    agent = wolf("x")
    pack = [e for e in agent.diary if e["kind"] == "pack"][0]
    assert pack["data"]["mates"] == ["Bob"] == agent.mates
