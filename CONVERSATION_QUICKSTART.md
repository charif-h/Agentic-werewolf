# New Conversation Mechanism - Quick Start Guide

## What's New?

The game now uses a **motivation-based conversation system** instead of turn-based speaking. Players compete to speak based on how motivated they are to respond, creating more realistic and dynamic discussions.

## How It Works (Simple Version)

1. **Players read the conversation** - Everyone sees what's been said
2. **Players decide if they want to speak** - Each calculates their motivation (1-10)
3. **The hub picks the most motivated** - Highest score(s) get to speak
4. **Message(s) are added to conversation** - Others see it and the cycle repeats

## What Affects Motivation?

Your motivation to speak is a score from 1-10 based on:

| Factor | Effect | Example |
|--------|--------|---------|
| **Being mentioned** | +3 if in last message<br>+1 if earlier | "Alice, what do you think?" → Alice gets +3 |
| **Unique argument** | +2 if new idea<br>-2 if already said | Repeating someone lowers your score |
| **Silence** | +2 if quiet 5+ messages<br>-1 if just spoke | Quiet players get motivated to speak |
| **Personality** | Extroverts: +1<br>Introverts: -1 | ENFP speaks more than INTJ |
| **Role** | Werewolves: -1<br>Villagers: +1 | Werewolves stay quiet, villagers speak up |

## Example

```
Round 1:
  Alice (Villager): "I think Bob is suspicious" → Score: 7
  Bob (Werewolf): stays quiet → Score: 0
  Charlie (Villager): "I agree with Alice" → Score: 5 (redundant)
  
  Winner: Alice speaks (score 7)

Round 2 (after Alice's message):
  Alice: stays quiet (just spoke) → Score: 4
  Bob: "Alice, why do you think that?" → Score: 10 (mentioned!)
  Charlie: "We need evidence" → Score: 7
  
  Winner: Bob speaks (score 10)

Round 3:
  Alice: "Bob is deflecting!" → Score: 9 (defending herself)
  Bob: stays quiet (just spoke) → Score: 3
  Charlie: "Alice makes a good point" → Score: 9 (long silence bonus)
  
  Winner: TIE! Both Alice and Charlie speak
```

## What This Means for the Game

✅ **More realistic** - Not everyone speaks in rigid order
✅ **Natural flow** - People respond when addressed
✅ **Less repetition** - Saying the same thing gives low motivation
✅ **Personality matters** - Extroverts talk more, introverts less
✅ **Role-appropriate** - Werewolves hide, villagers investigate
✅ **Dynamic** - Quiet players eventually get their turn

## For Developers

### Using the New System

```python
# Old way (still works for backward compatibility)
response = player_agent.discuss(conversation_history, alive_players)

# New way (returns message and motivation score)
message, score = player_agent.discuss_with_motivation(
    conversation_history,
    alive_players,
    last_speaker="Bob",
    messages_since_last_spoke=3
)
```

### The Hub Mechanism

```python
from backend.game.conversation_hub import ConversationHub

# Create hub for a discussion round
hub = ConversationHub()

# Players submit messages
hub.submit_message("Alice", "I suspect Bob", motivation_score=8)
hub.submit_message("Charlie", "I'm not sure", motivation_score=5)

# Get highest-scored message(s)
selected = hub.select_messages()  # Returns [Alice's message]

# Clear for next round
hub.clear()
```

## Documentation

For more details, see:
- **[CONVERSATION_MECHANISM.md](CONVERSATION_MECHANISM.md)** - Detailed explanation
- **[CONVERSATION_FLOW_DIAGRAM.md](CONVERSATION_FLOW_DIAGRAM.md)** - Visual flow chart
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Technical summary

## Testing

Run the tests to verify everything works:

```bash
# Unit tests for the hub and scoring
python test_conversation_mechanism.py

# Integration tests
python test_hub_integration.py

# Verify backward compatibility
python test_discussions.py
```

All tests should pass ✅

## Questions?

**Q: Will everyone still get to speak?**  
A: Yes! The silence duration factor ensures quiet players eventually become highly motivated to speak.

**Q: What if two players have the same score?**  
A: Both messages are published! This creates a natural "talking over each other" effect.

**Q: Can werewolves still participate?**  
A: Yes, but they get a -1 penalty to stay more hidden. They can still speak if they have other motivation factors.

**Q: Is this backward compatible?**  
A: Yes! The old `discuss()` method still exists and works the same way.

## Summary

The new conversation mechanism makes discussions more realistic and engaging by letting motivation drive who speaks, rather than just taking turns. Players naturally respond when addressed, contribute unique ideas, and behave according to their personality and role.

**Result:** More dynamic, realistic, and fun gameplay! 🎮
