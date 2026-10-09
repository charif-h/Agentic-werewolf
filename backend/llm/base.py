"""The interface every language-model backend implements"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol, Sequence, runtime_checkable

SYSTEM = "system"
USER = "user"
ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    """One chat message; `role` is "system", "user" or "assistant" """
    role: str
    content: str


class LLMError(Exception):
    """The model could not produce an answer (server down, bad output, ...)"""


@runtime_checkable
class LLMClient(Protocol):
    """
    A chat model.

    `generate` is synchronous and may take seconds; call it from a worker
    thread inside async code. It must be safe to call from several threads.
    """

    def generate(self, messages: Sequence[Message], *, max_tokens: Optional[int] = None,
                 temperature: Optional[float] = None,
                 json_schema: Optional[Dict[str, Any]] = None) -> str:
        """
        Args:
            messages: The conversation so far; the last one is from the user
            max_tokens: Upper bound on the length of the answer
            temperature: Sampling temperature (None = the client's default)
            json_schema: If given, the answer must be JSON matching this schema

        Returns:
            The text of the answer
        """
        ...
