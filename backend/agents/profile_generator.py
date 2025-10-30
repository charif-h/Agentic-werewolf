"""
Player profile generator with random attributes
"""
import random
from backend.models.game_models import PlayerProfile, PersonalityType, Sex


# Lists of names for variety
MALE_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald",
    "Steven", "Paul", "Andrew", "Joshua", "Kenneth", "Kevin", "Brian", "George"
]

FEMALE_NAMES = [
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica",
    "Sarah", "Karen", "Nancy", "Lisa", "Betty", "Margaret", "Sandra", "Ashley",
    "Dorothy", "Kimberly", "Emily", "Donna", "Michelle", "Carol", "Amanda", "Melissa"
]

NON_BINARY_NAMES = [
    "Alex", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Avery", "Quinn",
    "Dakota", "Skylar", "Parker", "Cameron", "River", "Phoenix", "Sage", "Rowan"
]


def generate_player_profile(player_id: str) -> PlayerProfile:
    """
    Generate a random player profile with name, sex, age, and personality
    
    Args:
        player_id: Unique identifier for the player
        
    Returns:
        PlayerProfile with randomly generated attributes
    """
    # Randomly select sex
    sex = random.choice(list(Sex))
    
    # Select appropriate name based on sex
    if sex == Sex.MALE:
        name = random.choice(MALE_NAMES)
    elif sex == Sex.FEMALE:
        name = random.choice(FEMALE_NAMES)
    else:
        name = random.choice(NON_BINARY_NAMES)
    
    # Generate random age between 18 and 80
    age = random.randint(18, 80)
    
    # Randomly assign one of the 16 personality types
    personality = random.choice(list(PersonalityType))
    
    return PlayerProfile(
        id=player_id,
        name=name,
        sex=sex,
        age=age,
        personality=personality
    )


def generate_all_players(num_players: int = 24) -> list[PlayerProfile]:
    """
    Generate all player profiles for the game
    
    Args:
        num_players: Number of players to generate (default 24)
        
    Returns:
        List of PlayerProfile objects
    """
    players = []
    for i in range(num_players):
        player_id = f"player_{i+1}"
        profile = generate_player_profile(player_id)
        players.append(profile)
    
    return players
