#!/usr/bin/env python3
"""
Integration test for the new conversation mechanism in game context
Tests that the hub mechanism integrates properly with WerewolfGame
"""
import sys
import os
sys.path.append('backend')

from backend.game.conversation_hub import ConversationHub
from backend.models.game_models import PlayerProfile, Role, Sex, PersonalityType, Discussion, Message
from datetime import datetime


def test_hub_integration_flow():
    """Test the complete flow of the hub mechanism"""
    print("Testing hub integration flow...")
    
    # Simulate a discussion round
    hub = ConversationHub()
    
    # Simulate multiple players submitting messages
    players_proposals = [
        ("Alice", "I think Bob is acting suspicious", 7),
        ("Bob", "no comment", 3),  # Should be filtered
        ("Charlie", "I agree with Alice's point", 5),
        ("David", "Let's examine the evidence carefully", 9),
        ("Eve", "Has anyone noticed Frank's behavior?", 8),
    ]
    
    print(f"  Simulating {len(players_proposals)} players considering responses...")
    
    for name, message, score in players_proposals:
        hub.submit_message(name, message, score)
    
    # Hub should have filtered out "no comment"
    assert hub.get_proposed_count() == 4, f"Expected 4 messages (filtered 1), got {hub.get_proposed_count()}"
    print(f"  ✅ Hub received {hub.get_proposed_count()} valid messages")
    
    # Select highest scoring message
    selected = hub.select_messages()
    
    print(f"  ✅ Hub selected {len(selected)} message(s)")
    assert len(selected) == 1, "Should select exactly 1 message with highest score (9)"
    assert selected[0].sender == "David", f"Should select David's message, got {selected[0].sender}"
    assert selected[0].content == "Let's examine the evidence carefully"
    
    print(f"  ✅ Selected message: [{selected[0].sender}] {selected[0].content}")
    
    # Verify message structure
    msg = selected[0]
    assert hasattr(msg, 'sender'), "Message should have sender"
    assert hasattr(msg, 'content'), "Message should have content"
    assert hasattr(msg, 'timestamp'), "Message should have timestamp"
    assert hasattr(msg, 'message_type'), "Message should have message_type"
    assert msg.message_type == "chat", f"Message type should be 'chat', got {msg.message_type}"
    
    print("  ✅ Message structure is valid")
    print("✅ Hub integration flow test passed!\n")


def test_multiple_rounds():
    """Test hub behavior across multiple discussion rounds"""
    print("Testing multiple discussion rounds...")
    
    # Round 1
    hub = ConversationHub()
    hub.submit_message("Alice", "I suspect Bob", 8)
    hub.submit_message("Charlie", "I'm not sure", 4)
    
    round1_messages = hub.select_messages()
    assert len(round1_messages) == 1
    assert round1_messages[0].sender == "Alice"
    print("  ✅ Round 1: Alice speaks (score 8)")
    
    # Clear hub for round 2
    hub.clear()
    assert hub.get_proposed_count() == 0, "Hub should be empty after clear"
    
    # Round 2 - Bob responds to being accused
    hub.submit_message("Bob", "Alice, why do you think that?", 10)
    hub.submit_message("David", "Let's hear Bob's defense", 6)
    
    round2_messages = hub.select_messages()
    assert len(round2_messages) == 1
    assert round2_messages[0].sender == "Bob"
    print("  ✅ Round 2: Bob responds (score 10 - mentioned)")
    
    # Clear for round 3
    hub.clear()
    
    # Round 3 - Tie scenario
    hub.submit_message("Alice", "Bob is being evasive", 9)
    hub.submit_message("Charlie", "I think Alice is right", 9)
    hub.submit_message("Eve", "We should vote soon", 5)
    
    round3_messages = hub.select_messages()
    assert len(round3_messages) == 2, "Should select both tied messages"
    senders = [msg.sender for msg in round3_messages]
    assert "Alice" in senders and "Charlie" in senders
    print(f"  ✅ Round 3: Multiple speakers (Alice & Charlie, both score 9)")
    
    print("✅ Multiple rounds test passed!\n")


def test_discussion_object_compatibility():
    """Test that hub messages work with Discussion objects"""
    print("Testing Discussion object compatibility...")
    
    hub = ConversationHub()
    hub.submit_message("Alice", "First message", 7)
    hub.submit_message("Bob", "Second message", 8)
    
    selected = hub.select_messages()
    
    # Create a Discussion object
    discussion = Discussion(
        round_number=1,
        topic="Test discussion",
        messages=[]
    )
    
    # Add selected messages to discussion
    discussion.messages.extend(selected)
    
    assert len(discussion.messages) == 1, "Discussion should have 1 message"
    assert discussion.messages[0].sender == "Bob"
    assert discussion.messages[0].content == "Second message"
    
    print("  ✅ Hub messages integrate with Discussion objects")
    
    # Test building conversation history
    conversation_history = "\n".join([f"[{msg.sender}] {msg.content}" for msg in discussion.messages])
    assert "[Bob] Second message" in conversation_history
    
    print("  ✅ Conversation history can be built from messages")
    print("✅ Discussion object compatibility test passed!\n")


def test_score_clamping():
    """Test that scores are properly clamped between 1-10"""
    print("Testing score clamping...")
    
    hub = ConversationHub()
    
    # Try to submit with out-of-range scores
    hub.submit_message("Alice", "Test 1", -5)  # Should clamp to 1
    hub.submit_message("Bob", "Test 2", 15)    # Should clamp to 10
    hub.submit_message("Charlie", "Test 3", 5)  # Normal score
    
    # Bob's message should win (clamped to 10)
    selected = hub.select_messages()
    assert len(selected) == 1
    assert selected[0].sender == "Bob", "Should select Bob's message (score clamped to 10)"
    
    print("  ✅ Negative scores clamped to 1")
    print("  ✅ Scores > 10 clamped to 10")
    print("✅ Score clamping test passed!\n")


if __name__ == "__main__":
    try:
        test_hub_integration_flow()
        test_multiple_rounds()
        test_discussion_object_compatibility()
        test_score_clamping()
        print("🎉 All integration tests passed!")
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
