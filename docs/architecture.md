# Architecture

```
React UI  --REST-->  FastAPI (backend/main.py)  -->  WerewolfGame (game/game_logic.py)
   ^                      |                              |-- GameMaster (no LLM)
   '------WebSocket-------'                              '-- PlayerAgent x N   }-- LLMClient -> Ollama (local Gemma)

```

State lives in memory: one `WerewolfGame` per session, kept in a `SessionManager` (`backend/services/sessions.py`) keyed by a random id, with a TTL and a maximum count. A per-session lock prevents two phases from running at once. There is no database.

## Backend modules

| Module | Role |
|---|---|
| `backend/main.py` | Builds the app: CORS, central error handler (generic 500, details only in the log), routers. |
| `backend/api/` | Routers: `games` (create, state, start, next-phase), `players`, `health` (root, health, model status), `websocket` (`/ws/{id}`); `serializers` (what clients may see), `state` (sessions and WebSocket connections), `errors`. |
| `backend/services/phases.py` | Phase state machine: a table from the current phase to the function that plays it (`advance_phase`). Blocking, so the API runs it in a worker thread (`asyncio.to_thread`). While it runs, `WerewolfGame.on_event` pushes `player_spoke` and `vote_cast` events to the game's WebSocket clients. |
| `backend/prompts/` | Prompt templates for player agents as plain functions (persona, game context, discussion, vote). Role-specific text comes from the role handlers. |
| `backend/roles/` | One module per role, registered in a registry (`get_handler(role)`). A `RoleHandler` holds the team, the prompts (description, discussion/voting strategy), and the night action (order, valid targets, what it records). Adding a role means adding one file. |
| `backend/engine/rules.py` | Pure rules, no LLM or I/O: role distribution, valid night targets, night resolution (kill, guard, seer, witch potions), hunter death shot, vote tally, win condition. Randomness is injectable (`random.Random`), so a full game can run in a unit test. |
| `backend/game/game_logic.py` | `WerewolfGame` orchestrator: asks player agents for decisions (LLM), passes them to the engine, writes the game log. Also runs the discussion rounds. |
| `backend/agents/player_agent.py` | `PlayerAgent`: one per player. Builds the persona prompt from profile + role and exposes `night_action`, `discuss`, `vote`. Keeps its own short message memory. |
| `backend/game/game_master.py` | `GameMaster`: template announcements (night, day, elimination, winner) and the rule that decides when discussion ends. No LLM calls. |
| `backend/agents/profile_generator.py` | Random unique names, sex, age (18-80), MBTI personality. |
| `backend/llm/schemas.py` | JSON schemas for the decisions players make (a target restricted to the valid names with an `enum`, the discussion `{speak, message}`, the witch's `{save, poison}`) and the parsers for the answers. Ollama's `format` option makes the model produce only matching JSON, so votes and night targets are always valid names. When the model is unreachable or the answer is not valid, the game uses a random valid target (never a potion). |
| `backend/llm/` | The `LLMClient` interface (`generate(messages, max_tokens, temperature, json_schema) -> str`), `Message`, `OllamaClient` (HTTP client for a local Ollama server: queues calls for `LLM_MAX_PARALLEL` slots, warms the model up, reports whether it is installed, counts calls/tokens/time), and a scripted `FakeLLMClient` for tests. One client is shared by every game and every player. |
| `backend/models/game_models.py` | Pydantic models and enums: `PlayerProfile`, `GameState`, `Discussion`, `Message`, `Role`, `GamePhase`, `PlayerStatus`, `PersonalityType`, `Sex`. |

## Phase flow

`POST /api/games/{id}/next-phase` runs one step depending on the game phase (see `services/phases.py`). It runs in a worker thread, so the server keeps answering other requests; add `?background=true` to get an immediate 202 and the result as a `phase_change` WebSocket event:

| Current phase | What happens | Next |
|---|---|---|
| night | werewolf (first one only) picks a target, guard protects, seer checks; then the witch is told the victim and may heal and/or poison; kill applied unless protected or healed; a dead hunter shoots; day announced | day |
| day | `conduct_discussion(max_rounds=5)`: players in random order may speak or say "no comment"; the Game Master ends it after a silent round (from round 2), at max rounds, or from round 3 when fewer than max(2, players/3) people spoke | discussion |
| discussion | every player votes independently; most votes is eliminated (ties random); win condition checked | night or ended |

## Performance on one GPU

* **One request at a time.** All games share one `OllamaClient`; its calls queue for `LLM_MAX_PARALLEL` slots (default 1), so ten games never fire ten requests at the GPU together. Time spent queued is reported as `wait_seconds`.
* **Model stays loaded.** `keep_alive` keeps it in memory between calls and the server loads it at startup (`LLM_WARMUP`), so the first game does not wait ~10 to 50 s.
* **Fewer calls.** In the discussion, `game/talkativeness.py` decides without any model call whether a player takes their turn: extraverts talk more than introverts, someone who spoke last round talks less, and a player who was just named always answers. The first turn of the day is never skipped.
* **Metrics per game.** `GET /api/games/{id}` returns `llm`: calls, errors, skipped turns, prompt/completion tokens, tokens per second, seconds of model time, seconds waiting. The totals for the whole server are in `OllamaClient.metrics()`; a summary of each game is logged when it ends.

## Frontend

`frontend/src/App.js` holds the state and buttons. `components/PlayerCard.js` and `components/GameLog.js` render players and log. `services/api.js` wraps the REST calls with axios. The WebSocket (`/ws`) is not used by the UI yet.

## Deployment

`docker-compose.yml` runs `ollama` (model server, models in the `ollama-models` volume), `model-pull` (one-shot download of `LLM_MODEL`), `backend` (uvicorn on 8000, waits for the model) and `frontend` (nginx on port 3000). `docker-compose.gpu.yml` adds NVIDIA GPU access. At startup the backend logs whether Ollama is reachable and the model installed (`backend/llm/health.py`); creating a game answers 503 with the reason while it is not.

## Planned changes

Tracked in GitHub milestones: separate a pure rules engine from the agents, session-based games, async API, finish roles, replace cloud providers with a local Gemma model, real test suite.
