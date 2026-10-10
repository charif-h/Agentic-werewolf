"""
Who talks in the discussion?

Asking every player to speak in every round costs one model call each, and most
of those turns produce nothing new. This module decides, without any model
call, whether a player takes their turn: talkative personalities speak more
often, a player who was just addressed always answers, and a player who has
been silent for a long time speaks up. `is_repetition` spots a line that only
repeats what was just said.

(These rules come from the motivation-score idea of the old
copilot/implement-new-conversation-mechanism branch, minus its cost: that
design asked every player for a message in every round and published only the
best one, so it needed many more model calls. Here the decision is taken before
the call.)
"""
import random
import re
from typing import Iterable, Optional

from backend.models.game_models import PlayerProfile

EXTRAVERT_CHANCE = 0.85      # personality types starting with E
INTROVERT_CHANCE = 0.55      # personality types starting with I
RECENTLY_SPOKE_FACTOR = 0.7  # someone who spoke last round is less eager to speak again
RECENT_LINES = 3             # how many of the latest lines count as "just addressed"
SILENCE_BOOST = ((8, 0.20), (4, 0.10))  # (messages without speaking, added chance), longest first
MAX_CHANCE = 0.95            # a silent player is encouraged, never forced (only being addressed is)
REPETITION_LINES = 8         # how far back a line can be a repetition
REPETITION_THRESHOLD = 0.7   # share of its keywords that were already said
MIN_KEYWORDS = 3             # shorter lines cannot be judged
STOPWORDS = frozenset(
    ("i you the a an is are was were been be have has had do does did will would could should can may "
     "might must this that these those and or but not no yes to from in on at for with it its "
     "your my me we our they their he she his her him them of as so if then than just really "
     "very about what why how who when there here").split()
)


def is_addressed(name: str, conversation: str) -> bool:
    """Is `name` mentioned in the last few lines of the conversation?"""
    lines = [line for line in conversation.strip().split("\n") if line.strip()]
    recent = "\n".join(lines[-RECENT_LINES:])
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", recent) is not None


def speak_probability(profile: PlayerProfile, conversation: str, spoke_last_round: bool,
                      messages_since_spoke: Optional[int] = None) -> float:
    """
    Chance (0 to 1) that the player takes their turn to speak

    `messages_since_spoke` is how many lines were said since this player last
    spoke (None = not known). A long silence raises the chance a little.
    """
    if is_addressed(profile.name, conversation):
        return 1.0
    chance = EXTRAVERT_CHANCE if profile.personality.value.startswith("E") else INTROVERT_CHANCE
    if spoke_last_round:
        chance *= RECENTLY_SPOKE_FACTOR
    if messages_since_spoke is not None:
        for after, boost in SILENCE_BOOST:
            if messages_since_spoke >= after:
                chance += boost
                break
    return min(chance, MAX_CHANCE)


def should_speak(profile: PlayerProfile, conversation: str, spoke_last_round: bool,
                 rng: Optional[random.Random] = None,
                 messages_since_spoke: Optional[int] = None) -> bool:
    """Does the player take their turn now? (random, so pass a seeded `rng` in tests)"""
    chance = speak_probability(profile, conversation, spoke_last_round, messages_since_spoke)
    return (rng or random).random() < chance


def keywords(text: str) -> set:
    """The meaningful words of a line (lower case, without the common ones)"""
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def is_repetition(text: str, recent_lines: Iterable[str]) -> bool:
    """
    Does `text` only repeat what was said in the latest lines?

    True when at least REPETITION_THRESHOLD of its keywords already appear in the
    last REPETITION_LINES lines (a "[Name]" prefix does not count).
    """
    new = keywords(text)
    if len(new) < MIN_KEYWORDS:
        return False
    said = set()
    for line in list(recent_lines)[-REPETITION_LINES:]:
        said |= keywords(re.sub(r"^\[[^\]]*\]\s*", "", line))
    return len(new & said) / len(new) >= REPETITION_THRESHOLD
