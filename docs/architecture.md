# Architecture

```
React UI  --REST-->  FastAPI (backend/main.py)  -->  WerewolfGame (game/game_logic.py)
   ^                      |                              |-- GameMaster (no LLM)
   '------WebSocket-------'                              '-- PlayerAgent x N   }-- AIProvider -> cloud LLM
                                                                                  (LangChain)
```

State lives in memory in one global `WerewolfGame` instance. There is no database.

## Backend modules

| Module | Role |
|---|---|
| `backend/main.py` | REST endpoints, `ConnectionManager` for WebSocket broadcast, CORS. Each endpoint calls `WerewolfGame` synchronously. |
| `backend/engine/rules.py` | Pure rules, no LLM or I/O: role distribution, valid night targets, night resolution (kill, guard, seer, lovers), vote tally, win condition. Randomness is injectable (`random.Random`), so a full game can run in a unit test. |
| `backend/game/game_logic.py` | `WerewolfGame` orchestrator: asks player agents for decisions (LLM), passes them to the engine, writes the game log. Also runs the discussion rounds. |
| `backend/agents/player_agent.py` | `PlayerAgent`: one per player. Builds the persona prompt from profile + role and exposes `night_action`, `discuss`, `vote`. Keeps its own short message memory. |
| `backend/game/game_master.py` | `GameMaster`: template announcements (night, day, elimination, winner) and the rule that decides when discussion ends. No LLM calls. |
| `backend/agents/profile_generator.py` | Random unique names, sex, age (18-80), MBTI personality. |
| `backend/agents/ai_provider.py` | `AIProvider.get_llm()`: factory returning a LangChain chat model for OpenAI, Gemini or Mistral. |
| `backend/models/game_models.py` | Pydantic models and enums: `PlayerProfile`, `GameState`, `Discussion`, `Message`, `Role`, `GamePhase`, `PlayerStatus`, `PersonalityType`, `Sex`. |

## Phase flow

`POST /api/game/next-phase` runs one step depending on `game.state.phase`:

| Current phase | What happens | Next |
|---|---|---|
| night | werewolf (first one only) picks a target, guard protects, seer checks; kill applied unless protected; day announced | day |
| day | `conduct_discussion(max_rounds=5)`: players in random order may speak or say "no comment"; the Game Master ends it after a silent round (from round 2), at max rounds, or from round 3 when fewer than max(2, players/3) people spoke | discussion |
| discussion | every player votes independently; most votes is eliminated (ties random); win condition checked | night or ended |

## Frontend

`frontend/src/App.js` holds the state and buttons. `components/PlayerCard.js` and `components/GameLog.js` render players and log. `services/api.js` wraps the REST calls with axios. The WebSocket (`/ws`) is not used by the UI yet.

## Deployment

`docker-compose.yml` runs two services: `backend` (uvicorn on 8000, built from `Dockerfile.backend`) and `frontend` (nginx on port 3000, built from `Dockerfile.frontend`). API keys are passed as environment variables.

## Planned changes

Tracked in GitHub milestones: separate a pure rules engine from the agents, session-based games, async API, finish roles, replace cloud providers with a local Gemma model, real test suite.
