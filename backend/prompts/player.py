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

PERSONALITY_BEHAVIOR = {
    "ENFP": "enthusiastic and curious",
    "ENFJ": "empathetic and diplomatic",
    "ENTP": "witty and analytical",
    "ENTJ": "direct and strategic",
    "ESFP": "friendly and spontaneous",
    "ESFJ": "caring and cooperative",
    "ESTP": "practical and observant",
    "ESTJ": "organized and decisive",
    "INFP": "thoughtful and idealistic",
    "INFJ": "insightful and reserved",
    "INTP": "logical and skeptical",
    "INTJ": "independent and methodical",
    "ISFP": "gentle and cautious",
    "ISFJ": "supportive and dutiful",
    "ISTP": "calm and pragmatic",
    "ISTJ": "reliable and careful",
}

NO_COMMENT = "no comment"

ROLE_WORDS = ("werewolf", "werewolves", "villager", "villagers", "seer", "witch", "hunter", "guard")

# Examples of short in-character replies (shown to the model in the discussion prompt)
DISCUSSION_EXAMPLES = (
    '- "Dee, you changed your story twice. Why?"\n'
    '- "I trust Bob. He stayed with us all night."\n'
    '- "Something is off about Eli, he has not said a word."'
)


def personality_behavior(personality: str) -> str:
    """Short description of how a personality type behaves"""
    return PERSONALITY_BEHAVIOR.get(personality, "neutral")


def knowledge_block(knowledge: Optional[List[str]]) -> str:
    """Secret facts the player learned during the game ('' when there are none)"""
    if not knowledge:
        return ""
    return "\nWHAT YOU KNOW (secret):\n" + "\n".join(f"- {fact}" for fact in knowledge) + "\n"


def player_system_prompt(name: str, age: int, sex: str, personality: str,
                         personality_description: str,
                         role_description: Optional[str] = None,
                         knowledge: Optional[List[str]] = None) -> str:
    """Persona prompt used for night actions and other general actions"""
    lines = [
        f"You are {name}, a {age}-year-old {sex}, playing The Werewolves of Millers Hollow.",
        f"Personality ({personality}): {personality_description}",
    ]
    if role_description:
        lines.append(f"Your role: {role_description}")
    prompt = "\n".join(lines)
    if knowledge:
        prompt += "\n" + knowledge_block(knowledge)
    return prompt + "\nStay in character. Never reveal your own role."


def short_reply_system_prompt(name: str, personality: str) -> str:
    """Compact persona prompt used for discussion and voting"""
    return (f"You are {name}, playing Werewolf. Personality ({personality}): "
            f"{personality_behavior(personality)}.\n"
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


def discussion_prompt(name: str, conversation: str, alive_names: List[str], role: str,
                      role_strategy: str, factors: str,
                      knowledge: Optional[List[str]] = None) -> str:
    """Ask a player what to say in the discussion"""
    return f"""You are {name} in the village discussion.

Conversation so far:
{conversation if conversation.strip() else "Nobody has spoken yet."}

Alive players: {', '.join(alive_names)}

Secret: you are a {role}. {role_strategy}
{knowledge_block(knowledge)}
Reasons to speak:
{factors}

Good replies look like this:
{DISCUSSION_EXAMPLES}

Say what you say out loud: one or two short sentences. If you really have nothing to add, answer exactly: {NO_COMMENT}"""


def vote_prompt(name: str, role: str, voting_strategy: str, conversation: str,
                candidates: List[str], knowledge: Optional[List[str]] = None) -> str:
    """Ask a player who to vote for"""
    return f"""You are {name}, voting to eliminate someone.

Secret: you are a {role}. {voting_strategy}
{knowledge_block(knowledge)}
Conversation:
{conversation if conversation.strip() else "Nobody spoke."}

Candidates: {', '.join(candidates)}

Pick the player you find most suspicious. Answer with ONLY one name from the candidates."""


def witch_prompt(victim: Optional[str], can_save: bool, can_poison: bool,
                 poison_targets: List[str]) -> str:
    """Ask the witch what she does tonight"""
    lines = [f"As the witch, the werewolves attacked {victim} tonight." if victim
             else "As the witch, nobody was attacked tonight."]
    options = []
    if can_save:
        options.append("SAVE (use your healing potion on the victim)")
    if can_poison:
        options.append(f"POISON <name> (kill one player among: {', '.join(poison_targets)})")
    options.append("PASS (do nothing)")
    lines.append("Your options: " + "; ".join(options) + ".")
    lines.append("Answer with exactly one of: " + ", ".join(
        (["SAVE"] if can_save else []) + (["POISON <name>"] if can_poison else []) + ["PASS"]) + ".")
    return " ".join(lines)


def hunter_prompt(instruction: str, targets: List[str]) -> str:
    """Ask the dying hunter who to shoot"""
    return f"{instruction} from these players: {', '.join(targets)}. Respond with ONLY the player's name."


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


LEAK_REMINDER = "\n\n(Do not state your own role. Say it again without revealing it.)"
