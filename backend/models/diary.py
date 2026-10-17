"""
Typed diary entries of a player

An entry is `{id, step, kind, text, data}`. `kind` says what the entry is, `text` is what the
player wrote and `data` holds the structured part (the role, the pack, the opinions...), so that
prompts never depend on parsing free text. The night and day summaries also keep the old
`summary` and `opinions` fields, so clients written before the typed entries keep working.
"""
from typing import Any, Dict, Optional

ROLE_CARD = "role_card"
PACK = "pack"
REACTION = "reaction"
DECISION = "decision"
PLAN = "plan"
NIGHT_SUMMARY = "night_summary"
DAY_SUMMARY = "day_summary"

DIARY_KINDS = (ROLE_CARD, PACK, REACTION, DECISION, PLAN, NIGHT_SUMMARY, DAY_SUMMARY)

# Entries that always stay in the prompts, whatever the budget ("who I am")
HEADER_KINDS = (ROLE_CARD, PACK)


def make_entry(entry_id: int, step: str, kind: str, text: str,
               data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """A diary entry; `kind` must be one of `DIARY_KINDS`"""
    if kind not in DIARY_KINDS:
        raise ValueError(f"Unknown diary entry kind: {kind}")
    entry: Dict[str, Any] = {"id": entry_id, "step": step, "kind": kind, "text": text, "data": data or {}}
    if kind in (NIGHT_SUMMARY, DAY_SUMMARY):          # old shape, kept for compatibility
        entry["summary"] = text
        entry["opinions"] = entry["data"].get("opinions", [])
    return entry
