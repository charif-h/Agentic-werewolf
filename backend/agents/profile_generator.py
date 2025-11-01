"""
Player profile generator with random attributes
"""
import random
from backend.models.game_models import PlayerProfile, PersonalityType, Sex


# Lists of names for variety
MALE_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark", "Donald",
    "Steven", "Paul", "Andrew", "Joshua", "Kenneth", "Kevin", "Brian", "George", "Amin",
    "Samuel", "Ethan", "Jacob", "Ryan", "Nathan", "Caleb", "Dylan", "Luke", "Gabriel", 
    "Bassam", "Omar", "Hassan", "Yusuf", "Ibrahim", "Zayd", "Tariq", "Khalid", "Rami",
    "Adnan", "Faris", "Jamal", "Nabil", "Sami", "Amir", "Bilal", "Hadi", "Chan"
]

NON_BINARY_NAMES = [
    "Alex", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Avery", "Quinn",
    "Dakota", "Skylar", "Parker", "Cameron", "River", "Phoenix", "Sage", "Rowan",
    "Drew", "Blake", "Jamie", "Pat", "Sam", "Chris", "Robin", "Ash", "Lou"
]

FEMALE_NAMES = [
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica",
    "Sarah", "Karen", "Nancy", "Lisa", "Betty", "Margaret", "Sandra", "Ashley",
    "Dorothy", "Kimberly", "Emily", "Donna", "Michelle", "Carol", "Amanda", "Melissa",
    "Alice", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia", "Harper", "Evelyn",
    "Layla", "Zoe", "Aaliyah", "Fatima", "Noor", "Yasmin", "Lina", "Maya", "Sara",
    "Hana", "Rania", "Dina", "Salma", "Nadia", "Laila", "Jana", "Reem", "Dana"
]



def generate_player_profile(player_id: str, used_names: set) -> PlayerProfile:
    """
    Generate a random player profile with name, sex, age, and personality
    
    Args:
        player_id: Unique identifier for the player
        used_names: Set of already used names to avoid duplicates
        
    Returns:
        PlayerProfile with randomly generated attributes
    """
    # Randomly select sex
    sex = random.choice(list(Sex))
    
    # Select appropriate name based on sex, ensuring uniqueness
    available_names = []
    if sex == Sex.MALE:
        available_names = [name for name in MALE_NAMES if name not in used_names]
    elif sex == Sex.FEMALE:
        available_names = [name for name in FEMALE_NAMES if name not in used_names]
    else:
        available_names = [name for name in NON_BINARY_NAMES if name not in used_names]
    
    # If no available names for this sex, try other categories
    if not available_names:
        all_names = MALE_NAMES + FEMALE_NAMES + NON_BINARY_NAMES
        available_names = [name for name in all_names if name not in used_names]
    
    # If still no available names, add suffix
    if not available_names:
        if sex == Sex.MALE:
            base_name = random.choice(MALE_NAMES)
        elif sex == Sex.FEMALE:
            base_name = random.choice(FEMALE_NAMES)
        else:
            base_name = random.choice(NON_BINARY_NAMES)
        
        # Add suffix until unique
        counter = 1
        name = f"{base_name}{counter}"
        while name in used_names:
            counter += 1
            name = f"{base_name}{counter}"
    else:
        name = random.choice(available_names)
    
    # Add name to used set
    used_names.add(name)
    
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


def generate_all_players(num_players: int = 5) -> list[PlayerProfile]:
    """
    Generate a list of unique player profiles
    
    Args:
        num_players: Number of players to generate (default: 5)
        
    Returns:
        List of PlayerProfile objects with unique names
    """
    players = []
    used_names = set()
    
    for i in range(num_players):
        player_id = f"player_{i+1}"
        player = generate_player_profile(player_id, used_names)
        players.append(player)
    
    return players
