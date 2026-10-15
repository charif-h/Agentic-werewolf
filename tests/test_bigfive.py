"""Big Five personality: levels, the psychological test, and its flag."""
import json
from unittest.mock import patch

import pytest

from backend.agents import psytest
from backend.agents.player_agent import PlayerAgent
from backend.agents.profile_generator import generate_all_players
from backend.api.serializers import serialize_player
from backend.config import Settings
from backend.game.game_logic import WerewolfGame
from backend.llm import FakeLLMClient, schemas
from backend.models.game_models import BigFive, PlayerProfile, Role, Sex
from backend.models.personality import BEHAVIOR, LEVEL_NAMES, TRAITS, level_from_score


def answers_for(levels):
    """Answers whose scores fall in the middle of the range of `levels` (trait -> 1-5)"""
    result = []
    for trait, _, reverse in psytest.ITEMS:
        level = levels[trait]
        target_sum = level * 5 + 3            # 8, 13, 18, 23, 28: the middle of each level range
        base, extra = divmod(target_sum, 6)
        index = sum(1 for t, _, _ in psytest.ITEMS[:len(result)] if t == trait)
        value = base + (1 if index < extra else 0)
        result.append(6 - value if reverse else value)
    return result


def profile(personality=None, name="Ann"):
    return PlayerProfile(id=name, name=name, sex=Sex.FEMALE, age=30,
                         personality=personality or BigFive(), role=Role.VILLAGER)


def test_test_has_six_statements_per_trait_and_some_are_reversed():
    for trait in TRAITS:
        items = [reverse for t, _, reverse in psytest.ITEMS if t == trait]
        assert len(items) == 6 and 0 < sum(items) < 6
    assert len(psytest.statements()) == 30 and not any("(R)" in s for s in psytest.statements())


@pytest.mark.parametrize("score,level", [(6, 1), (10, 1), (11, 2), (15, 2), (16, 3), (20, 3),
                                         (21, 4), (25, 4), (26, 5), (30, 5)])
def test_score_ranges_give_the_levels_of_the_questionnaire(score, level):
    assert level_from_score(score) == level


def test_reverse_items_count_six_minus_the_answer():
    assert psytest.score([5] * 30)["openness"] == 3 * 5 + 3 * 1          # 3 normal items at 5, 3 reversed at 1
    assert psytest.score([3] * 30) == {trait: 18 for trait in TRAITS}


def test_a_player_who_answers_as_described_is_confirmed():
    personality = BigFive(openness=1, conscientiousness=2, extraversion=3, agreeableness=4, neuroticism=5)
    check = psytest.evaluate(answers_for(personality.levels()), personality)
    assert check.completed and check.confirmed and check.flagged == []
    assert check.measured == personality.levels()


def test_traits_that_differ_from_the_description_are_flagged():
    personality = BigFive(extraversion=5, neuroticism=1)
    check = psytest.evaluate([3] * 30, personality)               # a neutral answerer
    assert check.completed and not check.confirmed
    assert check.flagged == ["extraversion", "neuroticism"]


def test_unusable_answers_leave_the_test_not_completed_and_flag_nothing():
    for bad in (None, [3] * 29, [3] * 29 + [9]):
        check = psytest.evaluate(bad, BigFive())
        assert not check.completed and not check.confirmed and check.flagged == []


def test_parse_psytest():
    assert schemas.parse_psytest(json.dumps({"answers": [3] * 30}), 30) == [3] * 30
    assert schemas.parse_psytest(json.dumps({"answers": [3] * 29}), 30) is None
    assert schemas.parse_psytest(json.dumps({"answers": ["3"] * 30}), 30) is None
    assert schemas.parse_psytest(json.dumps({"answers": [True] * 30}), 30) is None
    assert schemas.parse_psytest("not json", 30) is None


def test_generated_players_have_a_level_for_every_trait():
    for player in generate_all_players(20):
        assert all(1 <= level <= 5 for level in player.personality.levels().values())


def test_description_gives_one_line_per_trait_with_its_level():
    text = BigFive(extraversion=5, neuroticism=1).describe()
    assert len(text.splitlines()) == 5
    assert f"Extraversion: {LEVEL_NAMES[5]} - {BEHAVIOR['extraversion'][5]}" in text
    assert "very high extraversion" in BigFive(extraversion=5).summary()


def test_agent_takes_the_test_in_character_and_the_result_is_kept_on_the_profile():
    personality = BigFive(openness=4, extraversion=2)
    levels = personality.levels()
    llm = FakeLLMClient(json.dumps({"answers": answers_for(levels)}))
    agent = PlayerAgent(profile(personality), llm)
    check = agent.take_psytest()
    assert check.confirmed and agent.profile.persona_check is check
    messages, options = llm.calls[0]
    assert "Extraversion: low" in messages[0].content            # the persona is in the system prompt
    assert "1. I have a vivid imagination." in messages[-1].content and "30. " in messages[-1].content
    assert options["json_schema"]["properties"]["answers"]["minItems"] == 30
    assert "Role" not in messages[0].content and "Your role" not in messages[0].content


def test_a_model_that_cannot_answer_does_not_stop_the_player():
    agent = PlayerAgent(profile(), FakeLLMClient(RuntimeError("down")))
    check = agent.take_psytest()
    assert not check.completed and agent.profile.persona_check == check


def test_the_game_tests_every_player_during_setup_and_counts_the_flags():
    llm = FakeLLMClient("")                                       # neutral answers (all 3)
    game = WerewolfGame(num_players=6, llm=llm)
    game.setup_game()
    checks = [p.persona_check for p in game.state.players]
    assert all(c is not None and c.completed for c in checks) and len(llm.calls) == 6
    stats = game.metrics.snapshot()
    assert stats["psytests"] == 6
    assert stats["psytest_flagged"] == sum(1 for c in checks if c.flagged)


def test_the_test_can_be_turned_off():
    llm = FakeLLMClient("")
    game = WerewolfGame(num_players=4, llm=llm)
    with patch("backend.game.game_logic.get_settings", return_value=Settings(_env_file=None, psytest_enabled=False)):
        game.setup_game()
    assert llm.calls == [] and all(p.persona_check is None for p in game.state.players)


def test_the_api_shows_the_levels_and_the_result_of_the_test():
    player = profile(BigFive(extraversion=5))
    assert serialize_player(player)["personality"]["extraversion"] == "very high"
    assert "persona_check" not in serialize_player(player)
    player.persona_check = psytest.evaluate([3] * 30, player.personality)
    shown = serialize_player(player, detailed=True)
    assert shown["persona_check"]["flagged"] == ["extraversion"] and shown["persona_check"]["confirmed"] is False
