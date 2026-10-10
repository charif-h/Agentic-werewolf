"""A scripted LLM for tests and offline runs"""
import json
import re
import threading
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from backend.llm.base import Message

Responder = Callable[[Sequence[Message]], str]


def fit_to_schema(text: str, json_schema: Dict[str, Any]) -> str:
    """
    Turn a plain-text answer into JSON that matches `json_schema`

    Real models answer in JSON when a schema is given; scripted tests would
    rather write "Bob". Answers that already are valid JSON are left alone.
    Understands the schemas of `backend.llm.schemas`: target, discussion, witch.
    """
    try:
        if isinstance(json.loads(text), dict):
            return text
    except ValueError:
        pass
    properties = json_schema.get("properties", {})
    reply = text.strip()
    if "target" in properties:
        return json.dumps({"target": reply.strip("\"'`.,;:!* ")})
    if "speak" in properties:
        silent = not reply or reply.lower().strip(". ") == "no comment"
        return json.dumps({"speak": not silent, "message": "" if silent else reply})
    if "save" in properties:
        save = re.search(r"\b(save|heal)\b", reply, re.IGNORECASE) is not None
        poison = "none"
        found = re.search(r"\bpoison\b\s*(\w+)", reply, re.IGNORECASE)
        if found:
            for name in properties["poison"].get("enum", []):
                if name.lower() == found.group(1).lower():
                    poison = name
        return json.dumps({"save": save, "poison": poison})
    return text


class FakeLLMClient:
    """
    Answers without any model.

    `responses` is a fixed string, a list of strings (used in turn, the last
    one repeats), a callable `f(messages) -> str`, or an Exception to raise.
    Every call is recorded in `calls` as `(messages, options)`.

    When the caller asks for JSON (`json_schema`), plain-text answers are
    wrapped to fit the schema (see `fit_to_schema`); pass `wrap_json=False` to
    get the raw string, e.g. to test how malformed answers are handled.
    """

    def __init__(self, responses: Union[str, List[str], Responder, Exception] = "no comment",
                 wrap_json: bool = True):
        self.responses = responses
        self.wrap_json = wrap_json
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
            answer = responses(messages)
        elif isinstance(responses, list):
            answer = responses[min(index, len(responses) - 1)]
        else:
            answer = responses
        if json_schema is not None and self.wrap_json:
            return fit_to_schema(answer, json_schema)
        return answer

    @property
    def last_messages(self) -> List[Message]:
        return self.calls[-1][0]
