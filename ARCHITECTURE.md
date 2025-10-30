# Architecture Overview

## System Design

The Agentic Werewolf application follows a modern client-server architecture with AI-powered agents.

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Game Board  │  │ Player Cards │  │  Game Log    │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP/WebSocket
                         ▼
┌─────────────────────────────────────────────────────────┐
│               Backend (FastAPI + Python)                │
│  ┌──────────────────────────────────────────────────┐  │
│  │              Game Controller                      │  │
│  │  - Game state management                         │  │
│  │  - Phase transitions                             │  │
│  │  - Rule enforcement                              │  │
│  └──────────────────┬───────────────────────────────┘  │
│                     │                                   │
│  ┌──────────────────┴───────────────────────────────┐  │
│  │           Agent Orchestration Layer              │  │
│  │                                                   │  │
│  │  ┌───────────────┐    ┌────────────────────────┐ │  │
│  │  │ Game Master   │    │  24 Player Agents      │ │  │
│  │  │  - Narration  │    │  - Decision making     │ │  │
│  │  │  - Moderation │    │  - Personality-driven  │ │  │
│  │  │  - Rules      │    │  - Role-based actions  │ │  │
│  │  └───────┬───────┘    └──────────┬─────────────┘ │  │
│  │          │                       │                │  │
│  │          └───────────┬───────────┘                │  │
│  │                      ▼                            │  │
│  │           ┌────────────────────┐                  │  │
│  │           │   AI Provider      │                  │  │
│  │           │   (LangChain)      │                  │  │
│  │           └─────────┬──────────┘                  │  │
│  └─────────────────────┼────────────────────────────┘  │
└────────────────────────┼────────────────────────────────┘
                         │
         ┌───────────────┴────────────────┐
         │                                │
    ┌────▼─────┐  ┌──────▼──────┐  ┌────▼──────┐
    │ OpenAI   │  │   Gemini    │  │  Mistral  │
    │  GPT-4   │  │    Pro      │  │  Medium   │
    └──────────┘  └─────────────┘  └───────────┘
```

## Core Components

### 1. Frontend Layer (React)

**Purpose**: Provide a web-based interface for users to observe the AI agents playing.

**Key Components**:
- `App.js`: Main application component, manages game state
- `PlayerCard.js`: Displays individual player information
- `GameLog.js`: Shows game events and narration
- API Service: Handles communication with backend

**Technologies**:
- React 18 with functional components and hooks
- Axios for HTTP requests
- CSS for styling

### 2. Backend Layer (FastAPI)

**Purpose**: Serve as the API gateway and orchestrate game logic.

**Key Modules**:

#### `backend/main.py`
- FastAPI application setup
- REST API endpoints for game control
- WebSocket support for real-time updates
- CORS configuration for frontend communication

**Endpoints**:
- `POST /api/game/create` - Initialize new game
- `GET /api/game/state` - Retrieve current state
- `POST /api/game/start` - Begin the game
- `POST /api/game/next-phase` - Progress to next phase
- `GET /api/players` - Get player information
- `GET /api/providers` - List available AI providers
- `WS /ws` - WebSocket for real-time updates

### 3. Game Logic Layer

**Purpose**: Implement the rules and mechanics of Werewolves of Millers Hollow.

#### `backend/game/game_logic.py`
**Responsibilities**:
- Game initialization and setup
- Role distribution algorithm
- Phase management (night/day/discussion/voting)
- Victory condition checking
- Player elimination and death mechanics
- Night action processing
- Vote counting and resolution

**Key Methods**:
- `setup_game()`: Create players and assign roles
- `start_night()`: Begin night phase
- `process_night_actions()`: Execute night powers
- `start_day()`: Announce day and night results
- `conduct_discussion()`: Run discussion rounds
- `conduct_vote()`: Manage voting process
- `check_win_condition()`: Determine game end

### 4. AI Agent System

#### Game Master Agent (`backend/agents/game_master_agent.py`)

**Purpose**: Act as the narrator and game moderator.

**Capabilities**:
- Atmospheric narration
- Phase announcements
- Event descriptions
- Rule explanations
- Discussion moderation

**Personality**: Neutral, dramatic, engaging storyteller

#### Player Agents (`backend/agents/player_agent.py`)

**Purpose**: Autonomous players with unique personalities.

**Capabilities**:
- Personality-driven decision making
- Role-based actions (werewolf attacks, seer checks, etc.)
- Participation in discussions
- Strategic voting
- Memory of game events

**Personality System**:
Each player has one of 16 MBTI personality types that influences:
- Communication style
- Trust patterns
- Decision-making approach
- Reaction to events
- Strategic thinking

### 5. AI Provider Layer (`backend/agents/ai_provider.py`)

**Purpose**: Abstract LLM provider selection and configuration.

**Supported Providers**:
- **OpenAI GPT-4**: Most capable, best for complex reasoning
- **Google Gemini Pro**: Good balance of capability and speed
- **Mistral Medium**: Fast and efficient

**Design Pattern**: Factory pattern for easy provider switching

### 6. Data Models (`backend/models/game_models.py`)

**Purpose**: Define data structures using Pydantic.

**Key Models**:
- `PlayerProfile`: Name, sex, age, personality, role, status
- `GameState`: Current phase, players, log, actions
- `PersonalityType`: Enum of 16 MBTI types
- `Role`: Game roles (werewolf, seer, witch, etc.)
- `GamePhase`: Enum of game phases
- `PlayerStatus`: Alive, dead, in love

### 7. Profile Generator (`backend/agents/profile_generator.py`)

**Purpose**: Create diverse player profiles randomly.

**Generation Algorithm**:
1. Randomly select sex from 3 options (male, female, non-binary)
2. Choose appropriate name from curated lists
3. Generate age between 18-80
4. Assign random MBTI personality type

## Data Flow

### Game Initialization Flow

```
User clicks "Create Game"
    ↓
Frontend calls POST /api/game/create
    ↓
Backend creates WerewolfGame instance
    ↓
Profile Generator creates 24 players
    ↓
Game Logic assigns roles to players
    ↓
Player Agents are initialized (24)
    ↓
Game Master Agent is initialized (1)
    ↓
Game Master narrates opening
    ↓
State returned to frontend
```

### Night Phase Flow

```
POST /api/game/start or next-phase
    ↓
Game Master announces night
    ↓
For each role with night power:
    Player Agent decides action
    ↓
    LLM Provider generates decision
    ↓
    Action recorded
    ↓
All night actions processed
    ↓
Results applied to game state
    ↓
State updated and returned
```

### Discussion Phase Flow

```
Game transitions to discussion
    ↓
For each alive player (multiple rounds):
    Player Agent receives context
    ↓
    LLM generates response based on:
        - Player's personality
        - Player's role
        - Game history
        - Current suspicions
    ↓
    Response added to game log
    ↓
All discussions compiled
    ↓
State returned to frontend
```

### Voting Phase Flow

```
Game transitions to voting
    ↓
For each alive player:
    Player Agent evaluates candidates
    ↓
    LLM makes voting decision based on:
        - Discussions
        - Personal suspicions
        - Role objectives
        - Personality traits
    ↓
    Vote recorded
    ↓
Votes counted
    ↓
Player with most votes eliminated
    ↓
Game Master narrates elimination
    ↓
Win condition checked
```

## Scalability Considerations

### Current Architecture (24 Players)
- Sequential LLM calls during discussions (manageable)
- Memory stored in-memory (no persistence)
- Single-threaded game processing

### Potential Improvements
1. **Parallel LLM Calls**: Use asyncio for concurrent agent decisions
2. **Persistent Storage**: Redis or database for game state
3. **Caching**: Cache personality descriptions and common responses
4. **Rate Limiting**: Handle API rate limits gracefully
5. **Session Management**: Multiple concurrent games

## Security Considerations

1. **API Keys**: Stored in environment variables, never committed
2. **CORS**: Configured for specific frontend domains in production
3. **Input Validation**: Pydantic models validate all inputs
4. **Rate Limiting**: Should be added for production deployment
5. **WebSocket Security**: Consider authentication for production

## Performance Optimization

### Current Optimizations
- Memory-limited conversation history (last 5 messages)
- Truncated game logs (last 20 entries for frontend)
- Minimal state serialization

### Future Optimizations
1. **Batch Processing**: Group similar LLM calls
2. **Prompt Caching**: Reuse common prompt segments
3. **Streaming**: Stream LLM responses for better UX
4. **Background Tasks**: Process night actions asynchronously

## Testing Strategy

### Unit Tests
- Profile generation
- Role distribution algorithm
- Vote counting
- Win condition logic

### Integration Tests
- API endpoint functionality
- Agent decision making
- Game state transitions

### End-to-End Tests
- Complete game simulation
- Multiple provider testing
- Frontend-backend integration

## Deployment

### Docker Deployment
- Multi-stage builds for optimized images
- Nginx reverse proxy for frontend
- Environment-based configuration

### Cloud Deployment Options
1. **AWS**: ECS/EKS for containers, RDS for persistence
2. **Google Cloud**: Cloud Run, Cloud SQL
3. **Azure**: Container Instances, Cosmos DB
4. **Heroku**: Container Registry, Postgres addon

## Monitoring and Logging

### Logging
- Game events logged to `game_log`
- API requests logged by FastAPI
- LLM interactions tracked

### Metrics to Monitor
- LLM API latency
- Game duration
- Agent decision patterns
- Error rates
- Cost per game (API usage)

## Future Enhancements

1. **Multi-game Support**: Run multiple games concurrently
2. **Human Players**: Allow humans to join AI games
3. **Game Recording**: Save and replay games
4. **Advanced Analytics**: Track agent behavior patterns
5. **Custom Personalities**: User-defined personality traits
6. **Voice Narration**: Text-to-speech for game master
7. **Visual Enhancements**: 3D avatars, animations
8. **Tournament Mode**: Multiple games with rankings
