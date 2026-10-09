"""
Base class for role handlers (strategy pattern)

A handler bundles everything that is specific to one role: its team, the
prompts that describe it to the LLM, and its night action. To add a role, add
one module in this package that defines a subclass and registers it.
"""
from typing import Dict, List, Optional

from backend.models.game_models import GameState, PlayerProfile, PlayerStatus, Role

WEREWOLVES = "werewolves"
VILLAGERS = "villagers"

DEFAULT_RATE_LIMIT_REPLY = "I'm still thinking about this situation."

VILLAGE_DISCUSSION_STRATEGY = """Your goal: find and eliminate werewolves.
- Ask probing questions
- Point out suspicious behavior
- Work with others to find threats"""

VILLAGE_VOTING_STRATEGY = """As a VILLAGE TEAM member, vote to eliminate:
1. The player who acted most suspiciously during discussions
2. Anyone who deflected questions or was overly defensive
3. Players whose behavior doesn't match their claimed actions
4. The person you personally believe is most likely to be a werewolf"""


class RoleHandler:
    """Everything the game needs to know about one role"""

    role: Role
    team: str = VILLAGERS

    # Prompts
    description: str = ""            # "You are the X..." (system prompt)
    discussion_strategy: str = VILLAGE_DISCUSSION_STRATEGY  # tips when speaking in the discussion
    voting_strategy: str = VILLAGE_VOTING_STRATEGY
    response_hint: str = ""          # extra line in the "should I speak?" factors
    rate_limit_reply: str = DEFAULT_RATE_LIMIT_REPLY

    # Night action. `night_order` is None for roles that do not act at night.
    night_order: Optional[int] = None
    night_instruction: str = ""      # e.g. "As the guard, choose a player to protect tonight"
    night_constraint: str = ""       # extra rule appended to the prompt
    announce_night_choice: bool = False  # Game Master announces that a choice was made

    # Death shot (hunter): when the player dies they immediately eliminate someone
    death_shot: bool = False
    death_shot_instruction: str = ""

    @property
    def acts_at_night(self) -> bool:
        return self.night_order is not None

    def night_targets(self, state: GameState, actor: PlayerProfile) -> List[str]:
        """Names `actor` may target tonight (empty if the role has no night action)"""
        return []

    def record_night(self, results: Dict, target: PlayerProfile) -> None:
        """Store this role's night choice in the night `results` dict"""

    def night_prompt(self, valid_targets: List[str]) -> str:
        """Prompt asking the player for a night target"""
        targets = f" from these players: {', '.join(valid_targets)}." if valid_targets else "."
        return (f"{self.night_instruction}{targets}{self.night_constraint} "
                "Respond with ONLY the player's name.")


def alive_names(state: GameState, exclude: Optional[str] = None) -> List[str]:
    """Names of alive players, optionally excluding the player with id `exclude`"""
    return [p.name for p in state.players
            if p.status == PlayerStatus.ALIVE and p.id != exclude]
