"""A scripted LLM for tests and offline runs"""
import threading
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from backend.llm.base import Message

Responder = Callable[[Sequence[Message]], str]


class FakeLLMClient:
    """
    Answers without any model.

    `responses` is a fixed string, a list of strings (used in turn, the last
    one repeats), a callable `f(messages) -> str`, or an Exception to raise.
    Every call is recorded in `calls` as `(messages, options)`.
    """

    def __init__(self, responses: Union[str, List[str], Responder, Exception] = "no comment"):
        self.responses = responses
        self.calls: List[tuple] = []
        self._lock = threading.Lock()

    def generate(self, messages: Sequence[Message], *, max_tokens: Optional[int] = None,
                 temperature: Optional[float] = None,
                 json_schema: Optional[Dict[str, Any]] = None) -> str:
        options = {"max_tokens": max_tokens, "temperature": temperature,
                   "json_schema": json_schema}
        with self._lock:
            index = len(self.calls)
            self.calls.append((list(messages), options))
        responses = self.responses
        if isinstance(responses, Exception):
            raise responses
        if callable(responses):
            return responses(messages)
        if isinstance(responses, list):
            return responses[min(index, len(responses) - 1)]
        return responses

    @property
    def last_messages(self) -> List[Message]:
        return self.calls[-1][0]
