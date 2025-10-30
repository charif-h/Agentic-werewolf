"""
Models for the Werewolves game
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class PersonalityType(str, Enum):
    """16 Personality Types based on MBTI"""
    INTJ = "INTJ"  # Architect
    INTP = "INTP"  # Logician
    ENTJ = "ENTJ"  # Commander
    ENTP = "ENTP"  # Debater
    INFJ = "INFJ"  # Advocate
    INFP = "INFP"  # Mediator
    ENFJ = "ENFJ"  # Protagonist
    ENFP = "ENFP"  # Campaigner
    ISTJ = "ISTJ"  # Logistician
    ISFJ = "ISFJ"  # Defender
    ESTJ = "ESTJ"  # Executive
    ESFJ = "ESFJ"  # Consul
    ISTP = "ISTP"  # Virtuoso
    ISFP = "ISFP"  # Adventurer
    ESTP = "ESTP"  # Entrepreneur
    ESFP = "ESFP"  # Entertainer


class Sex(str, Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non-binary"


class Role(str, Enum):
    """Game roles in Werewolves of Millers Hollow"""
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    SEER = "seer"
    WITCH = "witch"
    HUNTER = "hunter"
    CUPID = "cupid"
    LITTLE_GIRL = "little_girl"
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
    IN_LOVE = "in_love"


class PlayerProfile(BaseModel):
    """Player profile with personality"""
    id: str
    name: str
    sex: Sex
    age: int = Field(ge=18, le=80)
    personality: PersonalityType
    role: Optional[Role] = None
    status: PlayerStatus = PlayerStatus.ALIVE
    in_love_with: Optional[str] = None  # Player ID
    
    def get_personality_description(self) -> str:
        """Get detailed personality description for AI prompts"""
        descriptions = {
            PersonalityType.INTJ: "Strategic, analytical, and independent thinker. Plans ahead and values logic.",
            PersonalityType.INTP: "Innovative, curious, and logical. Enjoys complex problem-solving.",
            PersonalityType.ENTJ: "Bold, strong-willed leader. Good at making decisions and organizing.",
            PersonalityType.ENTP: "Smart, curious debater. Enjoys intellectual challenges and arguing points.",
            PersonalityType.INFJ: "Idealistic, organized advocate. Strong values and vision for the future.",
            PersonalityType.INFP: "Poetic, kind mediator. Guided by principles and values.",
            PersonalityType.ENFJ: "Charismatic, inspiring leader. Natural at bringing people together.",
            PersonalityType.ENFP: "Enthusiastic, creative, and sociable. Free spirit with great people skills.",
            PersonalityType.ISTJ: "Practical, fact-minded logistician. Reliable and thorough.",
            PersonalityType.ISFJ: "Dedicated, warm protector. Always ready to defend loved ones.",
            PersonalityType.ESTJ: "Excellent administrator, manages people and systems efficiently.",
            PersonalityType.ESFJ: "Caring, social, and popular. Eager to help and please others.",
            PersonalityType.ISTP: "Bold, practical experimenter. Master of tools and techniques.",
            PersonalityType.ISFP: "Flexible, charming artist. Explores life with aesthetic sensibility.",
            PersonalityType.ESTP: "Smart, energetic, and perceptive. Lives in the moment.",
            PersonalityType.ESFP: "Spontaneous, enthusiastic entertainer. Enjoys life and people."
        }
        return descriptions.get(self.personality, "Unique personality")


class GameState(BaseModel):
    """Current state of the game"""
    phase: GamePhase = GamePhase.SETUP
    day_number: int = 0
    players: List[PlayerProfile] = []
    eliminated_players: List[str] = []  # Player IDs
    night_actions: dict = {}
    voting_results: dict = {}
    game_log: List[str] = []
    
    
class Message(BaseModel):
    """Message in the game"""
    sender: str
    content: str
    timestamp: str
    message_type: str = "chat"  # chat, action, system
