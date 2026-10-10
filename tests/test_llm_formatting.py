"""Chat formatting for Gemma and rough token budgeting."""
from backend.llm import ASSISTANT, SYSTEM, USER, Message, estimate_tokens, fit_lines, fit_text, to_alternating

SEP = "\n\n"


def roles(messages):
    return [m.role for m in messages]


def test_system_message_becomes_a_prefix_of_the_first_user_turn():
    out = to_alternating([Message(SYSTEM, "rules"), Message(USER, "hi")])
    assert out == [Message(USER, "rules" + SEP + "hi")]


def test_already_alternating_conversation_is_unchanged_apart_from_the_system_prefix():
    out = to_alternating([Message(SYSTEM, "s"), Message(USER, "a"), Message(ASSISTANT, "b"), Message(USER, "c")])
    assert out == [Message(USER, "s" + SEP + "a"), Message(ASSISTANT, "b"), Message(USER, "c")]


def test_consecutive_messages_of_the_same_role_are_merged():
    out = to_alternating([Message(USER, "a"), Message(USER, "b"), Message(ASSISTANT, "c"), Message(ASSISTANT, "d"),
                          Message(USER, "e")])
    assert out == [Message(USER, "a" + SEP + "b"), Message(ASSISTANT, "c" + SEP + "d"), Message(USER, "e")]


def test_leading_assistant_turns_are_dropped():
    out = to_alternating([Message(SYSTEM, "s"), Message(ASSISTANT, "orphan"), Message(USER, "q")])
    assert out == [Message(USER, "s" + SEP + "q")]


def test_trailing_assistant_turn_is_dropped():
    out = to_alternating([Message(USER, "q"), Message(ASSISTANT, "a")])
    assert out == [Message(USER, "q")]


def test_several_system_messages_are_joined():
    out = to_alternating([Message(SYSTEM, "one"), Message(SYSTEM, "two"), Message(USER, "q")])
    assert out == [Message(USER, "one" + SEP + "two" + SEP + "q")]


def test_only_a_system_message_becomes_a_user_turn():
    assert to_alternating([Message(SYSTEM, "s")]) == [Message(USER, "s")]
    assert to_alternating([]) == []


def test_result_always_alternates_and_input_is_untouched():
    original = [Message(SYSTEM, "s"), Message(ASSISTANT, "x"), Message(USER, "a"), Message(USER, "b"),
                Message(ASSISTANT, "c"), Message(ASSISTANT, "d")]
    snapshot = list(original)
    out = to_alternating(original)
    assert original == snapshot
    assert roles(out)[0] == USER and roles(out)[-1] == USER
    assert all(a != b for a, b in zip(roles(out), roles(out)[1:]))


def test_estimate_tokens_is_monotonic_and_never_zero():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abc" * 10) < estimate_tokens("abc" * 20)


def test_fit_lines_keeps_the_most_recent_lines():
    lines = [f"line {i:03d} " + "x" * 20 for i in range(50)]
    kept = fit_lines(lines, 60)
    assert kept[0] == "[earlier messages omitted]"
    assert kept[-1] == lines[-1]
    assert sum(estimate_tokens(line) + 1 for line in kept[1:]) <= 60
    assert fit_lines(lines[:2], 1000) == lines[:2]            # everything fits: no notice


def test_fit_lines_cuts_a_single_huge_line_from_its_start():
    kept = fit_lines(["a" * 10_000 + "END"], 20)
    assert kept[-1].endswith("END") and len(kept[-1]) < 100


def test_fit_text():
    assert fit_text("", 10) == ""
    text = "\n".join(f"row {i}" for i in range(100))
    out = fit_text(text, 30)
    assert out.splitlines()[0] == "[earlier messages omitted]" and out.endswith("row 99")
