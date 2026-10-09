"""Game Master templates and discussion pacing (no LLM)."""
from backend.game.game_master import GameMaster
from backend.models.game_models import PersonalityType, PlayerProfile, Sex

gm = GameMaster()


def test_gm_has_no_llm():
    assert not hasattr(gm, "llm")


def test_announcements_contain_facts():
    players = [PlayerProfile(id=f"p{i}", name=f"P{i}", sex=Sex.MALE, age=30,
                             personality=PersonalityType.INTJ) for i in range(3)]
    assert "3" in gm.narrate_game_start(players)
    assert "2" in gm.announce_night(2)
    assert "Bob was killed." in gm.announce_day(1, "Bob was killed.")
    text = gm.narrate_elimination("Bob", "seer", by_vote=True)
    assert "Bob" in text and "seer" in text and "voted out" in text
    assert "killed during the night" in gm.narrate_elimination("Bob", "seer", by_vote=False)
    win = gm.announce_winner("villagers", ["Ann", "Cy"])
    assert "villagers" in win and "Ann, Cy" in win
    assert "none" in gm.announce_winner("werewolves", [])


def test_night_announcements_are_neutral():
    # No arguments, so no player names can leak into the shared game log
    assert gm.announce_werewolf_awakening()
    assert gm.announce_werewolf_decision()


def test_discussion_pacing():
    f = gm.should_continue_discussion
    assert f(5, 1, 8, 5) is True            # normal early round
    assert f(0, 1, 8, 5) is True            # silent first round gets a second chance
    assert f(0, 2, 8, 5) is False           # silent second round ends it
    assert f(1, 3, 9, 5) is False           # round 3+: too few speakers
    assert f(4, 3, 9, 5) is True            # round 3+: enough speakers
    assert f(8, 5, 8, 5) is False           # max rounds reached
