"""
Who talks in the discussion?

Asking every player to speak in every round costs one model call each, and most
of those turns produce nothing new. This module decides, without any model
call, whether a player takes their turn: talkative personalities speak more
often, and a player who was just addressed always answers.
"""
import random
import re
from typing import Optional

from backend.models.game_models import PlayerProfile

EXTRAVERT_CHANCE = 0.85      # personality types starting with E
INTROVERT_CHANCE = 0.55      # personality types starting with I
RECENTLY_SPOKE_FACTOR = 0.7  # someone who spoke last round is less eager to speak again
RECENT_LINES = 3             # how many of the latest lines count as "just addressed"


def is_addressed(name: str, conversation: str) -> bool:
    """Is `name` mentioned in the last few lines of the conversation?"""
    lines = [line for line in conversation.strip().split("\n") if line.strip()]
    recent = "\n".join(lines[-RECENT_LINES:])
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", recent) is not None


def speak_probability(profile: PlayerProfile, conversation: str, spoke_last_round: bool) -> float:
    """Chance (0 to 1) that the player takes their turn to speak"""
    if is_addressed(profile.name, conversation):
        return 1.0
    chance = EXTRAVERT_CHANCE if profile.personality.value.startswith("E") else INTROVERT_CHANCE
    return chance * RECENTLY_SPOKE_FACTOR if spoke_last_round else chance


def should_speak(profile: PlayerProfile, conversation: str, spoke_last_round: bool,
                 rng: Optional[random.Random] = None) -> bool:
    """Does the player take their turn now? (random, so pass a seeded `rng` in tests)"""
    return (rng or random).random() < speak_probability(profile, conversation, spoke_last_round)
