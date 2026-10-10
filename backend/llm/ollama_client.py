"""LLMClient for a local model served by Ollama (https://ollama.com)"""
import logging
import threading
import time
from typing import Any, Dict, Optional, Sequence

import httpx

from backend.llm.base import LLMError, Message
from backend.llm.formatting import to_alternating

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Talks to the Ollama HTTP API (`/api/chat`, non-streaming).

    One instance can be shared by many threads: `httpx.Client` is thread-safe
    and the server decides how many requests run in parallel.
    """

    def __init__(self, host: str = "http://localhost:11434", model: str = "gemma3:4b", *,
                 temperature: float = 0.8, max_tokens: Optional[int] = 256, num_ctx: int = 4096,
                 keep_alive: str = "30m", timeout: float = 120.0,
                 transport: Optional[httpx.BaseTransport] = None):
        """
        Args:
            host: Base URL of the Ollama server
            model: Model tag, e.g. "gemma3:4b"
            temperature: Default sampling temperature
            max_tokens: Default answer length limit (None = model default)
            num_ctx: Context window in tokens (smaller = less VRAM)
            keep_alive: How long Ollama keeps the model loaded after a call
            timeout: Seconds to wait for one answer
            transport: Custom httpx transport (used by tests)
        """
        self.host = host.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self._http = httpx.Client(base_url=self.host, timeout=timeout, transport=transport)
        self._metrics_lock = threading.Lock()
        self.reset_metrics()

    def reset_metrics(self) -> None:
        """Start counting calls, tokens and time from zero"""
        with self._metrics_lock:
            self._metrics = {"calls": 0, "errors": 0, "prompt_tokens": 0,
                             "completion_tokens": 0, "seconds": 0.0, "generation_seconds": 0.0,
                             "load_seconds": 0.0}

    def metrics(self) -> Dict[str, Any]:
        """Calls, tokens and time since the last reset (thread-safe snapshot)"""
        with self._metrics_lock:
            data = dict(self._metrics)
        seconds = data["generation_seconds"]
        data["tokens_per_second"] = data["completion_tokens"] / seconds if seconds else 0.0
        return data

    def _record(self, started: float, answer: Optional[Dict[str, Any]]) -> None:
        with self._metrics_lock:
            self._metrics["calls"] += 1
            self._metrics["seconds"] += time.monotonic() - started
            if answer is None:
                self._metrics["errors"] += 1
                return
            self._metrics["prompt_tokens"] += answer.get("prompt_eval_count") or 0
            self._metrics["completion_tokens"] += answer.get("eval_count") or 0
            self._metrics["generation_seconds"] += (answer.get("eval_duration") or 0) / 1e9
            self._metrics["load_seconds"] += (answer.get("load_duration") or 0) / 1e9

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
        try:
            return self._chat(payload, started)
        except LLMError:
            self._record(started, None)
            raise

    def _chat(self, payload: Dict[str, Any], started: float) -> str:
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
            text = answer["message"]["content"]
        except (ValueError, KeyError, TypeError) as e:
            raise LLMError("Unexpected answer from Ollama") from e
        self._record(started, answer)
        return text

    def status(self) -> Dict[str, Any]:
        """
        Is the server up and is the model installed?

        Returns:
            {"model", "host", "reachable", "installed", "size_bytes"}
        """
        info = {"model": self.model, "host": self.host, "reachable": False,
                "installed": False, "size_bytes": None}
        try:
            response = self._http.get("/api/tags", timeout=5)
            response.raise_for_status()
            info["reachable"] = True
            for installed in response.json().get("models", []):
                if installed.get("name") == self.model or installed.get("model") == self.model:
                    info["installed"] = True
                    info["size_bytes"] = installed.get("size")
        except (httpx.HTTPError, ValueError):
            pass
        return info

    def close(self) -> None:
        self._http.close()
