"""Structured (JSON) decisions: schemas, parsers, and how the agent uses them."""
import json

import pytest

from backend.agents.player_agent import PlayerAgent
from backend.llm import FakeLLMClient, LLMError
from backend.llm import schemas
from backend.llm.fake import fit_to_schema
from backend.models.game_models import PersonalityType, PlayerProfile, Role, Sex

NAMES = ["Bob", "Cy", "Dee"]


def make_agent(role, responses, wrap_json=True):
    profile = PlayerProfile(id="p", name="Ann", sex=Sex.FEMALE, age=30,
                            personality=PersonalityType.INTJ, role=role)
    return PlayerAgent(profile, FakeLLMClient(responses, wrap_json=wrap_json))


STATE = {'phase': 'night', 'day_number': 1, 'players': [], 'valid_targets': NAMES}


# --- schemas and parsers ---------------------------------------------------------------

def test_target_schema_restricts_the_answer_to_valid_names():
    schema = schemas.target_schema(NAMES)
    assert schema["properties"]["target"]["enum"] == NAMES
    assert schema["required"] == ["target"]
    assert "enum" not in schemas.target_schema([])["properties"]["target"]


def test_witch_schema_allows_none():
    schema = schemas.witch_schema(["Bob"])
    assert schema["properties"]["poison"]["enum"] == ["Bob", "none"]
    assert set(schema["required"]) == {"save", "poison"}


@pytest.mark.parametrize("text,expected", [
    ('{"target": "Bob"}', "Bob"),
    ('{"target": " cy "}', "Cy"),
    ('```json\n{"target": "Dee"}\n```', "Dee"),
    ('{"target": "Zed"}', None),
    ('{"target": 3}', None),
    ('{"name": "Bob"}', None),
    ('Bob', None),
    ('["Bob"]', None),
    ('', None),
    (None, None),
])
def test_parse_target(text, expected):
    assert schemas.parse_target(text, NAMES) == expected


def test_parse_discussion():
    assert schemas.parse_discussion('{"speak": true, "message": "Hi"}') == (True, "Hi")
    assert schemas.parse_discussion('{"speak": false, "message": ""}') == (False, "")
    assert schemas.parse_discussion('{"speak": "yes", "message": "Hi"}') is None
    assert schemas.parse_discussion('{"speak": true}') is None
    assert schemas.parse_discussion("hello") is None


def test_parse_witch():
    assert schemas.parse_witch('{"save": true, "poison": "none"}', NAMES) == (True, None)
    assert schemas.parse_witch('{"save": false, "poison": "cy"}', NAMES) == (False, "Cy")
    assert schemas.parse_witch('{"save": false, "poison": "Zed"}', NAMES) == (False, None)
    assert schemas.parse_witch('{"save": 1, "poison": "none"}', NAMES) is None
    assert schemas.parse_witch("SAVE", NAMES) is None


# --- the fake client wraps plain answers so scripted tests stay short ----------------------------

def test_fake_wraps_plain_text_for_each_schema():
    assert json.loads(fit_to_schema("Bob.", schemas.target_schema(NAMES))) == {"target": "Bob"}
    assert json.loads(fit_to_schema("Hello", schemas.discussion_schema())) == {"speak": True, "message": "Hello"}
    assert json.loads(fit_to_schema("No comment.", schemas.discussion_schema())) == {"speak": False, "message": ""}
    witch = schemas.witch_schema(NAMES)
    assert json.loads(fit_to_schema("SAVE and POISON Cy", witch)) == {"save": True, "poison": "Cy"}
    assert json.loads(fit_to_schema("PASS", witch)) == {"save": False, "poison": "none"}


def test_fake_leaves_real_json_alone_and_can_return_raw_text():
    raw = '{"target": "Cy"}'
    assert fit_to_schema(raw, schemas.target_schema(NAMES)) == raw
    client = FakeLLMClient("Bob", wrap_json=False)
    assert client.generate([], json_schema=schemas.target_schema(NAMES)) == "Bob"


# --- the agent asks for JSON and cannot be fooled -----------------------------------------------

def test_vote_requests_a_schema_listing_the_other_players():
    agent = make_agent(Role.VILLAGER, "Cy")
    assert agent.vote("talk", ["Ann", "Bob", "Cy"]) == "Cy"
    options = agent.llm.calls[0][1]
    assert options["json_schema"]["properties"]["target"]["enum"] == ["Bob", "Cy"]     # not "Ann"
    assert options["max_tokens"] == 60


def test_vote_falls_back_to_a_random_valid_candidate_when_the_answer_is_not_valid_json():
    agent = make_agent(Role.VILLAGER, "I think it is Cy because he is quiet", wrap_json=False)
    seen = {agent.vote("talk", ["Ann", "Bob", "Cy"]) for _ in range(60)}
    assert seen == {"Bob", "Cy"}                 # no substring guessing, no bias to one player


def test_vote_ignores_a_name_outside_the_candidates():
    agent = make_agent(Role.VILLAGER, '{"target": "Zed"}', wrap_json=False)
    assert agent.vote("talk", ["Ann", "Bob", "Cy"]) in ("Bob", "Cy")


def test_vote_survives_a_model_error():
    agent = make_agent(Role.VILLAGER, LLMError("down"))
    assert agent.vote("talk", ["Ann", "Bob"]) == "Bob"


def test_night_action_returns_the_chosen_name_or_none():
    assert make_agent(Role.SEER, "dee").night_action(STATE) == "Dee"
    assert make_agent(Role.SEER, "nobody", wrap_json=False).night_action(STATE) is None
    assert make_agent(Role.SEER, LLMError("down")).night_action(STATE) is None
    assert make_agent(Role.VILLAGER, "Bob").night_action(STATE) is None        # no night action


def test_night_action_asks_with_the_valid_targets_as_enum():
    agent = make_agent(Role.WEREWOLF, "Bob")
    agent.night_action(STATE)
    assert agent.llm.calls[0][1]["json_schema"]["properties"]["target"]["enum"] == NAMES
    assert 'Answer in JSON: {"target": "<name>"}.' in agent.llm.last_messages[-1].content


def test_hunter_shot():
    agent = make_agent(Role.HUNTER, "Cy")
    assert agent.hunter_shot(STATE, NAMES) == "Cy"
    assert make_agent(Role.HUNTER, "???", wrap_json=False).hunter_shot(STATE, NAMES) is None


@pytest.mark.parametrize("raw,can_save,can_poison,expected", [
    ('{"save": true, "poison": "none"}', True, True, "SAVE"),
    ('{"save": false, "poison": "Cy"}', True, True, "POISON Cy"),
    ('{"save": true, "poison": "Cy"}', True, True, "SAVE and POISON Cy"),
    ('{"save": false, "poison": "none"}', True, True, "PASS"),
    ('{"save": true, "poison": "Cy"}', False, False, "PASS"),         # no potions left
    ('{"save": true, "poison": "Cy"}', False, True, "POISON Cy"),
    ("what?", True, True, "PASS"),                                   # unclear: no potion at random
])
def test_witch_action(raw, can_save, can_poison, expected):
    agent = make_agent(Role.WITCH, raw, wrap_json=False)
    assert agent.witch_action(STATE, "Bob", can_save, can_poison, NAMES) == expected


def test_witch_action_survives_a_model_error():
    assert make_agent(Role.WITCH, LLMError("down")).witch_action(STATE, "Bob", True, True, NAMES) == "PASS"


def test_discussion_uses_the_speak_flag():
    spoken = '{"speak": true, "message": "Dee, you changed your story."}'
    assert make_agent(Role.VILLAGER, spoken, wrap_json=False).discuss("", ["Ann", "Bob"]) == "Dee, you changed your story."
    silent = '{"speak": false, "message": "ignored"}'
    assert make_agent(Role.VILLAGER, silent, wrap_json=False).discuss("", ["Ann", "Bob"]) == "no comment"
    assert make_agent(Role.VILLAGER, "just text", wrap_json=False).discuss("", ["Ann", "Bob"]) == "no comment"
    assert make_agent(Role.VILLAGER, LLMError("down")).discuss("", ["Ann", "Bob"]) == "no comment"


def test_discussion_requests_the_discussion_schema():
    agent = make_agent(Role.VILLAGER, "Hi there")
    agent.discuss("", ["Ann", "Bob"])
    options = agent.llm.calls[0][1]
    assert set(options["json_schema"]["properties"]) == {"speak", "message"}
    assert options["max_tokens"] == 160
