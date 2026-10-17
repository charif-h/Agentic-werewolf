"""
Who talks in the discussion?

Asking every player to speak in every round costs one model call each, and most
of those turns produce nothing new. This module decides, without any model
call, whether a player takes their turn: players with high extraversion speak more
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

# chance to take a turn, by level of extraversion (1 = very low ... 5 = very high)
SPEAK_CHANCE = {1: 0.45, 2: 0.55, 3: 0.70, 4: 0.85, 5: 0.92}
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


ACCUSATION_WORDS = ("accuse", "suspect", "suspicious", "lying", "liar", "lied", "werewolf", "wolf", "guilty",
                    "blame", "fishy", "dodging", "deflect", "vote you", "vote for you", "eliminate you")
ROLE_CLAIM = re.compile(r"\b(i am|i'm|im)\s+(the|a|an)?\s*(seer|witch|hunter|guard|villager|werewolf)\b")
SPEAKER = re.compile(r"^\[([^\]]*)\]\s*(.*)$", re.DOTALL)


def split_line(line: str) -> tuple:
    """`("Bob", "I trust Cy.")` from "[Bob] I trust Cy." (an empty speaker for a line without one)"""
    found = SPEAKER.match(line.strip())
    return (found.group(1), found.group(2)) if found else ("", line.strip())


def mentions(name: str, text: str) -> bool:
    """Is `name` named as a whole word in `text`?"""
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text) is not None


def mentioned_in(name: str, lines: Iterable[str]) -> bool:
    """Do the lines of other players name `name`?"""
    return any(speaker != name and mentions(name, text) for speaker, text in map(split_line, lines))


def is_accused(name: str, lines: Iterable[str]) -> bool:
    """Does a line of another player name `name` together with an accusation word?"""
    for speaker, text in map(split_line, lines):
        lowered = text.lower()
        if speaker != name and mentions(name, text) and any(word in lowered for word in ACCUSATION_WORDS):
            return True
    return False


def has_claim(name: str, lines: Iterable[str]) -> bool:
    """Does another player claim a role in these lines ("I am the seer")?"""
    return any(speaker != name and ROLE_CLAIM.search(text.lower()) for speaker, text in map(split_line, lines))


def accused_player(text: str, names: Iterable[str], me: str) -> Optional[str]:
    """The player `text` (a line of `me`) accuses: a name together with an accusation word, else None"""
    lowered = text.lower()
    if not any(word in lowered for word in ACCUSATION_WORDS):
        return None
    for name in names:
        if name != me and mentions(name, text):
            return name
    return None


def reaction_trigger(name: str, new_lines: Iterable[str], own_line: Optional[str], previous_accused: Optional[str],
                     names: Iterable[str]) -> Optional[str]:
    """
    Why this player should note a reaction in the diary after their turn, or None for a quiet turn:
    "accused" (named with an accusation), "claim" (somebody claimed a role) or "suspect_changed" (their
    own line accuses someone other than before). A cheap heuristic, no model call.
    """
    new_lines = list(new_lines)
    if is_accused(name, new_lines):
        return "accused"
    if has_claim(name, new_lines):
        return "claim"
    if own_line:
        accused = accused_player(own_line, names, name)
        if accused and previous_accused and accused != previous_accused:
            return "suspect_changed"
    return None


def speak_probability(profile: PlayerProfile, conversation: str, spoke_last_round: bool,
                      messages_since_spoke: Optional[int] = None,
                      new_lines: Optional[Iterable[str]] = None) -> float:
    """
    Chance (0 to 1) that the player takes their turn to speak

    `messages_since_spoke` is how many lines were said since this player last
    spoke (None = not known). A long silence raises the chance a little. A player
    named or accused in the `new_lines` (everything said since their last turn) always answers.
    """
    if is_addressed(profile.name, conversation) or (new_lines is not None and mentioned_in(profile.name, new_lines)):
        return 1.0
    chance = SPEAK_CHANCE[profile.personality.extraversion]
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
                 messages_since_spoke: Optional[int] = None,
                 new_lines: Optional[Iterable[str]] = None) -> bool:
    """Does the player take their turn now? (random, so pass a seeded `rng` in tests)"""
    chance = speak_probability(profile, conversation, spoke_last_round, messages_since_spoke, new_lines)
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
