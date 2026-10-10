"""
Chat formatting for models without a system role (Gemma).

Gemma's chat template only knows "user" and "model" turns, and they must
alternate, starting with a user turn and ending with one. `to_alternating`
turns any message list into that shape.
"""
from typing import List, Sequence

from backend.llm.base import ASSISTANT, SYSTEM, USER, Message

SYSTEM_SEPARATOR = "\n\n"


def to_alternating(messages: Sequence[Message]) -> List[Message]:
    """
    Make `messages` a strictly alternating user / assistant conversation

    * system messages become a prefix of the first user turn
    * consecutive messages with the same role are merged (blank line between)
    * assistant turns before the first user turn are dropped
    * the conversation ends with a user turn (a trailing assistant turn is dropped)

    The input is not modified.
    """
    system_text = SYSTEM_SEPARATOR.join(m.content for m in messages if m.role == SYSTEM and m.content)
    turns: List[Message] = []
    for message in messages:
        if message.role == SYSTEM:
            continue
        role = ASSISTANT if message.role == ASSISTANT else USER
        if not turns and role == ASSISTANT:
            continue                      # must start with a user turn
        if turns and turns[-1].role == role:
            turns[-1] = Message(role, turns[-1].content + SYSTEM_SEPARATOR + message.content)
        else:
            turns.append(Message(role, message.content))
    while turns and turns[-1].role == ASSISTANT:
        turns.pop()                       # must end with a user turn

    if system_text:
        if turns:
            turns[0] = Message(USER, system_text + SYSTEM_SEPARATOR + turns[0].content)
        else:
            turns = [Message(USER, system_text)]
    return turns
