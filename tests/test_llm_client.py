"""The LLMClient interface, the fake client and the Ollama client."""
import json
from unittest.mock import patch

import httpx
import pytest

from backend.agents.player_agent import PlayerAgent
from backend.game.game_logic import WerewolfGame
from backend.llm import ASSISTANT, SYSTEM, USER, FakeLLMClient, LLMClient, LLMError, Message
from backend.llm.ollama_client import OllamaClient
from backend.models.game_models import PersonalityType, PlayerProfile, Role, Sex

HELLO = [Message(SYSTEM, "be brief"), Message(USER, "hi")]


def test_fake_client_satisfies_the_protocol():
    assert isinstance(FakeLLMClient(), LLMClient)


def test_messages_are_immutable_value_objects():
    assert Message(USER, "x") == Message("user", "x")
    with pytest.raises(Exception):
        Message(USER, "x").content = "y"


def test_fake_client_fixed_list_and_callable_responses():
    assert FakeLLMClient("a").generate(HELLO) == "a"
    sequence = FakeLLMClient(["one", "two"])
    assert [sequence.generate(HELLO) for _ in range(3)] == ["one", "two", "two"]
    echo = FakeLLMClient(lambda messages: messages[-1].content.upper())
    assert echo.generate(HELLO) == "HI"


def test_fake_client_can_fail_and_records_calls():
    failing = FakeLLMClient(RuntimeError("down"))
    with pytest.raises(RuntimeError):
        failing.generate(HELLO, temperature=0.2, max_tokens=5)
    messages, options = failing.calls[0]
    assert messages == HELLO
    assert options == {"max_tokens": 5, "temperature": 0.2, "json_schema": None}
    assert failing.last_messages == HELLO


def make_ollama(handler, **options):
    return OllamaClient("http://ollama.test:11434/", "gemma3:4b",
                        transport=httpx.MockTransport(handler), **options)


def ok(content="hello"):
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


def test_ollama_sends_a_chat_request_and_returns_the_text():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return ok("salut")

    client = make_ollama(handler, temperature=0.5, max_tokens=64, num_ctx=2048, keep_alive="10m")
    assert client.generate(HELLO + [Message(ASSISTANT, "ok"), Message(USER, "more")]) == "salut"
    assert seen["url"] == "http://ollama.test:11434/api/chat"
    body = seen["body"]
    assert body["model"] == "gemma3:4b" and body["stream"] is False and body["keep_alive"] == "10m"
    assert body["messages"] == [
        {"role": "system", "content": "be brief"}, {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "ok"}, {"role": "user", "content": "more"},
    ]
    assert body["options"] == {"temperature": 0.5, "num_ctx": 2048, "num_predict": 64}
    assert "format" not in body


def test_ollama_per_call_options_override_the_defaults():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return ok("{}")

    schema = {"type": "object", "properties": {"target": {"type": "string"}}}
    make_ollama(handler).generate(HELLO, max_tokens=10, temperature=0.0, json_schema=schema)
    assert seen["body"]["options"]["num_predict"] == 10
    assert seen["body"]["options"]["temperature"] == 0.0
    assert seen["body"]["format"] == schema


def test_ollama_without_a_token_limit_leaves_it_to_the_model():
    seen = {}

    def handler(request):
        seen["options"] = json.loads(request.content)["options"]
        return ok()

    make_ollama(handler, max_tokens=None).generate(HELLO)
    assert "num_predict" not in seen["options"]


def test_ollama_errors_become_llm_errors_with_helpful_text():
    def down(request):
        raise httpx.ConnectError("refused")

    def slow(request):
        raise httpx.ReadTimeout("too slow")

    with pytest.raises(LLMError, match="Is it running"):
        make_ollama(down).generate(HELLO)
    with pytest.raises(LLMError, match="in time"):
        make_ollama(slow).generate(HELLO)
    with pytest.raises(LLMError, match="ollama pull gemma3:4b"):
        make_ollama(lambda r: httpx.Response(404, json={"error": "model not found"})).generate(HELLO)
    with pytest.raises(LLMError, match="HTTP 500"):
        make_ollama(lambda r: httpx.Response(500, text="boom")).generate(HELLO)
    with pytest.raises(LLMError, match="Unexpected"):
        make_ollama(lambda r: httpx.Response(200, json={"nope": 1})).generate(HELLO)
    with pytest.raises(LLMError, match="Unexpected"):
        make_ollama(lambda r: httpx.Response(200, text="not json")).generate(HELLO)


def test_ollama_status():
    tags = {"models": [{"name": "gemma3:1b", "size": 5}, {"name": "gemma3:4b", "model": "gemma3:4b", "size": 3_300_000_000}]}
    status = make_ollama(lambda r: httpx.Response(200, json=tags)).status()
    assert status == {"model": "gemma3:4b", "host": "http://ollama.test:11434", "reachable": True,
                      "installed": True, "size_bytes": 3_300_000_000}
    missing = make_ollama(lambda r: httpx.Response(200, json={"models": []})).status()
    assert missing["reachable"] and not missing["installed"]

    def down(request):
        raise httpx.ConnectError("refused")

    unreachable = make_ollama(down).status()
    assert not unreachable["reachable"] and not unreachable["installed"]


def test_ollama_client_satisfies_the_protocol():
    assert isinstance(make_ollama(lambda r: ok()), LLMClient)


def test_all_players_share_one_client():
    llm = FakeLLMClient("x")
    game = WerewolfGame(num_players=8, llm=llm)
    game.setup_game()
    assert game.llm is llm
    assert all(agent.llm is llm for agent in game.player_agents.values())


def test_game_creates_the_client_once_when_none_is_given():
    with patch("backend.game.game_logic.create_llm_client", return_value=FakeLLMClient("x")) as factory:
        game = WerewolfGame(num_players=8)
        game.setup_game()
    factory.assert_called_once_with()
    assert len({id(agent.llm) for agent in game.player_agents.values()}) == 1


def test_agent_memory_holds_messages_and_is_replayed():
    profile = PlayerProfile(id="p", name="Ann", sex=Sex.FEMALE, age=30,
                            personality=PersonalityType.INTJ, role=Role.SEER)
    llm = FakeLLMClient("Bob")
    agent = PlayerAgent(profile, llm)
    state = {'phase': 'night', 'day_number': 1, 'players': [], 'valid_targets': ['Bob']}
    agent.night_action(state)
    assert [m.role for m in agent.memory] == [USER, ASSISTANT]
    assert agent.memory[1].content == "Bob"
    agent.night_action(state)
    roles = [m.role for m in llm.last_messages]
    assert roles == [SYSTEM, USER, ASSISTANT, USER]
