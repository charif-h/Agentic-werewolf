"""Single-GPU concurrency, warm-up, per-game metrics and the talkativeness gate."""
import asyncio
import contextvars
import random
import threading
import time
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.api import state
from backend.config import Settings
from backend.game import talkativeness
from backend.game.game_logic import WerewolfGame
from backend.llm import FakeLLMClient, LLMError, Message
from backend.llm.metrics import LLMMetrics, current_metrics, track
from backend.llm.ollama_client import OllamaClient
from backend.models.game_models import PersonalityType, PlayerProfile, Sex
from backend.services.phases import advance_phase
from backend.services.sessions import SessionManager

HELLO = [Message("user", "hi")]
ANSWER = {"message": {"role": "assistant", "content": "ok"}, "prompt_eval_count": 20,
          "eval_count": 5, "eval_duration": 100_000_000}


def make_client(handler, **options):
    return OllamaClient("http://ollama.test", "gemma3:4b", transport=httpx.MockTransport(handler), **options)


# --- one request at a time (or as many as configured) ----------------------------------------

def run_threads(client, count):
    threads = [threading.Thread(target=client.generate, args=(HELLO,)) for _ in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)


@pytest.mark.parametrize("max_parallel", [1, 2, 3])
def test_requests_never_exceed_max_parallel(max_parallel):
    lock = threading.Lock()
    state_ = {"now": 0, "peak": 0}

    def handler(request):
        with lock:
            state_["now"] += 1
            state_["peak"] = max(state_["peak"], state_["now"])
        time.sleep(0.03)
        with lock:
            state_["now"] -= 1
        return httpx.Response(200, json=ANSWER)

    client = make_client(handler, max_parallel=max_parallel)
    run_threads(client, 8)
    assert client.metrics()["calls"] == 8
    assert state_["peak"] == max_parallel


def test_queued_calls_report_their_waiting_time():
    def handler(request):
        time.sleep(0.05)
        return httpx.Response(200, json=ANSWER)

    client = make_client(handler, max_parallel=1)
    run_threads(client, 4)
    metrics = client.metrics()
    assert metrics["wait_seconds"] > 0.1          # three of the four calls had to wait
    assert metrics["seconds"] >= metrics["wait_seconds"]


def test_a_failing_call_frees_its_slot():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500, text="boom") if calls["n"] == 1 else httpx.Response(200, json=ANSWER)

    client = make_client(handler, max_parallel=1)
    with pytest.raises(LLMError):
        client.generate(HELLO)
    assert client.generate(HELLO) == "ok"
    assert client.metrics()["errors"] == 1


def test_max_parallel_is_at_least_one():
    assert make_client(lambda r: httpx.Response(200, json=ANSWER), max_parallel=0).max_parallel == 1


# --- warm-up -----------------------------------------------------------------------------------

def test_warm_up_loads_the_model_with_keep_alive():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = request.content
        return httpx.Response(200, json={"done": True})

    seconds = make_client(handler, keep_alive="45m").warm_up()
    assert seconds >= 0 and seen["path"] == "/api/generate"
    assert b'"keep_alive":"45m"' in seen["body"].replace(b" ", b"")
    assert b"messages" not in seen["body"]


def test_warm_up_errors():
    with pytest.raises(LLMError, match="ollama pull"):
        make_client(lambda r: httpx.Response(404, json={})).warm_up()
    with pytest.raises(LLMError, match="HTTP 500"):
        make_client(lambda r: httpx.Response(500)).warm_up()

    def down(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMError, match="warm up"):
        make_client(down).warm_up()


class WarmClient(FakeLLMClient):
    def __init__(self, ready=True):
        super().__init__("x")
        self.ready = ready
        self.warmed = threading.Event()

    def status(self):
        return {"model": "m", "host": "h", "reachable": self.ready, "installed": self.ready,
                "size_bytes": 1}

    def warm_up(self):
        self.warmed.set()
        return 0.1


def start_server(client, monkeypatch, warmup=True):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, llm_warmup=warmup))
    with patch("backend.main.create_llm_client", return_value=client):
        with TestClient(main.app):
            client.warmed.wait(1)


def test_the_server_warms_the_model_up_at_startup(monkeypatch):
    client = WarmClient()
    start_server(client, monkeypatch)
    assert client.warmed.is_set()


def test_no_warm_up_when_disabled_or_when_the_model_is_not_ready(monkeypatch):
    disabled = WarmClient()
    start_server(disabled, monkeypatch, warmup=False)
    assert not disabled.warmed.is_set()
    not_ready = WarmClient(ready=False)
    start_server(not_ready, monkeypatch)
    assert not not_ready.warmed.is_set()


# --- per-game metrics ---------------------------------------------------------------------------------

def test_calls_are_counted_for_the_game_that_made_them():
    client = make_client(lambda r: httpx.Response(200, json=ANSWER))
    game_a, game_b = LLMMetrics(), LLMMetrics()
    with track(game_a):
        client.generate(HELLO)
        client.generate(HELLO)
    with track(game_b):
        client.generate(HELLO)
    client.generate(HELLO)                        # outside any game: only the totals
    assert (game_a.snapshot()["calls"], game_b.snapshot()["calls"]) == (2, 1)
    assert client.metrics()["calls"] == 4
    assert game_a.snapshot()["completion_tokens"] == 10
    assert current_metrics() is None


def test_tracking_follows_worker_threads_started_with_the_context():
    client = make_client(lambda r: httpx.Response(200, json=ANSWER))
    game = LLMMetrics()

    async def run():
        with track(game):
            await asyncio.to_thread(client.generate, HELLO)

    asyncio.run(run())
    assert game.snapshot()["calls"] == 1
    outside = contextvars.copy_context()
    outside.run(client.generate, HELLO)
    assert game.snapshot()["calls"] == 1


def test_snapshot_has_tokens_per_second_and_rounds():
    metrics = LLMMetrics()
    metrics.add_call(1.23456, 0.0, ANSWER)
    metrics.add_skipped_turn()
    snapshot = metrics.snapshot()
    assert snapshot["tokens_per_second"] == pytest.approx(50.0)
    assert snapshot["seconds"] == 1.23 and snapshot["skipped_turns"] == 1
    metrics.reset()
    assert metrics.snapshot()["calls"] == 0


def test_advance_phase_tracks_the_game_metrics():
    game = WerewolfGame(num_players=6, llm=FakeLLMClient("Bob looks odd."))
    game.setup_game()
    game.start_night()
    seen = []
    game.process_night_actions = lambda: seen.append(current_metrics()) or {}
    advance_phase(game)
    assert seen == [game.metrics]


def test_game_state_reports_llm_metrics():
    with patch("backend.api.games.create_llm_client", return_value=FakeLLMClient("Bob")):
        with TestClient(main.app) as client:
            state_sessions = SessionManager()
            with patch.object(state, "sessions", state_sessions):
                game_id = client.post("/api/games", json={"num_players": 6}).json()["game_id"]
                llm = client.get(f"/api/games/{game_id}").json()["llm"]
    assert llm["calls"] == 0 and llm["skipped_turns"] == 0 and "tokens_per_second" in llm


# --- talkativeness gate -----------------------------------------------------------------------------------

def player(name, personality):
    return PlayerProfile(id=name, name=name, sex=Sex.MALE, age=30, personality=personality)


def test_a_player_who_was_just_addressed_always_speaks():
    assert talkativeness.is_addressed("Ann", "[Bob] hi\n[Cy] Ann, what do you think?")
    assert not talkativeness.is_addressed("Ann", "[Bob] Joanna is odd")          # whole words only
    assert not talkativeness.is_addressed("Ann", "[Bob] Ann?\n[Cy] a\n[Dee] b\n[Eli] c")   # too old
    ann = player("Ann", PersonalityType.INTP)
    assert talkativeness.speak_probability(ann, "[Cy] Ann, what do you think?", True) == 1.0


def test_extraverts_talk_more_than_introverts_and_repeat_less():
    extravert, introvert = player("Eve", PersonalityType.ENFP), player("Ivy", PersonalityType.INTJ)
    assert talkativeness.speak_probability(extravert, "", False) > talkativeness.speak_probability(introvert, "", False)
    assert (talkativeness.speak_probability(extravert, "", True)
            < talkativeness.speak_probability(extravert, "", False))


def test_should_speak_follows_the_probability():
    extravert = player("Eve", PersonalityType.ENFP)
    rng = random.Random(1)
    spoke = sum(talkativeness.should_speak(extravert, "", False, rng) for _ in range(2000))
    assert 0.80 < spoke / 2000 < 0.90
    assert talkativeness.should_speak(extravert, "Eve?", False, random.Random(1))


def count_calls(gate, seed):
    random.seed(seed)
    llm = FakeLLMClient(lambda m: "Bob looks odd.")
    game = WerewolfGame(num_players=10, llm=llm)
    game.setup_game()
    settings = Settings(_env_file=None, discussion_gate=gate)
    with patch("backend.game.game_logic.get_settings", return_value=settings):
        game.conduct_discussion()
    return len(llm.calls), game.metrics.snapshot()["skipped_turns"]


def test_the_gate_saves_model_calls():
    with_gate = [count_calls(True, seed) for seed in range(8)]
    without_gate = [count_calls(False, seed) for seed in range(8)]
    assert sum(c for c, _ in with_gate) < 0.9 * sum(c for c, _ in without_gate)
    assert all(skipped == 0 for _, skipped in without_gate)
    assert all(skipped > 0 for _, skipped in with_gate)


def test_the_first_turn_of_the_day_is_never_skipped():
    llm = FakeLLMClient("Bob looks odd.")
    game = WerewolfGame(num_players=6, llm=llm)
    game.setup_game()
    with patch("backend.game.game_logic.should_speak", return_value=False):
        messages = game.conduct_discussion()
    assert len(messages) == 1 and len(llm.calls) == 1        # the opener spoke, then silence ended it
