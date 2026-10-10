# Architecture

One idea shapes the code: **the rules of the game know nothing about the language model**. The model only answers questions ("who do you vote for?", "what do you say?"); the rules decide what the answers mean. That is why a whole game can be played in a unit test with a scripted model, and why the model can be changed without touching the rules.

## The big picture

```
  Browser (React + Vite)                      one process (FastAPI / uvicorn)
 ┌────────────────────┐   REST + WebSocket  ┌──────────────────────────────────────────────┐
 │ page, live log,    │ <─────────────────> │  api/        routers, what clients may see   │
 │ model status       │                     │      │                                       │
 └────────────────────┘                     │  services/   sessions · phase state machine  │
                                            │      │                                       │
                                            │  game/       WerewolfGame (orchestrator)     │
                                            │      │  ┌─────────────┬──────────────────┐  │
                                            │      │  │ engine/     │ agents/          │  │
                                            │      │  │ rules       │ PlayerAgent ×N   │  │
                                            │      │  │ (no LLM,    │   uses roles/    │  │
                                            │      │  │  no I/O)    │   and prompts/   │  │
                                            │      │  └─────────────┴────────┬─────────┘  │
                                            │      │                         │            │
                                            │  llm/        LLMClient ─ OllamaClient       │
                                            └─────────────────────────────────┬────────────┘
                                                                              │ HTTP /api/chat
                                                                       ┌──────▼───────┐
                                                                       │    Ollama    │  gemma3:4b
                                                                       └──────────────┘
```

Dependencies point downwards only: `engine` and `roles` import nothing from `agents`, `llm` or `api`. State lives in memory (no database): one `WerewolfGame` per session.

## Modules

| Module | What it does |
|---|---|
| `main.py` | builds the app: CORS, one error handler (generic 500, details only in the log), the routers, the startup check of the model |
| `api/` | routers `games`, `players`, `health`, `websocket`; `serializers` decide what a client may see (no roles of living players, no guard or seer information); `state` holds the sessions and the WebSocket connections; `errors` |
| `services/sessions.py` | `SessionManager`: games by random id, time-to-live, maximum number (the least recently used goes first), one lock per game |
| `services/phases.py` | the **phase state machine**: a table from the current phase to the function that plays it (`advance_phase`) |
| `game/game_logic.py` | `WerewolfGame`, the **orchestrator**: asks the agents for decisions, hands them to the engine, writes the log, runs the discussion, emits live events |
| `game/game_master.py` | the Game Master: template announcements and the rule that ends the discussion. **No LLM** |
| `game/talkativeness.py` | decides, without any model call, whether a player takes their turn (personality, being named, long silence) and whether a line only repeats what was just said |
| `game/targets.py` | turns free text into valid player names (whole-word, case-insensitive) |
| `engine/rules.py` | **the rules**: role distribution, who may be targeted, night resolution (kill, guard, seer, witch), hunter's shot, vote tally, win condition. Pure functions over `GameState`; randomness is injectable |
| `roles/` | one module per role (team, descriptions, strategies, night action) and a registry. **Adding a role means adding one file** |
| `agents/player_agent.py` | `PlayerAgent`: one per player. Builds the prompts, asks for **JSON** answers, keeps a short memory and the player's secret knowledge (the seer's findings, the werewolves' teammates), falls back safely when an answer is unusable |
| `prompts/` | every sentence sent to the model, as plain functions |
| `llm/` | the model side: `LLMClient` (the interface), `OllamaClient`, `schemas` (JSON schemas and their parsers), `formatting` (Gemma chat format), `tokens` (context budget), `metrics`, `health`, and `FakeLLMClient` for tests |
| `models/game_models.py` | the data: `GameState`, `PlayerProfile`, `Role`, `GamePhase`, ... |

## A game, phase by phase

`POST /api/games/{id}/next-phase` plays one step of the state machine in a **worker thread**, so the server keeps answering other requests while the model works:

| Phase played | What happens | Next phase |
|---|---|---|
| night | the first werewolf chooses a victim, the guard a person to protect, the seer someone to inspect; the witch is told the victim and may heal and/or poison; the engine resolves it; a dead hunter shoots; the seer and the witch are told what they learned | day |
| day | `conduct_discussion`: up to 5 rounds of players speaking in turn (see below) until the Game Master says it is over | discussion |
| discussion | every player votes independently (a vote is always for another living player); the engine tallies and eliminates (ties are random); a dead hunter shoots; win condition checked | night, or the end |

Every step reports `player_spoke`, `vote_cast`, then `phase_change` (and `game_ended` after the last one) to the game's WebSocket. With `?background=true` the request answers 202 at once and the result arrives as the event.

**The discussion.** Players are asked in random order. Before asking, `talkativeness` decides without a model call: extraverts speak more than introverts, someone who spoke last round less, someone silent for a long time more, and someone who was just named always answers (the very first turn is never skipped). A line that only repeats what was just said is not published. The Game Master ends the discussion after a silent round, at the maximum, or when too few people speak. All of this exists to save model calls and to keep the talk interesting.

**What a player is asked.** Each question is a prompt plus a JSON schema. A vote or a night target must be one of the valid names (an `enum`, enforced by Ollama), the discussion answer is `{speak, message}`, the witch's is `{save, poison}`. If the model is unreachable or the answer is unusable the game uses a random valid target, stays silent in the discussion, and **never** uses a potion by chance.

## Concurrency

* **One model, one GPU.** All games share one `OllamaClient`. Its calls queue for `LLM_MAX_PARALLEL` slots (default 1), so ten games never fire ten requests at the GPU together. Time spent waiting is measured.
* **One phase per game at a time.** A lock per session; a second `next-phase` gets 409. Sessions that are busy are never expired.
* **Async API, blocking game.** The routes are `async`; the game code is plain blocking Python and runs in `asyncio.to_thread`. The thread reports events back to the event loop with `run_coroutine_threadsafe`.
* **Per-game metrics.** A context variable ties every model call to the game that made it: `GET /api/games/{id}` returns calls, tokens, time, skipped turns, unusable answers; a summary is logged when the game ends.

## The frontend

React with Vite (no runtime dependency but React). `useGame` keeps one reducer, calls the REST endpoints and follows the game's WebSocket (with reconnect and a reload after a reconnect); messages and votes appear as events arrive, the end of a phase reloads the real state. `useModelStatus` polls `/api/model` and shows the banner when Ollama is down. In development Vite forwards `/api` and `/ws` to the backend; in Docker nginx does. See [frontend.md](frontend.md).

## Deployment

`docker-compose.yml` runs `ollama` (models in a volume), `model-pull` (one-shot download of `LLM_MODEL`), `backend` (waits for the model) and `frontend` (nginx on port 3000, forwards `/api` and `/ws`). `docker-compose.gpu.yml` adds the NVIDIA GPU. At startup the backend logs whether Ollama is reachable and the model installed; creating a game answers 503 with the reason while it is not.

## Tests and tools

* About 360 backend tests (5 s, no GPU) with a scripted `FakeLLMClient`; the frontend has its own (Vitest). Full games are played by the engine alone, by the orchestrator with fake agents, and through the HTTP API and WebSocket.
* `tests/snapshots/` pins the exact prompts.
* `scripts/simulate.py` plays complete games against the real model and reports win rates, invalid answers, latency and role leaks; `scripts/benchmark_models.py` compares models. They found real problems that the unit tests could not (a model habit of closing JSON strings with curly quotes).
* CI (GitHub Actions) runs lint, tests and the frontend build; see [ci.md](ci.md).

## Recipes

* **Add a role**: create `roles/<name>.py` with a registered `RoleHandler` subclass (description, strategies, night action if any), add the role to `models.Role` and to `engine.rules.distribute_roles`, add tests. The registry finds the module by itself.
* **Change a prompt**: edit `prompts/player.py` (or a role's text), run `UPDATE_SNAPSHOTS=1 pytest tests/test_prompt_snapshots.py`, review the diff, then compare with `scripts/simulate.py` before and after.
* **Change the model**: `LLM_MODEL=<tag>`; compare with `scripts/benchmark_models.py` first ([model-benchmark.md](model-benchmark.md)).
* **Change a rule**: edit `engine/rules.py`; it has no dependencies, so its tests (`tests/test_rules_engine.py`) run instantly.
