"""First day: what is new, who was named, and reactions in the diary (fake LLM, no network)."""
import random

from backend import prompts
from backend.agents.player_agent import PlayerAgent
from backend.game.game_logic import WerewolfGame
from backend.game.talkativeness import (
    accused_player, has_claim, is_accused, mentioned_in, reaction_trigger, should_speak, speak_probability)
from backend.llm import FakeLLMClient
from backend.llm.metrics import track
from backend.models.game_models import BigFive, GameState, PlayerProfile, Role, Sex

NAMES = ["Ann", "Bob", "Cy", "Dee"]


def profile(name, role=Role.VILLAGER, extraversion=1):
    return PlayerProfile(id=name.lower(), name=name, sex=Sex.FEMALE, age=30,
                         personality=BigFive(extraversion=extraversion), role=role)


# --- detection ------------------------------------------------------------------------

def test_mention_and_accusation_detection():
    lines = ["[Bob] Ann, where were you last night?", "[Cy] Dee is lying, I am sure."]
    assert mentioned_in("Ann", lines) and mentioned_in("Dee", lines) and not mentioned_in("Bob", lines)
    assert is_accused("Dee", lines) and not is_accused("Ann", lines)       # asked a question, not accused
    assert not mentioned_in("Ann", ["[Ann] I am Ann"])                      # one's own line does not count


def test_names_are_matched_as_whole_words():
    assert not mentioned_in("Ann", ["[Bob] Joanna looks odd"])


def test_claims_and_accused_player():
    assert has_claim("Ann", ["[Bob] I am the seer, trust me."]) and not has_claim("Ann", ["[Bob] hello"])
    assert not has_claim("Bob", ["[Bob] I am the seer"])
    assert accused_player("Cy is lying to us", NAMES, "Ann") == "Cy"
    assert accused_player("Cy seems nice", NAMES, "Ann") is None
    assert accused_player("Ann is lying", NAMES, "Ann") is None


def test_reaction_triggers():
    assert reaction_trigger("Ann", ["[Bob] Ann is a liar."], None, None, NAMES) == "accused"
    assert reaction_trigger("Ann", ["[Bob] I am the seer."], None, None, NAMES) == "claim"
    assert reaction_trigger("Ann", ["[Bob] hi"], "Cy is lying", "Dee", NAMES) == "suspect_changed"
    assert reaction_trigger("Ann", ["[Bob] hi"], "Cy is lying", "Cy", NAMES) is None
    assert reaction_trigger("Ann", ["[Bob] hi"], "Cy is lying", None, NAMES) is None      # first accusation
    assert reaction_trigger("Ann", ["[Bob] The weather is nice."], None, None, NAMES) is None


def test_a_player_named_in_the_new_lines_always_takes_their_turn():
    quiet = profile("Ann", extraversion=1)
    assert speak_probability(quiet, "[Bob] a\n[Bob] b\n[Bob] c\n[Bob] d", False) < 1.0
    new_lines = ["[Bob] Ann, answer me.", "[Cy] x", "[Cy] y", "[Cy] z"]
    assert speak_probability(quiet, "\n".join(new_lines), False, new_lines=new_lines) == 1.0
    assert should_speak(quiet, "[Bob] a", False, rng=random.Random(1), new_lines=["[Bob] Ann, answer me."])


# --- the prompt -----------------------------------------------------------------------

def test_the_prompt_has_the_new_lines_and_the_mention_block():
    block = prompts.updates_block("Ann", ["[Bob] Ann, you lied to us.", "[Cy] I agree with Bob."])
    assert "New since your last turn:" in block and "[Cy] I agree with Bob." in block
    assert 'Bob talked about you: "Ann, you lied to us."' in block
    assert "Cy talked about you" not in block


def test_no_news_gives_no_block_and_the_first_turn_only_gets_the_notice():
    assert prompts.updates_block("Ann", []) == ""
    only = prompts.updates_block("Ann", ["[Bob] Ann, hello"], mentions_only=True)
    assert "New since your last turn" not in only and "Bob talked about you" in only


def test_the_agent_puts_the_updates_in_the_discussion_prompt():
    agent = PlayerAgent(profile("Ann"), FakeLLMClient("Bob, you are wrong."))
    agent.discuss("[Ann] hi\n[Bob] Ann, you lied.\n[Cy] Ok.", NAMES, new_lines=["[Bob] Ann, you lied.", "[Cy] Ok."])
    prompt = agent.llm.last_messages[-1].content
    assert "New since your last turn:\n[Bob] Ann, you lied.\n[Cy] Ok." in prompt
    assert 'Bob talked about you: "Ann, you lied."' in prompt


def test_before_the_first_turn_a_mention_is_still_flagged():
    agent = PlayerAgent(profile("Ann"), FakeLLMClient("Bob, you are wrong."))
    agent.discuss("[Bob] Ann, where were you?", NAMES)
    prompt = agent.llm.last_messages[-1].content
    assert "Bob talked about you" in prompt and "New since your last turn" not in prompt


# --- reactions in a game --------------------------------------------------------------

def scripted_game(lines_by_player):
    """4 villagers; each says its scripted line when it speaks, and diaries/reactions are fake."""
    game = WerewolfGame(num_players=4, llm=FakeLLMClient("x"))
    players = [profile(n, extraversion=5) for n in NAMES]
    game.state = GameState(players=players, day_number=1)

    def respond(messages):
        text = messages[-1].content
        if "quick note in your private diary" in text:
            return '{"text": "I felt accused, so I will answer."}'
        for name, line in lines_by_player.items():
            if f"You are {name} in the village discussion" in text:
                return line
        return "no comment"

    game.llm = FakeLLMClient(respond)
    game.player_agents = {p.id: PlayerAgent(p, game.llm) for p in players}
    return game


def reactions(game, name):
    agent = next(a for a in game.player_agents.values() if a.profile.name == name)
    return [e for e in agent.diary if e["kind"] == "reaction"]


def test_an_accused_player_writes_a_reaction_and_an_uninvolved_one_does_not(monkeypatch):
    # Bob always speaks first (random order is fixed by sorting the shuffle)
    monkeypatch.setattr(random, "shuffle", lambda items: items.sort(key=lambda p: NAMES.index(p.name)))
    game = scripted_game({"Ann": "Bob is lying to all of us.", "Bob": "I only watched the fire."})
    game._reactions = {}
    with track(game.metrics):
        game.conduct_discussion(max_rounds=1)
    assert len(reactions(game, "Bob")) == 1
    assert reactions(game, "Bob")[0]["data"]["cause"] == "accused"
    assert "accused" in reactions(game, "Bob")[0]["text"]
    assert reactions(game, "Cy") == [] and reactions(game, "Dee") == []         # Cy and Dee are not involved
    assert game.metrics.snapshot()["reaction_entries"] == 1


def test_a_role_claim_makes_the_others_react(monkeypatch):
    monkeypatch.setattr(random, "shuffle", lambda items: items.sort(key=lambda p: NAMES.index(p.name)))
    game = scripted_game({"Ann": "I am the seer and Dee is clean.", "Bob": "no comment"})
    with track(game.metrics):
        game.conduct_discussion(max_rounds=1)
    assert [e["data"]["cause"] for e in reactions(game, "Bob")] == ["claim"]


def test_at_most_two_reactions_per_player_per_day(monkeypatch):
    monkeypatch.setattr(random, "shuffle", lambda items: items.sort(key=lambda p: NAMES.index(p.name)))
    game = scripted_game({"Ann": "Bob is lying about everything.", "Bob": "Ann is lying, Ann is a wolf.",
                          "Cy": "Bob is guilty, Bob lied.", "Dee": "Bob, answer us."})
    with track(game.metrics):
        game.conduct_discussion(max_rounds=5)
    for name in NAMES:
        assert len(reactions(game, name)) <= 2
    assert game.metrics.snapshot()["reaction_entries"] <= 2 * len(NAMES)


def test_the_counter_starts_again_each_day():
    game = scripted_game({})
    game._reactions = {"Bob": 2}
    game.start_day()
    assert game._reactions == {}


def test_no_reactions_without_the_diary(monkeypatch):
    monkeypatch.setattr(random, "shuffle", lambda items: items.sort(key=lambda p: NAMES.index(p.name)))
    game = scripted_game({"Ann": "Bob is lying to all of us."})
    monkeypatch.setattr("backend.game.game_logic.get_settings", lambda: type("S", (), {
        "diary_enabled": False, "discussion_max_rounds": 1, "discussion_gate": False,
        "reactions_per_day": 2})())
    calls = len(game.llm.calls)
    game.conduct_discussion(max_rounds=1)
    assert all(not reactions(game, n) for n in NAMES)
    assert not any("quick note" in m[-1].content for m, _ in game.llm.calls[calls:])
