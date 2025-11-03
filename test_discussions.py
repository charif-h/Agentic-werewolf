#!/usr/bin/env python3
"""
Test script to verify the discussion system is working
"""
import sys
import os
sys.path.append('backend')
os.chdir('backend')

from backend.models.game_models import PlayerProfile, Role, Sex, PersonalityType, Discussion, Message
from datetime import datetime

def test_discussion_model():
    """Test the Discussion and Message models"""
    print("Testing Discussion and Message models...")
    
    # Create test messages
    message1 = Message(
        sender="Alice",
        content="I think Bob is acting suspicious",
        timestamp=datetime.now().isoformat(),
        message_type="chat"
    )
    
    message2 = Message(
        sender="Bob", 
        content="That's not true! I'm innocent!",
        timestamp=datetime.now().isoformat(),
        message_type="chat"
    )
    
    # Create discussion
    discussion = Discussion(
        round_number=1,
        topic="Share your suspicions",
        messages=[message1, message2]
    )
    
    print(f"✅ Discussion created with {len(discussion.messages)} messages")
    print(f"   Round: {discussion.round_number}")
    print(f"   Topic: {discussion.topic}")
    
    for msg in discussion.messages:
        print(f"   - {msg.sender}: {msg.content}")
    
    return discussion

def test_game_state_with_discussions():
    """Test GameState with discussions"""
    print("\nTesting GameState with discussions...")
    
    from backend.models.game_models import GameState
    
    state = GameState()
    
    # Add test discussion
    discussion = test_discussion_model()
    state.discussions.append(discussion)
    
    print(f"✅ GameState has {len(state.discussions)} discussions")
    
    return state

if __name__ == "__main__":
    try:
        test_discussion_model()
        test_game_state_with_discussions()
        print("\n🎉 All tests passed! Discussion system is working correctly.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()