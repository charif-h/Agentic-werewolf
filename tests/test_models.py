"""Basic tests for models and profile generation (no LLM required)."""
from datetime import datetime

from backend.agents.profile_generator import generate_all_players
from backend.models.game_models import (
    Discussion,
    GameState,
    Message,
    PersonalityType,
    PlayerProfile,
    Sex,
)


def test_player_profile():
    player = PlayerProfile(
        id="test_1", name="Test Player", sex=Sex.MALE, age=25,
        personality=PersonalityType.INTJ,
    )
    assert player.name == "Test Player"
    assert player.get_personality_description()


def test_generate_all_players_unique_names():
    players = generate_all_players(24)
    assert len(players) == 24
    assert len({p.name for p in players}) == 24
    assert all(18 <= p.age <= 80 for p in players)


def test_game_state_stores_discussions():
    message = Message(sender="Alice", content="Bob seems suspicious",
                      timestamp=datetime.now().isoformat())
    state = GameState()
    state.discussions.append(
        Discussion(round_number=1, topic="Share suspicions", messages=[message])
    )
    assert len(state.discussions) == 1
    assert state.discussions[0].messages[0].sender == "Alice"
