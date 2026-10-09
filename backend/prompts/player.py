"""
Prompt templates for player agents.

All wording sent to the LLM for players lives here, as plain functions that
return strings. Role-specific text (description, strategies, night prompt)
lives in the role handlers (`backend.roles`), which are passed in by the agent.
"""
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
    """Full persona prompt used for night actions and general actions"""
    prompt = f"""You are {name}, a {age}-year-old {sex}{" "}
playing The Werewolves of Millers Hollow.

Your Personality: {personality} - {personality_description}

Your personality influences how you:
- Communicate with others (formal/casual, aggressive/gentle, logical/emotional)
- Make decisions and vote
- React to accusations and events
- Build trust or suspicion with other players
"""
    if role_description:
        prompt += f"\n\nYour Role: {role_description}"
    if knowledge:
        prompt += "\n" + knowledge_block(knowledge)
    prompt += "\n\nPlay authentically according to your personality and role. Stay in character."
    return prompt


def short_reply_system_prompt(name: str, personality: str) -> str:
    """Compact persona prompt used for discussion and voting"""
    # Note the space after "Werewolf." (kept from the original prompt)
    return f"""You are {name} playing Werewolf.{" "}

CRITICAL RULES:
- Keep responses SHORT (1-2 sentences maximum)
- NEVER mention roles directly (werewolf, villager, seer, etc.)
- Be subtle and natural
- Don't explain your reasoning or strategy
- Act like a normal person in a tense situation

Personality: {personality} - be {personality_behavior(personality)}"""


def game_context(phase: str, day_number: int, alive_names: List[str], recent_events,
                 discussion_lines: List[str], action: str) -> str:
    """Game state summary followed by the action the player must take"""
    discussion_context = ""
    if discussion_lines:
        discussion_context = "\nRecent Discussions:\n" + "\n".join(discussion_lines)
    return f"""
Current Game State:
- Phase: {phase}
- Day: {day_number}
- Alive Players: {', '.join(alive_names)}
- Recent Events: {recent_events}
{discussion_context}

Current Action: {action}
"""


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
    """Ask a player whether and what to say in the discussion"""
    return f"""You are {name} in a Werewolf game discussion.

CURRENT CONVERSATION:
{conversation if conversation.strip() else "No one has spoken yet."}

ALIVE PLAYERS: {', '.join(alive_names)}

YOUR HIDDEN INFO: You are a {role}
{role_strategy}
{knowledge_block(knowledge)}
RESPONSE FACTORS:
{factors}

INSTRUCTIONS:
- Keep response SHORT (1-2 sentences max)
- NEVER mention roles directly (werewolf, villager, etc.)
- You can respond to what others said or ask questions
- Be subtle and natural
- If you have nothing to add, say "no comment"

Do you want to respond to the current conversation?"""


def vote_prompt(name: str, role: str, voting_strategy: str, conversation: str,
                candidates: List[str], knowledge: Optional[List[str]] = None) -> str:
    """Ask a player who to vote for"""
    return f"""You are {name} voting to eliminate someone.

YOUR HIDDEN INFO: You are a {role}
{voting_strategy}
{knowledge_block(knowledge)}
CONVERSATION RECAP:
{conversation if conversation.strip() else "No discussion took place."}

VOTING CANDIDATES: {', '.join(candidates)}

INSTRUCTIONS:
- Analyze who acted most suspiciously
- Consider who seemed defensive or evasive
- Think about who tried to redirect blame
- Vote for who you personally find most suspicious
- Respond with ONLY the player's name

Who do you vote to eliminate?"""


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
