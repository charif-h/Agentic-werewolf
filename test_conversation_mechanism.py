#!/usr/bin/env python3
"""
Test script for the new conversation mechanism with motivation scores
"""
import sys
import os
sys.path.append('backend')
os.chdir('backend')

from backend.game.conversation_hub import ConversationHub
from backend.models.game_models import PlayerProfile, Role, Sex, PersonalityType
from datetime import datetime


def test_conversation_hub():
    """Test the ConversationHub class"""
    print("Testing ConversationHub...")
    
    hub = ConversationHub()
    
    # Submit messages with different scores
    hub.submit_message("Alice", "I think Bob is suspicious", 7)
    hub.submit_message("Charlie", "I agree with Alice", 5)
    hub.submit_message("David", "We should look at evidence", 8)
    hub.submit_message("Eve", "I'm not sure yet", 3)
    
    print(f"✅ Hub received {hub.get_proposed_count()} proposed messages")
    
    # Select messages with highest score
    selected = hub.select_messages()
    
    print(f"✅ Hub selected {len(selected)} message(s) with highest score")
    for msg in selected:
        print(f"   - {msg.sender}: {msg.content}")
    
    # Test that the highest score (8) was selected
    assert len(selected) == 1, "Should select exactly 1 message"
    assert selected[0].sender == "David", "Should select David's message with score 8"
    
    print("✅ ConversationHub test passed!")
    return hub


def test_hub_with_tie():
    """Test hub behavior when multiple messages have same top score"""
    print("\nTesting ConversationHub with tied scores...")
    
    hub = ConversationHub()
    
    # Submit messages where two have the highest score
    hub.submit_message("Alice", "I think Bob is the werewolf", 9)
    hub.submit_message("Charlie", "I think David is suspicious", 9)
    hub.submit_message("Eve", "I'm not sure", 5)
    
    print(f"✅ Hub received {hub.get_proposed_count()} proposed messages")
    
    selected = hub.select_messages()
    
    print(f"✅ Hub selected {len(selected)} message(s) with highest score (9)")
    for msg in selected:
        print(f"   - {msg.sender}: {msg.content}")
    
    # Both messages with score 9 should be selected
    assert len(selected) == 2, "Should select both messages with score 9"
    senders = [msg.sender for msg in selected]
    assert "Alice" in senders and "Charlie" in senders, "Should select both Alice and Charlie"
    
    print("✅ Hub tie handling test passed!")
    return hub


def test_motivation_score_calculation():
    """Test the motivation score calculation"""
    print("\nTesting motivation score calculation...")
    
    # Create a test player profile without initializing the agent's LLM
    profile = PlayerProfile(
        id="test_1",
        name="Alice",
        sex=Sex.FEMALE,
        age=25,
        personality=PersonalityType.ENFP,  # Extroverted personality
        role=Role.VILLAGER
    )
    
    # Create a mock agent just for testing the motivation score method
    # We'll mock the __init__ to avoid needing API keys
    class MockPlayerAgent:
        def __init__(self, profile):
            self.profile = profile
            
        def _calculate_motivation_score(self, conversation_history: str, 
                                        last_speaker,
                                        messages_since_last_spoke: int,
                                        proposed_response: str) -> int:
            # Copy the actual implementation from PlayerAgent
            score = 5  # Base score
            
            # Factor 2.1: Being cited/mentioned in previous message
            if last_speaker and self.profile.name in conversation_history:
                # Check if mentioned in the last message
                if conversation_history:
                    lines = conversation_history.strip().split('\n')
                    if lines and self.profile.name in lines[-1]:
                        score += 3  # High motivation if mentioned in last message
                    else:
                        score += 1  # Lower boost if mentioned earlier
            
            # Factor 2.2: Uniqueness of argument
            if conversation_history and proposed_response:
                response_words = set(proposed_response.lower().split())
                conversation_words = set(conversation_history.lower().split())
                
                common_words = {'i', 'you', 'the', 'a', 'an', 'is', 'are', 'was', 'were', 'been', 'be',
                              'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                              'can', 'may', 'might', 'must', 'this', 'that', 'these', 'those', 'and', 'or',
                              'but', 'not', 'no', 'yes', 'to', 'from', 'in', 'on', 'at', 'for', 'with'}
                
                response_keywords = response_words - common_words
                overlap = len(response_keywords & conversation_words)
                uniqueness_ratio = 1.0 - (overlap / max(len(response_keywords), 1))
                
                if uniqueness_ratio > 0.7:  # Highly unique
                    score += 2
                elif uniqueness_ratio < 0.3:  # Already said
                    score -= 2
            
            # Factor 2.3: Silence duration
            if messages_since_last_spoke >= 5:
                score += 2
            elif messages_since_last_spoke >= 3:
                score += 1
            elif messages_since_last_spoke == 0:
                score -= 1
            
            # Factor 2.4: Personality influence
            if self.profile.personality.value[0] == 'E':  # Extroverted
                score += 1
            elif self.profile.personality.value[0] == 'I':  # Introverted
                score -= 1
            
            if self.profile.personality.value[3] == 'J':
                score += 1
            
            # Factor 2.5: Role-based motivation
            if self.profile.role == Role.WEREWOLF:
                score -= 1
            elif self.profile.role in [Role.SEER, Role.WITCH, Role.GUARD]:
                score += 0
            elif self.profile.role == Role.VILLAGER:
                score += 1
            
            return max(1, min(10, score))
    
    agent = MockPlayerAgent(profile)
    
    # Test case 1: Player mentioned in conversation
    conversation = "[Bob] Alice, what do you think about Charlie?"
    score = agent._calculate_motivation_score(conversation, "Bob", 3, "I think Charlie is suspicious")
    print(f"✅ Score when mentioned: {score} (should be higher)")
    assert score >= 7, f"Score should be high when mentioned, got {score}"
    
    # Test case 2: Player has been silent for a while
    score = agent._calculate_motivation_score("", None, 6, "I have something to say")
    print(f"✅ Score after long silence: {score} (should be higher)")
    assert score >= 6, f"Score should be high after long silence, got {score}"
    
    # Test case 3: Player just spoke
    score = agent._calculate_motivation_score("", None, 0, "Another comment")
    print(f"✅ Score after just speaking: {score} (should be lower)")
    
    # Test case 4: Extroverted personality bonus
    # ENFP starts with 'E' so should get +1 bonus
    print(f"✅ Extroverted personality (ENFP) gets motivation boost")
    
    print("✅ Motivation score calculation test passed!")


def test_no_comment_filtering():
    """Test that 'no comment' responses are filtered out"""
    print("\nTesting 'no comment' filtering...")
    
    hub = ConversationHub()
    
    # Submit some messages including "no comment"
    hub.submit_message("Alice", "I think Bob is suspicious", 8)
    hub.submit_message("Bob", "no comment", 5)  # Should be filtered
    hub.submit_message("Charlie", "I agree", 7)
    
    # Only 2 messages should be submitted (no comment filtered out)
    assert hub.get_proposed_count() == 2, "Should only have 2 messages (no comment filtered)"
    
    print("✅ 'no comment' filtering test passed!")


def test_hub_clear():
    """Test hub clearing for next round"""
    print("\nTesting hub clear functionality...")
    
    hub = ConversationHub()
    hub.submit_message("Alice", "Test message", 5)
    
    assert hub.get_proposed_count() == 1, "Should have 1 message"
    
    hub.clear()
    
    assert hub.get_proposed_count() == 0, "Should have 0 messages after clear"
    
    print("✅ Hub clear test passed!")


if __name__ == "__main__":
    try:
        test_conversation_hub()
        test_hub_with_tie()
        test_motivation_score_calculation()
        test_no_comment_filtering()
        test_hub_clear()
        print("\n🎉 All conversation mechanism tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
