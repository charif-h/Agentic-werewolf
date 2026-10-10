"""Ideas taken from the old motivation-score branch: silence boost and repetition filter."""
import random
from unittest.mock import patch

import pytest

from backend.config import Settings
from backend.game import talkativeness
from backend.game.game_logic import WerewolfGame
from backend.llm import FakeLLMClient
from backend.models.game_models import PersonalityType, PlayerProfile, Sex


def player(name="Eve", personality=PersonalityType.INTJ):
    return PlayerProfile(id=name, name=name, sex=Sex.FEMALE, age=30, personality=personality)


# --- silence boost ---------------------------------------------------------------------------

def test_a_long_silence_raises_the_chance_to_speak():
    p = player()
    base = talkativeness.speak_probability(p, "", False)
    assert talkativeness.speak_probability(p, "", False, messages_since_spoke=0) == base
    assert talkativeness.speak_probability(p, "", False, messages_since_spoke=3) == base
    assert talkativeness.speak_probability(p, "", False, messages_since_spoke=4) == pytest.approx(base + 0.10)
    assert talkativeness.speak_probability(p, "", False, messages_since_spoke=7) == pytest.approx(base + 0.10)
    assert talkativeness.speak_probability(p, "", False, messages_since_spoke=8) == pytest.approx(base + 0.20)
    assert talkativeness.speak_probability(p, "", False, messages_since_spoke=50) == pytest.approx(base + 0.20)


def test_the_boost_never_forces_a_player_to_speak():
    extravert = player(personality=PersonalityType.ENFP)
    assert talkativeness.speak_probability(extravert, "", False, messages_since_spoke=99) == talkativeness.MAX_CHANCE < 1


def test_being_addressed_still_beats_everything():
    assert talkativeness.speak_probability(player("Eve"), "[Bob] Eve, why?", True, messages_since_spoke=0) == 1.0


def test_should_speak_uses_the_silence_boost():
    p = player()
    quiet = sum(talkativeness.should_speak(p, "", False, random.Random(i), messages_since_spoke=0) for i in range(2000))
    long_silent = sum(talkativeness.should_speak(p, "", False, random.Random(i), messages_since_spoke=9) for i in range(2000))
    assert long_silent > quiet + 200            # about 0.55 against 0.75


# --- repetition filter ---------------------------------------------------------------------------

RECENT = [
    "[Hassan] Mark, your silence is becoming a significant point of concern.",
    "[Bassam] Harper, I appreciate your desire to help Thomas, but I think we need everyone's perspective.",
    "[Thomas] Harper, I'm still worried about Kimberly. She hasn't said a word.",
]


@pytest.mark.parametrize("text,expected", [
    ("Mark, your silence is a significant concern.", True),                 # same point again
    ("Thomas is worried about Kimberly, she has not said a word.", True),
    ("Dee changed her story about the well twice.", False),                # new information
    ("I saw Eli near the barn at night, carrying something.", False),
    ("Hmm.", False),                                                        # too short to judge
    ("", False),
])
def test_is_repetition(text, expected):
    assert talkativeness.is_repetition(text, RECENT) is expected


def test_a_line_is_only_compared_with_the_recent_ones():
    old = ["[A] The well was poisoned by someone from the village."] + ["[B] something else entirely"] * 9
    assert not talkativeness.is_repetition("The well was poisoned by someone from the village.", old)
    assert talkativeness.is_repetition("The well was poisoned by someone from the village.", old[:5])


def test_the_name_prefix_does_not_count_as_a_keyword():
    assert not talkativeness.is_repetition("Hassan Hassan Hassan Hassan", ["[Hassan] hello there"])


def test_keywords_ignore_common_words():
    assert talkativeness.keywords("I think the well is the problem") == {"think", "well", "problem"}


# --- in the discussion ------------------------------------------------------------------------------

def run_discussion(llm, gate=True, players=6):
    game = WerewolfGame(num_players=players, llm=llm)
    game.setup_game()
    with patch("backend.game.game_logic.get_settings", return_value=Settings(_env_file=None, discussion_gate=gate)):
        messages = game.conduct_discussion()
    return game, messages


def test_a_player_who_only_repeats_is_not_published_and_is_counted():
    game, messages = run_discussion(FakeLLMClient("The well was poisoned by someone from the village."))
    assert len(messages) == 1                       # the first line is new, everything after repeats it
    assert game.metrics.snapshot()["repeated_lines"] >= 1


def test_new_information_is_published():
    words = iter("barn river lantern cellar bridge orchard anvil harvest tavern chapel meadow quarry "
                 "granary bakery smithy mill pond forest hilltop cottage stable market tower fountain "
                 "crypt garden dock lighthouse vineyard windmill cabin glacier canyon harbor temple".split() * 5)
    game, messages = run_discussion(FakeLLMClient(lambda m: f"{next(words)} {next(words)} {next(words)} {next(words)}"))
    assert len(messages) > 3
    assert game.metrics.snapshot()["repeated_lines"] == 0


def test_the_filter_follows_the_gate_setting():
    game, messages = run_discussion(FakeLLMClient("The well was poisoned by someone from the village."), gate=False)
    assert len(messages) > 5
    assert game.metrics.snapshot()["repeated_lines"] == 0


def test_the_metrics_snapshot_has_the_counter():
    from backend.llm.metrics import LLMMetrics
    metrics = LLMMetrics()
    metrics.add_repeated_line()
    assert metrics.snapshot()["repeated_lines"] == 1
    metrics.reset()
    assert metrics.snapshot()["repeated_lines"] == 0
