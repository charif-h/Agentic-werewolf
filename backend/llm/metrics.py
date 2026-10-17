"""Counters for model calls: totals for the server and per game"""
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, Optional


class LLMMetrics:
    """Thread-safe counters of calls, tokens and time"""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._data = {"calls": 0, "errors": 0, "prompt_tokens": 0, "completion_tokens": 0,
                          "seconds": 0.0, "generation_seconds": 0.0, "load_seconds": 0.0,
                          "wait_seconds": 0.0, "skipped_turns": 0,
                          "invalid_answers": 0, "role_leaks": 0, "repeated_lines": 0, "opening_backreference": 0, "missing_reasons": 0, "reaction_entries": 0, "vote_plans": 0, "diary_vote_mismatch": 0, "unexplained_changes": 0, "wolf_voted_mate_unintended": 0, "wolf_sacrificed_mate": 0,
                          "psytests": 0, "psytest_flagged": 0}

    def add_call(self, seconds: float, wait_seconds: float = 0.0,
                 answer: Optional[Dict[str, Any]] = None) -> None:
        """
        Count one model call

        Args:
            seconds: Total time of the call, waiting for a free slot included
            wait_seconds: Time spent waiting for a free slot
            answer: The JSON answer of Ollama, or None if the call failed
        """
        with self._lock:
            self._data["calls"] += 1
            self._data["seconds"] += seconds
            self._data["wait_seconds"] += wait_seconds
            if answer is None:
                self._data["errors"] += 1
                return
            self._data["prompt_tokens"] += answer.get("prompt_eval_count") or 0
            self._data["completion_tokens"] += answer.get("eval_count") or 0
            self._data["generation_seconds"] += (answer.get("eval_duration") or 0) / 1e9
            self._data["load_seconds"] += (answer.get("load_duration") or 0) / 1e9

    def add_skipped_turn(self) -> None:
        """Count a player turn that did not need a model call"""
        with self._lock:
            self._data["skipped_turns"] += 1

    def add_invalid_answer(self) -> None:
        """Count an answer that could not be used (not valid JSON, name not allowed, model down)"""
        with self._lock:
            self._data["invalid_answers"] += 1

    def add_repeated_line(self) -> None:
        """Count a discussion line dropped because it only repeated what was just said"""
        with self._lock:
            self._data["repeated_lines"] += 1

    def add_wolf_voted_mate_unintended(self) -> None:
        """Count a werewolf vote on a mate without the deliberate sacrifice (caught by the guard)"""
        with self._lock:
            self._data["wolf_voted_mate_unintended"] += 1

    def add_wolf_sacrificed_mate(self) -> None:
        """Count a werewolf vote on a mate that was meant as a sacrifice"""
        with self._lock:
            self._data["wolf_sacrificed_mate"] += 1

    def add_vote_plan(self) -> None:
        """Count a plan written before a vote"""
        with self._lock:
            self._data["vote_plans"] += 1

    def add_diary_vote_mismatch(self) -> None:
        """Count a vote that first differed from the player's plan"""
        with self._lock:
            self._data["diary_vote_mismatch"] += 1

    def add_unexplained_change(self) -> None:
        """Count a vote that still differed from the plan after asking again, without an explanation"""
        with self._lock:
            self._data["unexplained_changes"] += 1

    def add_reaction_entry(self) -> None:
        """Count a reaction note written in a diary during the discussion (one model call)"""
        with self._lock:
            self._data["reaction_entries"] += 1

    def add_missing_reason(self) -> None:
        """Count a decision that came without a reason, even after asking again"""
        with self._lock:
            self._data["missing_reasons"] += 1

    def add_opening_backreference(self) -> None:
        """Count an opening line that referred to an earlier exchange although nobody had spoken"""
        with self._lock:
            self._data["opening_backreference"] += 1

    def add_psytest(self, flagged: bool) -> None:
        """Count a completed psychological test, and whether the player was flagged"""
        with self._lock:
            self._data["psytests"] += 1
            self._data["psytest_flagged"] += 1 if flagged else 0

    def add_role_leak(self) -> None:
        """Count a discussion line in which the speaker stated their own role"""
        with self._lock:
            self._data["role_leaks"] += 1

    def snapshot(self) -> Dict[str, Any]:
        """A copy of the counters, rounded, with tokens per second added"""
        with self._lock:
            data = dict(self._data)
        generation = data["generation_seconds"]
        data["tokens_per_second"] = data["completion_tokens"] / generation if generation else 0.0
        return {key: round(value, 2) if isinstance(value, float) else value
                for key, value in data.items()}


_current: ContextVar[Optional[LLMMetrics]] = ContextVar("llm_metrics", default=None)


def current_metrics() -> Optional[LLMMetrics]:
    """The per-game counters active in this context, if any"""
    return _current.get()


@contextmanager
def track(metrics: LLMMetrics) -> Iterator[LLMMetrics]:
    """
    Count the model calls made inside the `with` block (in this thread or in
    tasks started from it) in `metrics`, in addition to the client's totals
    """
    token = _current.set(metrics)
    try:
        yield metrics
    finally:
        _current.reset(token)
