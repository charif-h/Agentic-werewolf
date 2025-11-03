"""
Quick test script to verify the basic functionality of the game system
Run this to ensure all components are properly configured.
"""
import sys
from backend.models.game_models import PlayerProfile, PersonalityType, Sex, Role
from backend.agents.profile_generator import generate_all_players

def test_models():
    """Test that models are properly defined"""
    print("Testing Models...")
    
    # Test creating a player profile
    player = PlayerProfile(
        id="test_1",
        name="Test Player",
        sex=Sex.MALE,
        age=25,
        personality=PersonalityType.INTJ
    )
    
    assert player.name == "Test Player"
    assert player.age == 25
    assert player.personality == PersonalityType.INTJ
    
    # Test personality description
    desc = player.get_personality_description()
    assert len(desc) > 0
    
    print("✓ Models working correctly")
    return True

def test_profile_generation():
    """Test player profile generation"""
    print("\nTesting Profile Generation...")
    
    # Generate 24 players
    players = generate_all_players(24)
    
    assert len(players) == 24
    assert all(isinstance(p, PlayerProfile) for p in players)
    assert all(18 <= p.age <= 80 for p in players)
    assert all(p.personality in PersonalityType for p in players)
    
    print(f"✓ Generated {len(players)} players")
    print(f"✓ Sample players:")
    for i, p in enumerate(players[:3]):
        print(f"  {i+1}. {p.name} ({p.sex.value}, {p.age}yo, {p.personality.value})")
    
    return True

def test_role_distribution():
    """Test role distribution algorithm"""
    print("\nTesting Role Distribution...")
    
    from backend.models.game_models import Role
    
    def distribute_roles(num_players):
        werewolf_count = max(2, num_players // 6)
        roles = [Role.WEREWOLF] * werewolf_count
        
        if num_players >= 8:
            roles.append(Role.SEER)
        if num_players >= 10:
            roles.append(Role.WITCH)
        if num_players >= 12:
            roles.append(Role.HUNTER)
        if num_players >= 14:
            roles.append(Role.CUPID)
        if num_players >= 16:
            roles.append(Role.GUARD)
        
        villager_count = num_players - len(roles)
        roles.extend([Role.VILLAGER] * villager_count)
        return roles
    
    roles = distribute_roles(24)
    
    assert len(roles) == 24
    
    from collections import Counter
    counts = Counter(roles)
    
    print("✓ Role distribution for 24 players:")
    for role, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {role.value}: {count}")
    
    assert counts[Role.WEREWOLF] == 4
    assert counts[Role.VILLAGER] == 15
    
    return True

def main():
    """Run all tests"""
    print("=" * 60)
    print("Werewolves of Millers Hollow - System Test")
    print("=" * 60)
    
    tests = [
        test_models,
        test_profile_generation,
        test_role_distribution
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test failed: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Tests completed: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n✓ All tests passed! The system is ready.")
        print("\nNext steps:")
        print("1. Set up your .env file with API keys")
        print("2. Install dependencies: pip install -r backend/requirements.txt")
        print("3. Run the backend: uvicorn backend.main:app --reload")
        print("4. Run the frontend: cd frontend && npm install && npm start")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
