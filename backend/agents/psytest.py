"""
Psychological test that checks a player behaves as their Big Five description says

The player answers 30 statements (six per trait, some reverse-scored) as the character
they were given. The sums are turned into levels and compared with the assigned
levels; a trait that differs is flagged. A flagged player still plays: the flag tells
the developer that the description in the prompt did not make the model act as intended.
"""
from typing import Dict, List, Optional, Sequence

from backend.models.personality import TRAITS, BigFive, PersonaCheck, level_from_score

# (trait, statement, reverse-scored)
ITEMS = [
    ("openness", "I have a vivid imagination.", False),
    ("openness", "I enjoy thinking about abstract ideas and theories.", False),
    ("openness", "I seek out new experiences, foods and places.", False),
    ("openness", "I prefer routines to trying new things.", True),
    ("openness", "I'm not very interested in art, music or literature.", True),
    ("openness", "I find philosophical discussions boring.", True),
    ("conscientiousness", "I keep my belongings and workspace organized.", False),
    ("conscientiousness", "I finish tasks before relaxing.", False),
    ("conscientiousness", "I plan ahead and stick to my plans.", False),
    ("conscientiousness", "I often forget to put things back where they belong.", True),
    ("conscientiousness", "I tend to procrastinate on important tasks.", True),
    ("conscientiousness", "I sometimes act without thinking through the consequences.", True),
    ("extraversion", "I feel comfortable around people, including strangers.", False),
    ("extraversion", "I'm usually the one who starts conversations.", False),
    ("extraversion", "I feel energized after spending time with a group.", False),
    ("extraversion", "I prefer to stay in the background.", True),
    ("extraversion", "I don't talk much in social situations.", True),
    ("extraversion", "I need a lot of time alone to recharge.", True),
    ("agreeableness", "I sympathize with other people's feelings.", False),
    ("agreeableness", "I make people feel at ease.", False),
    ("agreeableness", "I generally trust that people have good intentions.", False),
    ("agreeableness", "I'm not very interested in other people's problems.", True),
    ("agreeableness", "I can be critical or harsh with others.", True),
    ("agreeableness", "I put my own interests ahead of others' most of the time.", True),
    ("neuroticism", "I worry about things a lot.", False),
    ("neuroticism", "I get stressed out easily.", False),
    ("neuroticism", "My mood changes frequently.", False),
    ("neuroticism", "I often feel anxious or tense.", False),
    ("neuroticism", "I stay calm in difficult situations.", True),
    ("neuroticism", "I rarely feel sad or down.", True),
]


def statements() -> List[str]:
    """The statements in the order the answers are expected (the player is not told which are reverse-scored)"""
    return [text for _, text, _ in ITEMS]


def score(answers: Sequence[int]) -> Dict[str, int]:
    """Sum of the six answers of each trait (6-30), reverse-scored items counting 6 minus the answer"""
    totals = {trait: 0 for trait in TRAITS}
    for (trait, _, reverse), answer in zip(ITEMS, answers):
        totals[trait] += 6 - answer if reverse else answer
    return totals


def evaluate(answers: Optional[Sequence[int]], expected: BigFive) -> PersonaCheck:
    """
    Compare the levels found by the test with the assigned ones

    `answers` is None (or not 30 values of 1-5) when the model gave no usable answers: the
    check is then not completed and nothing is flagged.
    """
    if answers is None or len(answers) != len(ITEMS) or not all(1 <= a <= 5 for a in answers):
        return PersonaCheck(completed=False)
    scores = score(answers)
    measured = {trait: level_from_score(total) for trait, total in scores.items()}
    assigned = expected.levels()
    return PersonaCheck(completed=True, scores=scores, measured=measured,
                        flagged=[trait for trait in TRAITS if measured[trait] != assigned[trait]])
