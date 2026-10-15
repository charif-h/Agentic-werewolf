"""
Big Five personality of a player

Each trait has one of five levels (1 = very low ... 5 = very high). The levels are
turned into short behaviour sentences for the prompts, and the psychological test
(`backend.agents.psytest`) checks that the player really behaves as described.
"""
import random
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

TRAITS = ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism")
LEVEL_NAMES = {1: "very low", 2: "low", 3: "medium", 4: "high", 5: "very high"}

# How a player behaves at each level of each trait, as it shows in a Werewolf game
BEHAVIOR: Dict[str, Dict[int, str]] = {
    "openness": {
        1: "sticks to the familiar and distrusts odd theories",
        2: "practical, prefers simple and proven explanations",
        3: "open to new ideas when they are well argued",
        4: "curious, likes original theories and new angles",
        5: "very imaginative, loves bold and unusual theories",
    },
    "conscientiousness": {
        1: "impulsive and disorganised, acts without a plan",
        2: "casual, changes plans easily and often improvises",
        3: "reasonably organised, plans when needed",
        4: "methodical, checks facts and tracks who said what",
        5: "extremely disciplined, builds careful plans and forgets no detail",
    },
    "extraversion": {
        1: "very reserved, speaks rarely and briefly",
        2: "quiet, prefers to listen before speaking",
        3: "speaks when it matters",
        4: "sociable, joins the talk easily and often",
        5: "very talkative, speaks first and dominates the conversation",
    },
    "agreeableness": {
        1: "harsh and suspicious, accuses bluntly and trusts no one",
        2: "critical and competitive, argues and rarely backs down",
        3: "balanced, fair but not naive",
        4: "kind and trusting, gives the benefit of the doubt",
        5: "very warm and trusting, avoids conflict and defends others",
    },
    "neuroticism": {
        1: "unshakably calm, never rattled by accusations",
        2: "calm, keeps cool under pressure",
        3: "reacts to stress like most people",
        4: "anxious, worries and gets defensive when accused",
        5: "very anxious, panics easily and overreacts to accusations",
    },
}


def level_from_score(score: int) -> int:
    """Level (1-5) of the sum of six answers (6-30): 6-10 very low, 11-15 low, 16-20 medium, 21-25 high, 26-30 very high"""
    return min(5, max(1, (score - 1) // 5))


class BigFive(BaseModel):
    """Level (1 = very low ... 5 = very high) of each of the five traits"""
    openness: int = Field(3, ge=1, le=5)
    conscientiousness: int = Field(3, ge=1, le=5)
    extraversion: int = Field(3, ge=1, le=5)
    agreeableness: int = Field(3, ge=1, le=5)
    neuroticism: int = Field(3, ge=1, le=5)

    @classmethod
    def random(cls, rng: Optional[random.Random] = None) -> "BigFive":
        """Every trait at a random level"""
        rng = rng or random
        return cls(**{trait: rng.randint(1, 5) for trait in TRAITS})

    def levels(self) -> Dict[str, int]:
        return {trait: getattr(self, trait) for trait in TRAITS}

    def level_names(self) -> Dict[str, str]:
        """`{"openness": "high", ...}`"""
        return {trait: LEVEL_NAMES[level] for trait, level in self.levels().items()}

    def lines(self) -> List[str]:
        """One line per trait: `Extraversion: very high - very talkative, ...`"""
        return [f"{trait.capitalize()}: {LEVEL_NAMES[level]} - {BEHAVIOR[trait][level]}"
                for trait, level in self.levels().items()]

    def describe(self) -> str:
        """The full description, one trait per line (system prompt)"""
        return "\n".join(f"- {line}" for line in self.lines())

    def summary(self) -> str:
        """The description on one line (short prompts)"""
        return "; ".join(f"{LEVEL_NAMES[level]} {trait} ({BEHAVIOR[trait][level]})"
                         for trait, level in self.levels().items())


class PersonaCheck(BaseModel):
    """Result of the psychological test of one player"""
    completed: bool = False                                  # False: the model gave no usable answers
    scores: Dict[str, int] = Field(default_factory=dict)     # trait -> sum of six answers (6-30)
    measured: Dict[str, int] = Field(default_factory=dict)   # trait -> level found by the test
    flagged: List[str] = Field(default_factory=list)         # traits whose measured level differs from the assigned one

    @property
    def confirmed(self) -> bool:
        """The player behaves as described on all five traits"""
        return self.completed and not self.flagged
