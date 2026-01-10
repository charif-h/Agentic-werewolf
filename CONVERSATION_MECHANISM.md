# New Conversation Mechanism with Motivation Scores

## Overview

The new conversation mechanism implements a more realistic and dynamic discussion system where players compete to speak based on their motivation levels. This creates a more natural flow of conversation where the most motivated players speak, rather than everyone speaking in turn.

## How It Works

### 1. Player Reading Phase
Each player agent reads the current conversation as context. This includes:
- All messages in the current discussion
- Information about who spoke last
- How long since they last spoke
- The current game state and alive players

### 2. Decision & Motivation Scoring Phase
When a player decides to respond, they generate a message along with a **motivation score** from 1 to 10. The motivation score is calculated based on multiple factors:

#### Factor 2.1: Being Cited/Mentioned
- **High motivation (+3)**: Player was mentioned in the most recent message
- **Medium motivation (+1)**: Player was mentioned earlier in the conversation
- Players naturally want to respond when addressed directly

#### Factor 2.2: Argument Uniqueness
- **High motivation (+2)**: Player's argument is unique (>70% unique keywords)
- **Low motivation (-2)**: Player's argument has already been said (<30% unique)
- Encourages players to contribute new information and ideas

#### Factor 2.3: Silence Duration
- **High motivation (+2)**: Player has been silent for 5+ messages
- **Medium motivation (+1)**: Player has been silent for 3-4 messages
- **Low motivation (-1)**: Player just spoke in the previous round
- Ensures all players get chances to participate

#### Factor 2.4: Personality Influence
- **Extroverted personalities (E)**: +1 bonus (naturally more talkative)
- **Introverted personalities (I)**: -1 penalty (more reserved)
- **Judging types (J)**: +1 bonus (prefer structured discussions)
- Reflects natural communication styles

#### Factor 2.5: Role-Based Factors
- **Werewolves**: -1 (try to stay hidden and quiet)
- **Villagers**: +1 (motivated to find threats)
- **Special roles** (Seer, Witch, Guard): neutral (strategic balance)

### 3. Central Hub Collection
All players submit their proposed messages to a **ConversationHub** with their motivation scores. The hub:
- Collects all proposed messages
- Filters out "no comment" responses
- Tracks each message's motivation score

### 4. Message Selection
The hub selects which messages to publish based on the highest motivation scores:
- **Single highest score**: Only that message is published
- **Tied highest scores**: All messages with the top score are published simultaneously
- This creates natural scenarios where multiple people speak at once when equally motivated

### 5. Context Update & Loop
Once messages are published:
- They are added to the conversation history
- All players read the updated context
- The loop repeats for the next round
- Game Master can decide when to end discussion based on content quality

## Benefits of This Mechanism

1. **More Realistic Conversations**: Players don't speak in rigid turns
2. **Natural Participation**: Quiet players eventually become motivated to speak
3. **Reduces Redundancy**: Players are discouraged from repeating what's been said
4. **Personality-Driven**: Communication patterns match player personalities
5. **Role-Appropriate**: Players behave according to their game role
6. **Dynamic Interaction**: Addressing someone increases their motivation to respond

## Example Scenario

Round 1:
- Alice (Villager, ENFP): Submits "I think Bob is suspicious" (Score: 7)
- Bob (Werewolf, INTJ): Submits "Let's analyze the evidence" (Score: 4)
- Charlie (Seer, ENTJ): Silent this round (no submission)
- David (Villager, ESFJ): Submits "We need to work together" (Score: 6)

**Hub Decision**: Alice's message (score 7) is published

Round 2:
- Alice: Silent (just spoke, low motivation)
- Bob: Submits "Alice, why do you suspect me?" (Score: 8 - responding to accusation)
- Charlie: Submits "I agree with Alice" (Score: 5 - redundant argument)
- David: Submits "Bob seems defensive" (Score: 8 - unique observation)

**Hub Decision**: Both Bob and David speak (tied score of 8)

Round 3:
- Alice: Submits "Bob is deflecting!" (Score: 9 - was mentioned, defending herself)
- Bob: Silent (just spoke)
- Charlie: Submits "I've been observing everyone" (Score: 7 - long silence bonus)
- David: Silent (just spoke)

**Hub Decision**: Alice's message (score 9) is published

## Implementation Details

### Code Components

1. **ProposedMessage** (models/game_models.py)
   - Stores message content with motivation score
   - Validates score is between 1-10

2. **ConversationHub** (game/conversation_hub.py)
   - Manages message collection
   - Selects highest-scored messages
   - Filters out "no comment" responses

3. **PlayerAgent.discuss_with_motivation()** (agents/player_agent.py)
   - Generates message content
   - Calculates motivation score
   - Returns tuple of (message, score)

4. **PlayerAgent._calculate_motivation_score()** (agents/player_agent.py)
   - Implements the scoring algorithm
   - Considers all 5 factors
   - Clamps result between 1-10

5. **WerewolfGame.conduct_discussion()** (game/game_logic.py)
   - Orchestrates the hub-based discussion
   - Tracks player speech patterns
   - Publishes selected messages

### Testing

Comprehensive tests in `test_conversation_mechanism.py` verify:
- Hub message collection and selection
- Tie handling (multiple top scores)
- Motivation score calculation
- "No comment" filtering
- Hub clearing between rounds

All tests pass successfully, confirming the mechanism works as designed.

## Future Enhancements

Potential improvements to consider:
1. **Dynamic score weights**: Allow configuration of factor weights
2. **Learning patterns**: Track player behavior to adjust motivation
3. **Conversation quality**: Factor in message quality/relevance
4. **Time-based decay**: Reduce motivation if discussion drags on
5. **Urgency factor**: Increase motivation near voting phase
