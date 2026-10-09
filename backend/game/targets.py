"""Helpers to turn free-text LLM answers into valid player names"""
import random
import re
from typing import Iterable, Optional


def match_player_name(text: Optional[str], candidates: Iterable[str]) -> Optional[str]:
    """
    Find which candidate a free-text answer refers to.

    Matching is case-insensitive and ignores surrounding punctuation. An exact
    match wins; otherwise a candidate named as a whole word inside the text is
    returned (the first one mentioned, longest name first on ties).

    Returns:
        The candidate name as spelled in `candidates`, or None if no match
    """
    candidates = list(candidates)
    if not text or not text.strip():
        return None
    cleaned = text.strip().strip("\"'`.,;:!?*()[]{} \n\t")
    
    for name in candidates:
        if name.lower() == cleaned.lower():
            return name
    
    best = None  # (position, -length, name)
    for name in candidates:
        found = re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text, re.IGNORECASE)
        if found:
            key = (found.start(), -len(name), name)
            if best is None or key < best:
                best = key
    return best[2] if best else None


def pick_target(text: Optional[str], candidates: Iterable[str]) -> Optional[str]:
    """Parse `text` into one of `candidates`, or choose one at random if unclear"""
    candidates = list(candidates)
    if not candidates:
        return None
    return match_player_name(text, candidates) or random.choice(candidates)
