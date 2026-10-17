"""
JSON schemas for the decisions players make, and parsers for the answers.

With a schema, Ollama only lets the model produce JSON that matches it, so a
vote or a night target is always one of the valid names (an `enum`), and the
code does not have to guess what a sentence meant.
"""
import json
import re
from typing import Any, Dict, Iterable, Optional, Tuple

NONE = "none"


def target_schema(names: Iterable[str], vote: bool = False, sacrifice: bool = False) -> Dict[str, Any]:
    """
    `{"reason": str, "target": <one of names>}`; without names any string is accepted

    The reason comes first: the model reasons, then chooses. A `vote` also names the runner-up
    and why not (`"not_chosen": {"player", "why_not"}`, only when there is another candidate);
    with `sacrifice` (a werewolf voting) the answer says whether a mate is sacrificed on purpose.
    """
    names = list(names)
    target: Dict[str, Any] = {"type": "string"}
    if names:
        target["enum"] = names
    properties: Dict[str, Any] = {"reason": {"type": "string"}, "target": target}
    required = ["reason", "target"]
    if vote and len(names) > 1:
        properties["not_chosen"] = {
            "type": "object",
            "properties": {"player": {"type": "string", "enum": names}, "why_not": {"type": "string"}},
            "required": ["player", "why_not"],
        }
        required.append("not_chosen")
    if sacrifice:
        properties["sacrifice_mate"] = {"type": "boolean"}
        required.append("sacrifice_mate")
    return {"type": "object", "properties": properties, "required": required}


def discussion_schema() -> Dict[str, Any]:
    """
    `{"reason": str, "speak": bool, "message": str}`: why the player says it (private), whether
    they talk, and what they say out loud
    """
    return {
        "type": "object",
        "properties": {"reason": {"type": "string"}, "speak": {"type": "boolean"}, "message": {"type": "string"}},
        "required": ["reason", "speak", "message"],
    }


GUESSES = ["werewolf", "villager", "unsure"]
CONFIDENCES = ["low", "medium", "high"]
PLANS = ["frame", "ignore", "ally"]       # what a werewolf plans for a player who is not in its pack


def diary_schema(names: Iterable[str], wolf: bool = False) -> Dict[str, Any]:
    """
    `{"summary": str, "opinions": [{"player", "guess", "confidence", "reason"}]}`:
    what the player thinks of this step, and of each other player. A werewolf knows who is a
    werewolf, so for it (`wolf`) `names` are the players outside the pack and each opinion is a
    `plan` ("frame", "ignore" or "ally") instead of a guess.
    """
    if wolf:
        opinion = {
            "type": "object",
            "properties": {
                "player": {"type": "string", "enum": list(names)},
                "reason": {"type": "string"},
                "plan": {"type": "string", "enum": PLANS},
            },
            "required": ["player", "reason", "plan"],
        }
    else:
        opinion = {
            "type": "object",
            "properties": {
                "player": {"type": "string", "enum": list(names)},
                "reason": {"type": "string"},      # before the label: the model reasons, then concludes
                "guess": {"type": "string", "enum": GUESSES},
                "confidence": {"type": "string", "enum": CONFIDENCES},
            },
            "required": ["player", "reason", "guess", "confidence"],
        }
    return {
        "type": "object",
        "properties": {"summary": {"type": "string"},
                       "opinions": {"type": "array", "items": opinion}},
        "required": ["summary", "opinions"],
    }


def reaction_schema() -> Dict[str, Any]:
    """`{"text": str}`: a short diary note about a change in the discussion"""
    return {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}


def parse_reaction(text: Optional[str]) -> Optional[str]:
    """The note of a reaction answer, or None when it is empty or not valid"""
    data = parse_json(text)
    note = data.get("text") if data else None
    return note.strip() if isinstance(note, str) and note.strip() else None


def psytest_schema(count: int) -> Dict[str, Any]:
    """
    `{"answers": [{"statement": "...", "rating": <1-5>}, ...]}` with exactly `count` answers

    The player writes each statement before its rating, so a rating cannot slip onto
    another statement.
    """
    item = {
        "type": "object",
        "properties": {"statement": {"type": "string"}, "rating": {"type": "integer", "enum": [1, 2, 3, 4, 5]}},
        "required": ["statement", "rating"],
    }
    return {
        "type": "object",
        "properties": {"answers": {"type": "array", "minItems": count, "maxItems": count, "items": item}},
        "required": ["answers"],
    }


def witch_schema(poison_targets: Iterable[str]) -> Dict[str, Any]:
    """`{"reason": str, "save": bool, "poison": <a name or "none">}`"""
    return {
        "type": "object",
        "properties": {
            "reason": {"type": "string"},
            "save": {"type": "boolean"},
            "poison": {"type": "string", "enum": list(poison_targets) + [NONE]},
        },
        "required": ["reason", "save", "poison"],
    }


def parse_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """The JSON object in `text` (code fences tolerated), or None"""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def parse_reason(text: Optional[str]) -> str:
    """The `reason` of a decision answer, trimmed ('' when there is none)"""
    data = parse_json(text)
    reason = data.get("reason") if data else None
    return reason.strip() if isinstance(reason, str) else ""


def parse_target(text: Optional[str], names: Iterable[str]) -> Optional[str]:
    """The valid name in a `{"target": ...}` answer (spelled as in `names`), or None"""
    data = parse_json(text)
    target = data.get("target") if data else None
    if not isinstance(target, str):
        return None
    for name in names:
        if name.lower() == target.strip().lower():
            return name
    return None


def parse_decision(text: Optional[str], names: Iterable[str]) -> Optional[Dict[str, Any]]:
    """
    A decision `{"target", "reason", "not_chosen", "sacrifice_mate"}` from a decision answer, or None
    when the target is not one of `names`. The reason may be empty (the caller asks again);
    `not_chosen` is `{"player", "why_not"}` or None and `sacrifice_mate` a bool (false when absent).
    """
    names = list(names)
    target = parse_target(text, names)
    if target is None:
        return None
    data = parse_json(text) or {}
    not_chosen = data.get("not_chosen")
    if isinstance(not_chosen, dict) and isinstance(not_chosen.get("why_not"), str):
        player = parse_target(json.dumps({"target": not_chosen.get("player")}), names)
        not_chosen = ({"player": player, "why_not": not_chosen["why_not"].strip()}
                      if player and player != target else None)
    else:
        not_chosen = None
    return {"target": target, "reason": parse_reason(text), "not_chosen": not_chosen,
            "sacrifice_mate": data.get("sacrifice_mate") is True}


# Gemma likes typographic quotes: it writes curly apostrophes inside the message and then
# closes the string with a curly quote too, so the JSON never closes:
#   {"speak": true, "message": "Bob, it’s odd.”} ...garbage...
_BROKEN_DISCUSSION = re.compile(
    r'^\s*\{\s*(?:"reason"\s*:\s*"[^"]*"\s*,\s*)?"speak"\s*:\s*(true|false)\s*,\s*"message"\s*:\s*"(.*?)["“”]\s*\}',
    re.DOTALL)


def parse_discussion(text: Optional[str]) -> Optional[Tuple[bool, str]]:
    """
    `(speak, message)` from a discussion answer, or None if it is not valid

    Accepts the one malformed shape models really produce: the closing quote of
    the message replaced by a typographic quote (anything after the `}` is ignored).
    """
    data = parse_json(text)
    if data is None and text:
        broken = _BROKEN_DISCUSSION.match(text)
        if broken:
            data = {"speak": broken.group(1) == "true", "message": broken.group(2)}
    if not data or not isinstance(data.get("speak"), bool) or not isinstance(data.get("message"), str):
        return None
    return data["speak"], data["message"]


def parse_witch(text: Optional[str], poison_targets: Iterable[str]) -> Optional[Tuple[bool, Optional[str]]]:
    """`(save, name to poison or None)` from a witch answer, or None if it is not valid"""
    data = parse_json(text)
    if not data or not isinstance(data.get("save"), bool) or not isinstance(data.get("poison"), str):
        return None
    poison = data["poison"].strip()
    if poison.lower() == NONE:
        return data["save"], None
    for name in poison_targets:
        if name.lower() == poison.lower():
            return data["save"], name
    return data["save"], None


def parse_diary(text: Optional[str], names: Iterable[str], wolf: bool = False) -> Optional[Dict[str, Any]]:
    """
    A clean diary entry `{"summary", "opinions"}` from a diary answer, or None if it is not valid.
    Opinions about unknown players are dropped, and a player appears once (the first opinion wins).
    For a werewolf (`wolf`) an opinion is `{"player", "plan", "reason"}`.
    """
    data = parse_json(text)
    if not data or not isinstance(data.get("summary"), str) or not isinstance(data.get("opinions"), list):
        return None
    valid = {name.lower(): name for name in names}
    opinions, seen = [], set()
    for item in data["opinions"]:
        if not isinstance(item, dict) or not isinstance(item.get("player"), str):
            continue
        name = valid.get(item["player"].strip().lower())
        guess, confidence, reason = item.get("guess"), item.get("confidence"), item.get("reason")
        if wolf:
            if name is None or name in seen or item.get("plan") not in PLANS or not isinstance(reason, str):
                continue
            seen.add(name)
            opinions.append({"player": name, "plan": item["plan"], "reason": reason.strip()})
            continue
        if (name is None or name in seen or guess not in GUESSES or confidence not in CONFIDENCES
                or not isinstance(reason, str)):
            continue
        seen.add(name)
        opinions.append({"player": name, "guess": guess, "confidence": confidence,
                         "reason": reason.strip()})
    if not opinions:
        return None
    return {"summary": data["summary"].strip(), "opinions": opinions}


def parse_psytest(text: Optional[str], count: int) -> Optional[list]:
    """The `count` ratings (1-5) of a psychological test, in order, or None if the answer is not valid"""
    data = parse_json(text)
    answers = data.get("answers") if data else None
    if not isinstance(answers, list) or len(answers) != count:
        return None
    ratings = [a.get("rating") if isinstance(a, dict) else None for a in answers]
    if not all(isinstance(r, int) and not isinstance(r, bool) and 1 <= r <= 5 for r in ratings):
        return None
    return ratings
