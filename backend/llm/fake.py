"""A scripted LLM for tests and offline runs"""
import json
import re
import threading
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from backend.llm.base import Message

Responder = Callable[[Sequence[Message]], str]


def fit_to_schema(text: str, json_schema: Dict[str, Any]) -> str:
    """
    Turn a plain-text answer into JSON that matches `json_schema`

    Real models answer in JSON when a schema is given; scripted tests would
    rather write "Bob". Answers that already are valid JSON are left alone.
    Understands the schemas of `backend.llm.schemas`: target, discussion, witch, diary, psytest (neutral answers).
    """
    try:
        if isinstance(json.loads(text), dict):
            return text
    except ValueError:
        pass
    properties = json_schema.get("properties", {})
    reply = text.strip()
    if "target" in properties:
        target = reply.strip("\"'`.,;:!* ")
        answer = {"reason": "My reason.", "target": target}
        if "not_chosen" in properties:
            others = [n for n in properties["target"].get("enum", []) if n.lower() != target.lower()]
            if others:
                answer["not_chosen"] = {"player": others[0], "why_not": "Less suspicious."}
        if "sacrifice_mate" in properties:
            answer["sacrifice_mate"] = False
        return json.dumps(answer if "reason" in properties else {"target": target})
    if "speak" in properties:
        silent = not reply or reply.lower().strip(". ") == "no comment"
        answer = {"speak": not silent, "message": "" if silent else reply}
        return json.dumps({"reason": "My reason.", **answer} if "reason" in properties else answer)
    if "opinions" in properties:
        item = properties["opinions"]["items"]["properties"]
        names = item["player"]["enum"]
        if "plan" in item:
            return json.dumps({"summary": reply or "Nothing clear yet.", "opinions": [
                {"player": name, "plan": "ignore", "reason": "Not dangerous for now."} for name in names]})
        return json.dumps({"summary": reply or "Nothing clear yet.", "opinions": [
            {"player": name, "guess": "unsure", "confidence": "low", "reason": "Not enough to go on."}
            for name in names]})
    if list(properties) == ["text"]:
        return json.dumps({"text": reply or "I take note of it."})
    if "answers" in properties:
        return json.dumps({"answers": [{"statement": "", "rating": 3}] * properties["answers"].get("minItems", 0)})
    if "save" in properties:
        save = re.search(r"\b(save|heal)\b", reply, re.IGNORECASE) is not None
        poison = "none"
        found = re.search(r"\bpoison\b\s*(\w+)", reply, re.IGNORECASE)
        if found:
            for name in properties["poison"].get("enum", []):
                if name.lower() == found.group(1).lower():
                    poison = name
        answer = {"save": save, "poison": poison}
        return json.dumps({"reason": "My reason.", **answer} if "reason" in properties else answer)
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


class ScriptedPlayers:
    """
    A scripted model for behaviour tests: what each named player answers to each kind of question.

        script = ScriptedPlayers()
        script.night("Wolf1", "Bob")                    # a wolf's proposal for the victim
        script.say("Ann", "As I said earlier, Bob lies.")   # a back-reference in the discussion
        script.mismatch("Cy", planned="Bob", voted="Dee")   # plans one player, votes another
        game = WerewolfGame(llm=FakeLLMClient(script))

    The answers of a player are used in turn and the last one repeats. An answer can be a plain
    string (wrapped to fit the schema by the fake client) or a dict, sent as JSON (for example
    `{"target": "Bob", "reason": "...", "sacrifice_mate": True}`). Anything not scripted gets `default`.
    """

    KINDS = ("say", "wolf_chat", "night", "plan", "vote", "reaction")

    def __init__(self, default: str = "no comment"):
        self.default = default
        self._answers: Dict[Tuple[str, str], List[Union[str, dict]]] = {}
        self._used: Dict[Tuple[str, str], int] = {}

    def _add(self, kind: str, name: str, answers: Sequence[Union[str, dict]]) -> "ScriptedPlayers":
        self._answers.setdefault((kind, name), []).extend(answers)
        return self

    def say(self, name: str, *lines: str) -> "ScriptedPlayers":
        """What `name` says in the discussion"""
        return self._add("say", name, lines)

    def backreference(self, name: str, line: str = "As I said earlier, someone here is lying.") -> "ScriptedPlayers":
        """`name` opens the discussion as if continuing an earlier talk"""
        return self.say(name, line)

    def wolf_chat(self, name: str, *lines: str) -> "ScriptedPlayers":
        """What the werewolf `name` tells the pack at night"""
        return self._add("wolf_chat", name, lines)

    def night(self, name: str, *targets: Union[str, dict]) -> "ScriptedPlayers":
        """The night target `name` proposes (a werewolf's proposal for the victim, the seer's choice...)"""
        return self._add("night", name, targets)

    def plan(self, name: str, *targets: Union[str, dict]) -> "ScriptedPlayers":
        """Whom `name` plans to vote against"""
        return self._add("plan", name, targets)

    def vote(self, name: str, *targets: Union[str, dict]) -> "ScriptedPlayers":
        """Whom `name` really votes for"""
        return self._add("vote", name, targets)

    def mismatch(self, name: str, planned: str, voted: str) -> "ScriptedPlayers":
        """`name` plans to vote `planned` but votes `voted`, even when asked again (no explanation)"""
        return self.plan(name, planned).vote(name, {"target": voted, "reason": ""})

    def reaction(self, name: str, *notes: str) -> "ScriptedPlayers":
        """The reaction note `name` writes in the diary"""
        return self._add("reaction", name, notes)

    @staticmethod
    def kind_of(prompt: str) -> str:
        """The kind of question in the last message of a conversation"""
        if "Pack talk so far" in prompt:
            return "wolf_chat"
        if "The vote is about to begin" in prompt:
            return "plan"
        if "voting to eliminate someone" in prompt:
            return "vote"
        if "in the village discussion" in prompt:
            return "say"
        if "quick note in your private diary" in prompt:
            return "reaction"
        if "private diary" in prompt:
            return "diary"
        if "Phase: night" in prompt:
            return "night"
        return "other"

    @staticmethod
    def player_of(messages: Sequence[Message]) -> str:
        """The name of the player asking, from the start of the system message ("You are Ann, ...")"""
        found = re.match(r"\s*You are ([^,.\n]+)", messages[0].content if messages else "")
        return found.group(1).strip() if found else ""

    def __call__(self, messages: Sequence[Message]) -> str:
        kind = self.kind_of(messages[-1].content)
        key = (kind, self.player_of(messages))
        answers = self._answers.get(key)
        if not answers:
            return self.default
        index = self._used.get(key, 0)
        self._used[key] = index + 1
        answer = answers[min(index, len(answers) - 1)]
        return answer if isinstance(answer, str) else json.dumps(answer)
