# Conversation Mechanism Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DISCUSSION ROUND N                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Players Read Context                                            │
│                                                                          │
│  Current Conversation:                                                   │
│  [Alice] I think Bob is acting suspicious                               │
│  [Bob] That's not true! I'm investigating.                              │
│                                                                          │
│  Each Player Receives:                                                   │
│  • Full conversation history                                             │
│  • Who spoke last (Bob)                                                  │
│  • Messages since they last spoke                                        │
│  • List of alive players                                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Players Decide & Calculate Motivation                           │
│                                                                          │
│  Charlie (Villager, ENFP):                                              │
│  • Message: "I agree with Alice's observation"                          │
│  • Motivation Calculation:                                               │
│    Base: 5                                                               │
│    + Not mentioned: 0                                                    │
│    + Argument not unique (agrees with Alice): -2                         │
│    + Silent for 2 messages: 0                                            │
│    + Extroverted (E): +1                                                 │
│    + Villager role: +1                                                   │
│  • Final Score: 5                                                        │
│                                                                          │
│  David (Seer, INTJ):                                                    │
│  • Message: "Let's examine the facts systematically"                    │
│  • Motivation Calculation:                                               │
│    Base: 5                                                               │
│    + Not mentioned: 0                                                    │
│    + Unique argument: +2                                                 │
│    + Silent for 5 messages: +2                                           │
│    + Introverted (I): -1                                                 │
│    + Judging (J): +1                                                     │
│    + Seer role: 0                                                        │
│  • Final Score: 9                                                        │
│                                                                          │
│  Eve (Werewolf, ESTP):                                                  │
│  • Message: "no comment" (staying quiet)                                │
│  • Score: 0 (filtered out)                                               │
│                                                                          │
│  Frank (Villager, ISFJ):                                                │
│  • Message: "We should trust each other"                                │
│  • Motivation Calculation:                                               │
│    Base: 5                                                               │
│    + Not mentioned: 0                                                    │
│    + Somewhat unique: +1                                                 │
│    + Just spoke: -1                                                      │
│    + Introverted (I): -1                                                 │
│    + Villager role: +1                                                   │
│  • Final Score: 5                                                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Hub Collects Messages                                           │
│                                                                          │
│  ConversationHub receives:                                               │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ Sender: Charlie | Score: 5 | "I agree with Alice's..."  │           │
│  ├──────────────────────────────────────────────────────────┤           │
│  │ Sender: David   | Score: 9 | "Let's examine the facts..." │         │
│  ├──────────────────────────────────────────────────────────┤           │
│  │ Sender: Frank   | Score: 5 | "We should trust each..."  │           │
│  └──────────────────────────────────────────────────────────┘           │
│                                                                          │
│  Note: Eve's "no comment" was filtered out                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Hub Selects Highest Score                                       │
│                                                                          │
│  Maximum score: 9                                                        │
│  Messages with score 9: 1 (David)                                        │
│                                                                          │
│  Selected for publication:                                               │
│  ┌──────────────────────────────────────────────────────────┐           │
│  │ [David] Let's examine the facts systematically           │           │
│  └──────────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ STEP 5: Message Published to Conversation                               │
│                                                                          │
│  Updated Conversation:                                                   │
│  [Alice] I think Bob is acting suspicious                               │
│  [Bob] That's not true! I'm investigating.                              │
│  [David] Let's examine the facts systematically                         │
│                                                                          │
│  This becomes the new context for Round N+1                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↓
                         Loop Continues to Next Round


═══════════════════════════════════════════════════════════════════════════

SPECIAL CASE: Tied Scores
═══════════════════════════════════════════════════════════════════════════

If in Step 4, two players have the same highest score:

  Maximum score: 8
  Messages with score 8: 2 (Alice and Grace)
  
  Selected for publication:
  ┌──────────────────────────────────────────────────────────┐
  │ [Alice] Bob is deflecting the question!                  │
  │ [Grace] We need to vote on someone today.                │
  └──────────────────────────────────────────────────────────┘
  
  Both messages are published simultaneously
  This creates a natural "people talking over each other" effect


═══════════════════════════════════════════════════════════════════════════

MOTIVATION SCORE FACTORS SUMMARY
═══════════════════════════════════════════════════════════════════════════

Factor 1: Being Mentioned
  ┌─────────────────────────────────────┬────────┐
  │ Mentioned in last message           │  +3    │
  │ Mentioned earlier in conversation   │  +1    │
  │ Not mentioned                        │   0    │
  └─────────────────────────────────────┴────────┘

Factor 2: Argument Uniqueness
  ┌─────────────────────────────────────┬────────┐
  │ >70% unique keywords                │  +2    │
  │ 30-70% unique                        │   0    │
  │ <30% unique (redundant)             │  -2    │
  └─────────────────────────────────────┴────────┘

Factor 3: Silence Duration
  ┌─────────────────────────────────────┬────────┐
  │ 5+ messages since last spoke        │  +2    │
  │ 3-4 messages since last spoke       │  +1    │
  │ 1-2 messages since last spoke       │   0    │
  │ Just spoke (0 messages)             │  -1    │
  └─────────────────────────────────────┴────────┘

Factor 4: Personality
  ┌─────────────────────────────────────┬────────┐
  │ Extroverted (E)                     │  +1    │
  │ Introverted (I)                     │  -1    │
  │ Judging (J)                         │  +1    │
  └─────────────────────────────────────┴────────┘

Factor 5: Role
  ┌─────────────────────────────────────┬────────┐
  │ Werewolf (trying to hide)           │  -1    │
  │ Villager (finding threats)          │  +1    │
  │ Special roles (Seer, Witch, Guard)  │   0    │
  └─────────────────────────────────────┴────────┘

Final Score: Clamped between 1 and 10
```
