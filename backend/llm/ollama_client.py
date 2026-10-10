"""LLMClient for a local model served by Ollama (https://ollama.com)"""
import logging
import threading
import time
from typing import Any, Dict, Optional, Sequence

import httpx

from backend.llm.base import LLMError, Message
from backend.llm.formatting import to_alternating
from backend.llm.metrics import LLMMetrics, current_metrics

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Talks to the Ollama HTTP API (`/api/chat`, non-streaming).

    One instance is shared by every game and thread. A single GPU runs one
    request at a time, so calls queue up for one of `max_parallel` slots
    (raise it together with Ollama's OLLAMA_NUM_PARALLEL if your hardware
    can serve several requests at once).
    """

    def __init__(self, host: str = "http://localhost:11434", model: str = "gemma3:4b", *,
                 temperature: float = 0.8, max_tokens: Optional[int] = 256, num_ctx: int = 4096,
                 keep_alive: str = "30m", timeout: float = 120.0, max_parallel: int = 1,
                 transport: Optional[httpx.BaseTransport] = None):
        """
        Args:
            host: Base URL of the Ollama server
            model: Model tag, e.g. "gemma3:4b"
            temperature: Default sampling temperature
            max_tokens: Default answer length limit (None = model default)
            num_ctx: Context window in tokens (smaller = less VRAM)
            keep_alive: How long Ollama keeps the model loaded after a call
            timeout: Seconds to wait for one answer (after getting a slot)
            max_parallel: How many requests may be in flight at the same time
            transport: Custom httpx transport (used by tests)
        """
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.max_parallel = max(1, max_parallel)
        self._slots = threading.BoundedSemaphore(self.max_parallel)
        self._http = httpx.Client(base_url=self.host, timeout=timeout, transport=transport)
        self._totals = LLMMetrics()

    def reset_metrics(self) -> None:
        """Start counting calls, tokens and time from zero"""
        self._totals.reset()

    def metrics(self) -> Dict[str, Any]:
        """Calls, tokens and time since the last reset (thread-safe snapshot)"""
        return self._totals.snapshot()

    def _record(self, started: float, waited: float, answer: Optional[Dict[str, Any]]) -> None:
        seconds = time.monotonic() - started
        self._totals.add_call(seconds, waited, answer)
        game_metrics = current_metrics()      # the game that asked, if it is tracking
        if game_metrics is not None:
            game_metrics.add_call(seconds, waited, answer)

    def generate(self, messages: Sequence[Message], *, max_tokens: Optional[int] = None,
                 temperature: Optional[float] = None,
                 json_schema: Optional[Dict[str, Any]] = None) -> str:
        options: Dict[str, Any] = {
            "temperature": self.temperature if temperature is None else temperature,
            "num_ctx": self.num_ctx,
        }
        limit = max_tokens if max_tokens is not None else self.max_tokens
        if limit is not None:
            options["num_predict"] = limit
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in to_alternating(messages)],
            "stream": False,
            "options": options,
            "keep_alive": self.keep_alive,
            # Thinking models (Gemma 4) would spend the whole token budget "thinking" and
            # return an empty answer; the game needs short direct replies
            "think": False,
        }
        if json_schema is not None:
            payload["format"] = json_schema

        started = time.monotonic()
        with self._slots:                       # queue here when the model is busy
            waited = time.monotonic() - started
            try:
                answer = self._chat(payload)
            except LLMError:
                self._record(started, waited, None)
                raise
        self._record(started, waited, answer)
        return answer["message"]["content"]

    def _chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """One request to /api/chat; returns the decoded answer"""
        try:
            response = self._http.post("/api/chat", json=payload)
        except httpx.ConnectError as e:
            raise LLMError(f"Cannot reach Ollama at {self.host}. Is it running? ({e})") from e
        except httpx.TimeoutException as e:
            raise LLMError(f"Ollama did not answer in time ({e})") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama request failed: {e}") from e

        if response.status_code == 404:
            raise LLMError(f"Model '{self.model}' is not installed. Run: ollama pull {self.model}")
        if response.status_code != 200:
            raise LLMError(f"Ollama returned HTTP {response.status_code}: {response.text[:200]}")
        try:
            answer = response.json()
            answer["message"]["content"]
        except (ValueError, KeyError, TypeError) as e:
            raise LLMError("Unexpected answer from Ollama") from e
        return answer

    def warm_up(self) -> float:
        """
        Load the model into memory now, so that the first game does not wait for it

        Returns:
            Seconds it took

        Raises:
            LLMError: if Ollama cannot be reached or the model is missing
        """
        started = time.monotonic()
        try:
            response = self._http.post("/api/generate", json={
                "model": self.model, "keep_alive": self.keep_alive,
                "options": {"num_ctx": self.num_ctx},
            }, timeout=300)
        except httpx.HTTPError as e:
            raise LLMError(f"Could not warm up the model: {e}") from e
        if response.status_code == 404:
            raise LLMError(f"Model '{self.model}' is not installed. Run: ollama pull {self.model}")
        if response.status_code != 200:
            raise LLMError(f"Could not warm up the model (HTTP {response.status_code})")
        return time.monotonic() - started

    def status(self) -> Dict[str, Any]:
        """
        Is the server up and is the model installed?

        Returns:
            {"model", "host", "reachable", "installed", "size_bytes", "loaded", "vram_bytes"}
            where `loaded` says whether the model is in memory right now (the first
            answer of an unloaded model takes much longer)
        """
        info = {"model": self.model, "host": self.host, "reachable": False,
                "installed": False, "size_bytes": None, "loaded": False, "vram_bytes": None}
        try:
            response = self._http.get("/api/tags", timeout=5)
            response.raise_for_status()
            info["reachable"] = True
            for installed in response.json().get("models", []):
                if installed.get("name") == self.model or installed.get("model") == self.model:
                    info["installed"] = True
                    info["size_bytes"] = installed.get("size")
            if info["installed"]:
                running = self._http.get("/api/ps", timeout=5)
                running.raise_for_status()
                for loaded in running.json().get("models", []):
                    if loaded.get("name") == self.model or loaded.get("model") == self.model:
                        info["loaded"] = True
                        info["vram_bytes"] = loaded.get("size_vram")
        except (httpx.HTTPError, ValueError):
            pass
        return info

    def close(self) -> None:
        self._http.close()
