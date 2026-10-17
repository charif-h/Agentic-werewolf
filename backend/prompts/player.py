"""
Prompt templates for player agents.

All wording sent to the LLM for players lives here, as plain functions that
return strings. Role-specific text (description, strategies, night prompt)
lives in the role handlers (`backend.roles`), which are passed in by the agent.

The prompts are written for a small local model (Gemma 3 4B): short, one
instruction per sentence, an example of a good answer, and a last line that
says exactly what to answer.
"""
import re
from typing import List, Optional

NO_COMMENT = "no comment"

DISCUSSION_ANSWER_FORMAT = (
    'Answer in JSON: {"speak": true, "message": "<what you say out loud, one or two short sentences>"}. '
    'If you really have nothing to add, answer {"speak": false, "message": ""}. '
    "Write the JSON with plain straight quotes and apostrophes, never curly ones.")
TARGET_ANSWER_FORMAT = 'Answer in JSON: {"target": "<name>"}.'
WITCH_ANSWER_FORMAT = ('Answer in JSON: {"save": true or false, "poison": "<name>" or "none"}. '
                       'Use true / a name only for a potion you still have.')

DIARY_ANSWER_FORMAT = (
    '{"summary": "<two sentences on how you feel about this step>", "opinions": [{"player": "<name>", '
    '"reason": "<one short sentence>", "guess": "werewolf" or "villager" or "unsure", '
    '"confidence": "low" or "medium" or "high"}]}. Straight quotes only.')

PSYTEST_SCALE = "1 = strongly disagree, 2 = disagree, 3 = neutral, 4 = agree, 5 = strongly agree"

ROLE_WORDS = ("werewolf", "werewolves", "villager", "villagers", "seer", "witch", "hunter", "guard")

# Examples of short in-character replies (shown to the model in the discussion prompt)
DISCUSSION_EXAMPLES = (
    '- "Dee, you changed your story twice. Why?"\n'
    '- "I trust Bob. He stayed with us all night."\n'
    '- "Something is off about Eli, he has not said a word."'
)

# Examples for the first message of the day: nobody has said anything yet, so no one can be quoted
OPENER_EXAMPLES = (
    '- "Bob is dead. Who was awake last night and heard something?"\n'
    '- "Two of us could be wolves already. Where was everyone last night?"\n'
    '- "I saw nothing. Let us hear everybody before we accuse anyone."'
)


def diary_notes(entry: Optional[dict]) -> List[str]:
    """The opinions of a diary entry as lines of private notes for later prompts (empty without entry)"""
    if not entry:
        return []
    words = {"werewolf": "you suspect", "villager": "you trust", "unsure": "you are unsure about"}
    return [f"{entry['step']}, {words[o['guess']]} {o['player']} ({o['confidence']} confidence): {o['reason']}"
            for o in entry["opinions"]]


def knowledge_block(knowledge: Optional[List[str]]) -> str:
    """Secret facts the player learned during the game ('' when there are none)"""
    if not knowledge:
        return ""
    return "\nWHAT YOU KNOW (secret):\n" + "\n".join(f"- {fact}" for fact in knowledge) + "\n"


def player_system_prompt(name: str, age: int, sex: str, personality_description: str,
                         role_description: Optional[str] = None,
                         knowledge: Optional[List[str]] = None) -> str:
    """Persona prompt used for night actions and other general actions"""
    lines = [
        f"You are {name}, a {age}-year-old {sex}, playing The Werewolves of Millers Hollow.",
        f"Your personality (Big Five), show it in how you speak and decide:\n{personality_description}",
    ]
    if role_description:
        lines.append(f"Your role: {role_description}")
    prompt = "\n".join(lines)
    if knowledge:
        prompt += "\n" + knowledge_block(knowledge)
    return prompt + "\nStay in character. Never reveal your own role."


def short_reply_system_prompt(name: str, personality_summary: str) -> str:
    """Compact persona prompt used for discussion and voting"""
    return (f"You are {name}, playing Werewolf. Your personality (Big Five): {personality_summary}.\n"
            "Your personality drives everything you say and every choice you make: "
            "speak and decide the way this person would.\n"
            "Answer like a real person around a table: one or two short sentences, in character. "
            "Name a player when you accuse or defend someone, and give a reason. "
            "Never reveal your own role. No explanations, no stage directions.")


def game_context(phase: str, day_number: int, alive_names: List[str], recent_events,
                 discussion_lines: List[str], action: str) -> str:
    """Game state summary followed by the action the player must take"""
    discussion_context = ""
    if discussion_lines:
        discussion_context = "\nRecent discussion:\n" + "\n".join(discussion_lines) + "\n"
    return (f"Phase: {phase}, day {day_number}.\n"
            f"Alive players: {', '.join(alive_names)}.\n"
            f"Recent events: {recent_events}\n"
            f"{discussion_context}\n"
            f"{action}")


def response_factors(name: str, conversation: str, role_hint: str) -> str:
    """Bullet list of reasons the player might want to speak"""
    factors = []
    if name in conversation:
        factors.append("- You have been mentioned or addressed")
    if conversation:
        if len(conversation.strip().split('\n')) >= 2:  # there are recent messages
            factors.append("- Recent activity in conversation")
    if role_hint:
        factors.append(role_hint)
    if not factors:
        factors.append("- No special pressure to respond")
    return '\n'.join(factors)


def scene_block(day_number: int, announcement: str, alive_names: List[str], spoken: int) -> str:
    """
    Where the village is right now: the day, what the narrator announced about the night,
    who is alive and how many messages were said since the day began (top of discussion and vote prompts)
    """
    where = ("You speak first: nobody has said anything today." if spoken == 0
             else f"{spoken} message{'s' if spoken > 1 else ''} said since the day began.")
    return (f"Day {day_number}. {announcement}\n"
            f"Alive players: {', '.join(alive_names)}.\n"
            f"{where}\n\n")


OPENER_INSTRUCTION = ("Open the discussion yourself. Nobody has said anything yet. "
                      "Do not refer to earlier talk.")


def discussion_prompt(name: str, conversation: str, alive_names: List[str], role: str,
                      role_strategy: str, factors: str,
                      knowledge: Optional[List[str]] = None, scene: str = "") -> str:
    """Ask a player what to say in the discussion"""
    return f"""{scene}You are {name} in the village discussion.

Conversation so far:
{conversation if conversation.strip() else OPENER_INSTRUCTION}

Alive players: {', '.join(alive_names)}

Secret: you are a {role}. {role_strategy}
{knowledge_block(knowledge)}
Reasons to speak:
{factors}

Good replies look like this:
{DISCUSSION_EXAMPLES if conversation.strip() else OPENER_EXAMPLES}

{DISCUSSION_ANSWER_FORMAT}"""


def vote_prompt(name: str, role: str, voting_strategy: str, conversation: str,
                candidates: List[str], knowledge: Optional[List[str]] = None, scene: str = "") -> str:
    """Ask a player who to vote for"""
    return f"""{scene}You are {name}, voting to eliminate someone.

Secret: you are a {role}. {voting_strategy}
{knowledge_block(knowledge)}
Conversation:
{conversation if conversation.strip() else "Nobody spoke."}

Candidates: {', '.join(candidates)}

Pick the player you find most suspicious, the way your personality would. {TARGET_ANSWER_FORMAT}"""


def witch_prompt(victim: Optional[str], can_save: bool, can_poison: bool,
                 poison_targets: List[str]) -> str:
    """Ask the witch what she does tonight"""
    lines = [f"As the witch, the werewolves attacked {victim} tonight." if victim
             else "As the witch, nobody was attacked tonight."]
    options = []
    if can_save:
        options.append("save: use your healing potion on the victim")
    if can_poison:
        options.append(f"poison: kill one player among {', '.join(poison_targets)}")
    lines.append("Your options: " + ("; ".join(options) + "; or do nothing." if options
                                     else "do nothing, your potions are used."))
    lines.append(WITCH_ANSWER_FORMAT)
    return " ".join(lines)


def hunter_prompt(instruction: str, targets: List[str]) -> str:
    """Ask the dying hunter who to shoot"""
    return f"{instruction} from these players: {', '.join(targets)}. {TARGET_ANSWER_FORMAT}"


def diary_prompt(name: str, role: str, personality_summary: str, step: str, events: str,
                 others: List[str], previous: Optional[str] = None,
                 knowledge: Optional[List[str]] = None, vote: Optional[str] = None) -> str:
    """Ask a player to write their private diary entry for the step that just ended"""
    voted = f"\nYou voted to eliminate {vote}, so you suspect {vote}.\n" if vote else ""
    before = f"\nYour last diary entry said: {previous}\n" if previous else ""
    return f"""You are {name}, writing your private diary. Nobody else reads it, so be honest about what you think.
Secret: you are a {role}. Your personality (Big Five): {personality_summary}. Write the way you think.
{knowledge_block(knowledge)}{before}{voted}
What happened during {step}:
{events if events.strip() else "Nothing notable."}

Write what you think of {step}, then give your opinion of EACH of these players: {', '.join(others)}.
For each one give a short reason that refers to what they said or did, then your conclusion:
"werewolf" = you suspect them, "villager" = you trust them, "unsure" = you cannot tell; and how sure you are (low, medium or high).
The conclusion MUST agree with the reason: a reason that doubts someone means "werewolf", a reason that trusts someone means "villager".
Answer in JSON: {DIARY_ANSWER_FORMAT}"""


def psytest_prompt(name: str, statements: List[str]) -> str:
    """Ask a player to rate statements about themselves (the psychological test)"""
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(statements, 1))
    return f"""{name}, answer this questionnaire as the person you are: as you generally are, not as you would like to be.
Rate how well each statement describes you: {PSYTEST_SCALE}.

{numbered}

Answer in JSON, one entry per statement, in order. Write the statement, then your rating from 1 to 5:
{{"answers": [{{"statement": "<the statement>", "rating": <1-5>}}, ...]}}"""


def leaks_own_role(text: str, role: str) -> bool:
    """
    Does `text` state the speaker's own role ("I am the seer", "as a hunter", "my role")?

    Accusing someone of being a werewolf is normal play and is not a leak.
    """
    lowered = text.lower()
    if "my role" in lowered:
        return True
    pattern = (rf"\b(i am|i'm|im|as|being|i was)\s+(the|a|an|just|only)?\s*{re.escape(role.lower())}s?\b")
    return re.search(pattern, lowered) is not None


BACKREFERENCES = ("as i said", "as i mentioned", "like i said", "like you said", "as you said", "as we said",
                  "as we discussed", "as discussed", "earlier", "before the break", "we were saying",
                  "to continue", "going back to", "you said", "you told", "you mentioned", "you claimed",
                  "you were saying", "your story", "you changed")


def refers_to_earlier_talk(text: str) -> bool:
    """Does `text` refer to an earlier exchange ("as I said", "like you said", "earlier")?"""
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(phrase)}\b", lowered) for phrase in BACKREFERENCES)


BACKREFERENCE_REMINDER = ("\n\n(Nobody has spoken yet today. Do not refer to earlier talk. "
                          "Say it again as the first thing said.)")

LEAK_REMINDER ="\n\n(Do not state your own role. Say it again without revealing it.)"
