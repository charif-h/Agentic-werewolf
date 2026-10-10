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


def target_schema(names: Iterable[str]) -> Dict[str, Any]:
    """`{"target": <one of names>}`; without names any string is accepted"""
    names = list(names)
    target: Dict[str, Any] = {"type": "string"}
    if names:
        target["enum"] = names
    return {"type": "object", "properties": {"target": target}, "required": ["target"]}


def discussion_schema() -> Dict[str, Any]:
    """`{"speak": bool, "message": str}`: whether the player talks, and what they say"""
    return {
        "type": "object",
        "properties": {"speak": {"type": "boolean"}, "message": {"type": "string"}},
        "required": ["speak", "message"],
    }


def witch_schema(poison_targets: Iterable[str]) -> Dict[str, Any]:
    """`{"save": bool, "poison": <a name or "none">}`"""
    return {
        "type": "object",
        "properties": {
            "save": {"type": "boolean"},
            "poison": {"type": "string", "enum": list(poison_targets) + [NONE]},
        },
        "required": ["save", "poison"],
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


# Gemma likes typographic quotes: it writes curly apostrophes inside the message and then
# closes the string with a curly quote too, so the JSON never closes:
#   {"speak": true, "message": "Bob, it’s odd.”} ...garbage...
_BROKEN_DISCUSSION = re.compile(
    r'^\s*\{\s*"speak"\s*:\s*(true|false)\s*,\s*"message"\s*:\s*"(.*?)["“”]\s*\}',
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
