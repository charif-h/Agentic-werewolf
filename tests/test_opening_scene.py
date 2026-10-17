"""The first speaker of the day gets the scene, and no invented past (fake LLM, no network)."""
from backend import prompts
from backend.agents.player_agent import PlayerAgent
from backend.llm import FakeLLMClient
from backend.llm.metrics import LLMMetrics, track
from backend.models.game_models import BigFive, Message, PlayerProfile, Role, Sex

NAMES = ["Ann", "Bob", "Cy"]
SCENE = prompts.scene_block(2, "Day 2 begins. Bob was killed.", NAMES, 0)


def make_agent(answers):
    profile = PlayerProfile(id="p1", name="Ann", sex=Sex.FEMALE, age=30,
                            personality=BigFive(extraversion=2), role=Role.SEER)
    return PlayerAgent(profile, FakeLLMClient(answers))


def test_scene_block_says_who_died_and_that_you_speak_first():
    assert "Day 2. Day 2 begins. Bob was killed." in SCENE
    assert "Alive players: Ann, Bob, Cy." in SCENE
    assert "You speak first" in SCENE


def test_scene_block_counts_the_messages_said_since_the_day_began():
    assert "1 message said" in prompts.scene_block(1, "x", NAMES, 1)
    assert "3 messages said" in prompts.scene_block(1, "x", NAMES, 3)


def test_opener_prompt_has_the_scene_and_the_opening_instruction():
    agent = make_agent("Who killed Bob?")
    agent.discuss("", NAMES, SCENE)
    prompt = agent.llm.last_messages[-1].content
    assert prompt.startswith("Day 2. Day 2 begins. Bob was killed.")
    assert "You speak first" in prompt
    assert "Open the discussion yourself. Nobody has said anything yet." in prompt
    assert "Nobody has spoken yet." not in prompt


def test_vote_prompt_starts_with_the_scene():
    agent = make_agent("Bob")
    agent.vote("[Bob] hi", NAMES, prompts.scene_block(2, "Day 2 begins.", NAMES, 1))
    assert agent.llm.last_messages[-1].content.startswith("Day 2. Day 2 begins.")


def test_opener_does_not_carry_earlier_answers_but_later_speakers_do():
    agent = make_agent("Who killed Bob?")
    agent._remember("Night 1 question", "Night 1 answer")
    agent.discuss("", NAMES, SCENE)
    assert "Night 1 answer" not in [m.content for m in agent.llm.last_messages]
    agent.discuss("[Bob] hi", NAMES)
    assert "Night 1 answer" in [m.content for m in agent.llm.last_messages]


def test_backreference_in_the_opener_triggers_one_retry():
    agent = make_agent(["As I said earlier, Bob is suspicious.", "Who killed Bob last night?"])
    metrics = LLMMetrics()
    with track(metrics):
        reply = agent.discuss("", NAMES, SCENE)
    assert reply == "Who killed Bob last night?"
    assert len(agent.llm.calls) == 2
    assert "Do not refer to earlier talk" in agent.llm.last_messages[-1].content
    assert metrics.snapshot()["opening_backreference"] == 1


def test_backreference_with_other_speakers_is_not_a_problem():
    agent = make_agent("Like you said, Bob is suspicious.")
    metrics = LLMMetrics()
    with track(metrics):
        agent.discuss("[Bob] Cy is odd.", NAMES)
    assert len(agent.llm.calls) == 1
    assert metrics.snapshot()["opening_backreference"] == 0


def test_refers_to_earlier_talk():
    assert prompts.refers_to_earlier_talk("Like you said, it is Bob.")
    assert prompts.refers_to_earlier_talk("We spoke earlier about Cy.")
    assert not prompts.refers_to_earlier_talk("Bob died, who saw something?")


def test_short_system_prompt_makes_the_personality_drive_decisions():
    prompt = prompts.short_reply_system_prompt("Ann", "low extraversion (quiet)")
    assert "Your personality (Big Five): low extraversion (quiet)" in prompt
    assert "drives everything you say and every choice you make" in prompt


def test_opener_examples_do_not_quote_anyone():
    opener = prompts.discussion_prompt("Ann", "", NAMES, "seer", "S", "F")
    later = prompts.discussion_prompt("Ann", "[Bob] hi", NAMES, "seer", "S", "F")
    assert "you changed your story" not in opener and "you changed your story" in later


def test_accusing_someone_of_a_statement_nobody_made_counts_as_a_backreference():
    assert prompts.refers_to_earlier_talk("Patricia, you said you were outside? Tell me where.")
