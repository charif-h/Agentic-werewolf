# Architecture

```
React UI  --REST-->  FastAPI (backend/main.py)  -->  WerewolfGame (game/game_logic.py)
   ^                      |                              |-- GameMaster (no LLM)
   '------WebSocket-------'                              '-- PlayerAgent x N   }-- AIProvider -> cloud LLM
                                                                                  (LangChain)
```

State lives in memory: one `WerewolfGame` per session, kept in a `SessionManager` (`backend/services/sessions.py`) keyed by a random id, with a TTL and a maximum count. A per-session lock prevents two phases from running at once. There is no database.

## Backend modules

| Module | Role |
|---|---|
| `backend/main.py` | Builds the app: CORS, central error handler (generic 500, details only in the log), routers. |
| `backend/api/` | Routers: `games` (create, state, start, next-phase), `players`, `health` (root, health, providers), `websocket` (`/ws/{id}`); `serializers` (what clients may see), `state` (sessions and WebSocket connections), `errors`. |
| `backend/services/phases.py` | Phase state machine: a table from the current phase to the function that plays it (`advance_phase`). Blocking, so the API runs it in a worker thread (`asyncio.to_thread`). While it runs, `WerewolfGame.on_event` pushes `player_spoke` and `vote_cast` events to the game's WebSocket clients. |
| `backend/prompts/` | Prompt templates for player agents as plain functions (persona, game context, discussion, vote). Role-specific text comes from the role handlers. |
| `backend/roles/` | One module per role, registered in a registry (`get_handler(role)`). A `RoleHandler` holds the team, the prompts (description, discussion/voting strategy), and the night action (order, valid targets, what it records). Adding a role means adding one file. |
| `backend/engine/rules.py` | Pure rules, no LLM or I/O: role distribution, valid night targets, night resolution (kill, guard, seer, witch potions), hunter death shot, vote tally, win condition. Randomness is injectable (`random.Random`), so a full game can run in a unit test. |
| `backend/game/game_logic.py` | `WerewolfGame` orchestrator: asks player agents for decisions (LLM), passes them to the engine, writes the game log. Also runs the discussion rounds. |
| `backend/agents/player_agent.py` | `PlayerAgent`: one per player. Builds the persona prompt from profile + role and exposes `night_action`, `discuss`, `vote`. Keeps its own short message memory. |
| `backend/game/game_master.py` | `GameMaster`: template announcements (night, day, elimination, winner) and the rule that decides when discussion ends. No LLM calls. |
| `backend/agents/profile_generator.py` | Random unique names, sex, age (18-80), MBTI personality. |
| `backend/llm/` | The `LLMClient` interface (`generate(messages, max_tokens, temperature, json_schema) -> str`), `Message`, a scripted `FakeLLMClient` for tests, and `LangChainClient`, an adapter for the cloud providers. `WerewolfGame` creates **one** client and all players share it; agents receive it in their constructor. |
| `backend/agents/ai_provider.py` | `AIProvider.get_llm()`: factory returning a LangChain chat model for OpenAI, Gemini or Mistral. |
| `backend/models/game_models.py` | Pydantic models and enums: `PlayerProfile`, `GameState`, `Discussion`, `Message`, `Role`, `GamePhase`, `PlayerStatus`, `PersonalityType`, `Sex`. |

## Phase flow

`POST /api/games/{id}/next-phase` runs one step depending on the game phase (see `services/phases.py`). It runs in a worker thread, so the server keeps answering other requests; add `?background=true` to get an immediate 202 and the result as a `phase_change` WebSocket event:

| Current phase | What happens | Next |
|---|---|---|
| night | werewolf (first one only) picks a target, guard protects, seer checks; then the witch is told the victim and may heal and/or poison; kill applied unless protected or healed; a dead hunter shoots; day announced | day |
| day | `conduct_discussion(max_rounds=5)`: players in random order may speak or say "no comment"; the Game Master ends it after a silent round (from round 2), at max rounds, or from round 3 when fewer than max(2, players/3) people spoke | discussion |
| discussion | every player votes independently; most votes is eliminated (ties random); win condition checked | night or ended |

## Frontend

`frontend/src/App.js` holds the state and buttons. `components/PlayerCard.js` and `components/GameLog.js` render players and log. `services/api.js` wraps the REST calls with axios. The WebSocket (`/ws`) is not used by the UI yet.

## Deployment

`docker-compose.yml` runs two services: `backend` (uvicorn on 8000, built from `Dockerfile.backend`) and `frontend` (nginx on port 3000, built from `Dockerfile.frontend`). API keys are passed as environment variables.

## Planned changes

Tracked in GitHub milestones: separate a pure rules engine from the agents, session-based games, async API, finish roles, replace cloud providers with a local Gemma model, real test suite.
