"""The LLMClient interface, the fake client and the LangChain adapter."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.player_agent import PlayerAgent
from backend.game.game_logic import WerewolfGame
from backend.llm import ASSISTANT, SYSTEM, USER, FakeLLMClient, LLMClient, LLMError, Message
from backend.llm.factory import create_llm_client
from backend.llm.langchain_client import LangChainClient
from backend.models.game_models import PersonalityType, PlayerProfile, Role, Sex

HELLO = [Message(SYSTEM, "be brief"), Message(USER, "hi")]


def test_fake_client_satisfies_the_protocol():
    assert isinstance(FakeLLMClient(), LLMClient)
    assert isinstance(LangChainClient(MagicMock()), LLMClient)


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


def test_langchain_adapter_converts_messages_and_returns_text():
    chat = MagicMock()
    chat.invoke.return_value = SimpleNamespace(content="hello")
    answer = LangChainClient(chat).generate(HELLO + [Message(ASSISTANT, "ok"), Message(USER, "more")])
    assert answer == "hello"
    sent = chat.invoke.call_args[0][0]
    assert [type(m).__name__ for m in sent] == ["SystemMessage", "HumanMessage", "AIMessage", "HumanMessage"]
    assert [m.content for m in sent] == ["be brief", "hi", "ok", "more"]


def test_langchain_adapter_wraps_errors_keeping_the_text():
    chat = MagicMock()
    chat.invoke.side_effect = RuntimeError("429 rate limit exceeded")
    with pytest.raises(LLMError, match="rate limit"):
        LangChainClient(chat).generate(HELLO)


def test_factory_builds_a_langchain_client():
    with patch("backend.llm.factory.AIProvider.get_llm", return_value=MagicMock()) as get_llm:
        client = create_llm_client("mistral")
    get_llm.assert_called_once_with(provider="mistral")
    assert isinstance(client, LangChainClient)


def test_all_players_share_one_client():
    llm = FakeLLMClient("x")
    game = WerewolfGame(num_players=8, llm=llm)
    game.setup_game()
    assert game.llm is llm
    assert all(agent.llm is llm for agent in game.player_agents.values())


def test_game_creates_the_client_once_when_none_is_given():
    with patch("backend.game.game_logic.create_llm_client", return_value=FakeLLMClient("x")) as factory:
        game = WerewolfGame(num_players=8, ai_provider="gemini")
        game.setup_game()
    factory.assert_called_once_with("gemini")
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
