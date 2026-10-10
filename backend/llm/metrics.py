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
                          "wait_seconds": 0.0, "skipped_turns": 0}

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
