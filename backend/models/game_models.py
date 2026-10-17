"""
Models for the Werewolves game
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

from backend.models.personality import BigFive, PersonaCheck


class Sex(str, Enum):
    """Only these two values are supported (the name lists in the profile generator match)"""
    MALE = "male"
    FEMALE = "female"


class Role(str, Enum):
    """Game roles in Werewolves of Millers Hollow"""
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    GUARD = "guard"


class GamePhase(str, Enum):
    SETUP = "setup"
    NIGHT = "night"
    DAY = "day"
    DISCUSSION = "discussion"
    VOTING = "voting"
    ENDED = "ended"


class PlayerStatus(str, Enum):
    ALIVE = "alive"
    DEAD = "dead"


class PlayerProfile(BaseModel):
    """Player profile with personality"""
    id: str
    name: str
    sex: Sex
    age: int = Field(ge=18, le=80)
    personality: BigFive
    role: Optional[Role] = None
    status: PlayerStatus = PlayerStatus.ALIVE
    persona_check: Optional[PersonaCheck] = None   # result of the psychological test, None until it ran

    def get_personality_description(self) -> str:
        """Detailed personality description for AI prompts (one line per Big Five trait)"""
        return self.personality.describe()


class Message(BaseModel):
    """Message in the game"""
    sender: str
    content: str
    timestamp: str
    message_type: str = "chat"  # chat, action, system


class Discussion(BaseModel):
    """Discussion round with messages"""
    round_number: int
    topic: str
    messages: List[Message] = Field(default_factory=list)


class GameState(BaseModel):
    """Current state of the game"""
    phase: GamePhase = GamePhase.SETUP
    day_number: int = 0
    players: List[PlayerProfile] = Field(default_factory=list)
    eliminated_players: List[str] = Field(default_factory=list)  # Player IDs
    night_actions: dict = Field(default_factory=dict)
    game_log: List[str] = Field(default_factory=list)
    wolf_log: List[str] = Field(default_factory=list)   # private talk of the werewolves, never in the public log
    discussions: List[Discussion] = Field(default_factory=list)  # Store all discussions for context
    witch_heal_used: bool = False
    witch_poison_used: bool = False
    guard_last_protected: Optional[str] = None  # Player ID the guard protected last night
