"""Rough token budgeting (no tokenizer needed)"""
from typing import List

OMISSION_NOTICE = "[earlier messages omitted]"


def estimate_tokens(text: str) -> int:
    """
    Cheap upper-ish estimate of the number of tokens in `text`

    Counts about one token per 3 characters, which slightly overestimates
    English and keeps us on the safe side of the context window.
    """
    return len(text) // 3 + 1


def fit_lines(lines: List[str], max_tokens: int) -> List[str]:
    """
    Keep the most recent `lines` that fit in `max_tokens`

    When older lines had to go, an omission notice is put first. A single line
    longer than the whole budget is cut from its start.
    """
    kept: List[str] = []
    used = 0
    for line in reversed(lines):
        cost = estimate_tokens(line) + 1          # +1 for the newline
        if used + cost > max_tokens:
            if not kept:                          # even the newest line is too long
                kept.append(line[-max(max_tokens - 1, 1) * 3:])
            break
        kept.append(line)
        used += cost
    kept.reverse()
    if len(kept) < len(lines):
        kept.insert(0, OMISSION_NOTICE)
    return kept


def fit_text(text: str, max_tokens: int) -> str:
    """`fit_lines` for a multi-line string"""
    if not text:
        return text
    return "\n".join(fit_lines(text.split("\n"), max_tokens))
