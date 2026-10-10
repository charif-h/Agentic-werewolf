# Agentic Werewolf

[![CI](https://github.com/charif-h/Agentic-werewolf/actions/workflows/ci.yml/badge.svg)](https://github.com/charif-h/Agentic-werewolf/actions/workflows/ci.yml)

*The Werewolves of Millers Hollow* played by AI. Every player is an agent driven by a **local Gemma model** (through [Ollama](https://ollama.com)) with a random name, age and one of the 16 MBTI personalities, and a secret role. They talk, accuse each other, vote and kill. A rule-based Game Master narrates, and you watch it all live in a web page.

No API key, no cloud: nothing leaves your machine.

## What you need

| | |
|---|---|
| **Ollama** | to run the model: https://ollama.com (Windows: `winget install Ollama.Ollama`) |
| **The model** | `gemma3:4b`, a **3.4 GB** download |
| **Memory** | about **3 GB of GPU memory** (measured: 2.9 GB). A GPU with 6 GB or more is comfortable; an 8 GB laptop GPU (RTX 3070 Ti) plays a whole game in 1.5 to 2 minutes. Without a GPU Ollama falls back to the CPU: it works but is much slower (not measured here); use `gemma3:1b` (0.8 GB) in that case |
| **Python** 3.11+ and **Node.js** 18+ | unless you use Docker |

## Quick start

Install Ollama first (see above), then three steps. They are the same on Windows, macOS and Linux:

```bash
git clone https://github.com/charif-h/Agentic-werewolf.git && cd Agentic-werewolf

# 1. the model (once, 3.4 GB)
ollama pull gemma3:4b

# 2. the backend, in a first terminal
python -m venv venv && source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --port 8000

# 3. the web page, in a second terminal
cd frontend && npm install && npm run dev
```

Open **http://localhost:3000**, click *Create New Game*, *Start Game*, then *Next Phase* and watch.

Prefer containers? One command starts everything, Ollama and the model download included:

```bash
docker compose up --build                                                    # CPU
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build    # NVIDIA GPU (needs the NVIDIA Container Toolkit)
```

If something does not work, the page tells you what is wrong (Ollama not running, model not installed); the [Troubleshooting](#troubleshooting) section has the details.

## How a game works

1. **Setup**: random profiles, roles shuffled, one agent per player. Werewolves know each other.
2. **Night**: the werewolves choose a victim, the guard protects someone, the seer inspects someone; then the witch learns who was attacked and may heal and/or poison. A dead hunter shoots someone.
3. **Day**: the deaths are announced, then the **discussion**: players speak in turn (up to 5 rounds), accuse, defend, and answer when they are named.
4. **Vote**: everybody votes independently; the most voted player is eliminated and their role revealed.
5. Repeat until all werewolves are dead (**villagers win**) or the werewolves are at least as many as everybody else (**werewolves win**).

| Role | Power |
|---|---|
| Werewolf | kills one villager each night; the first living werewolf decides for the pack |
| Villager | none, only logic |
| Seer (from 8 players) | inspects one player per night and remembers the results |
| Witch (from 10) | one healing and one poison potion for the whole game |
| Hunter (from 12) | shoots a player when killed (by night, poison or vote) |
| Guard (from 16) | protects one player per night, never the same one twice in a row |

Werewolves are `max(2, players / 6)`; the rest are villagers. The page hides the roles of living players; the *Spectator mode* switch shows them if the server runs with `REVEAL_ROLES=true`.

## Configuration

Everything has a default. Set what you need in a `.env` file at the project root or as environment variables (the full list is in `.env.example`, the code in `backend/config.py`).

| Variable | Default | Meaning |
|---|---|---|
| `LLM_MODEL` | `gemma3:4b` | model tag; `gemma3:1b` is the small fallback ([model comparison](docs/model-benchmark.md)) |
| `OLLAMA_HOST` | `http://localhost:11434` | where Ollama runs |
| `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` | 0.8, 256 | sampling temperature, longest answer |
| `LLM_NUM_CTX`, `LLM_KEEP_ALIVE`, `LLM_TIMEOUT` | 4096, `30m`, 120 | context window, how long the model stays loaded, seconds per answer |
| `LLM_MAX_PARALLEL` | 1 | model calls in flight at once; raise with Ollama's `OLLAMA_NUM_PARALLEL` if your GPU can serve several |
| `LLM_WARMUP` | `true` | load the model when the server starts, so the first game does not wait |
| `DEFAULT_PLAYERS`, `MIN_PLAYERS`, `MAX_PLAYERS` | 8, 4, 12 | player count (requests are clamped to the min and max) |
| `DISCUSSION_MAX_ROUNDS` | 5 | most discussion rounds per day |
| `DISCUSSION_GATE` | `true` | players with nothing pressing to say skip their turn and repeated lines are not published (fewer model calls) |
| `REVEAL_ROLES` | `false` | the API sends everybody's role (debug and spectator mode) |
| `MAX_SESSIONS`, `SESSION_TTL_MINUTES` | 20, 120 | how many games at once, and when an idle game is removed |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | allowed web origins (JSON list) |
| `VITE_API_URL` | empty | frontend only: the backend address if it is not on the same origin |

## API

Several games can run at once; each has its own id.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/games` | create a game, body `{"num_players": 8}`; returns `game_id` |
| GET | `/api/games/{id}` | phase, day, players, latest log lines (`?log_limit=`, default 200), model usage, `roles_revealed` |
| POST | `/api/games/{id}/start` | start the first night |
| POST | `/api/games/{id}/next-phase` | play the current phase; waits for the result, or answers 202 at once with `?background=true` (409 if a phase is running, the game has not started or has ended) |
| GET | `/api/games/{id}/players` | player profiles |
| DELETE | `/api/games/{id}` | delete the game |
| GET | `/api/model` | is Ollama reachable, the model installed, loaded in memory (and how much GPU memory)? |
| GET | `/api/health` | liveness and number of running games |
| WS | `/ws/{id}` | live events: `player_spoke`, `vote_cast`, `phase_change`, `game_ended`, `error` |

Interactive documentation: http://localhost:8000/docs.

## Project layout

```
backend/
  main.py             app: middleware, error handler, routers
  api/                routers (games, players, health, websocket), what clients may see, shared state
  services/           sessions (several games) and the phase state machine
  game/               WerewolfGame (orchestrator), Game Master (templates), who talks, name parsing
  engine/rules.py     the rules: pure functions, no LLM, no I/O
  roles/              one module per role: add a role = add a file
  agents/             PlayerAgent and profile generator
  prompts/            every prompt sent to the model
  llm/                the model interface, Ollama client, JSON schemas, fake client for tests
  models/             data models
frontend/             React + Vite page (live events, model status, spectator mode)
scripts/              pull_model, benchmark_models, simulate
tests/                about 360 tests, no GPU needed
docs/                 architecture, model benchmark, frontend, CI, security
```

Read [docs/architecture.md](docs/architecture.md) to see how the pieces fit, [docs/model-benchmark.md](docs/model-benchmark.md) for the model choice, [docs/frontend.md](docs/frontend.md), [docs/ci.md](docs/ci.md) and [docs/security.md](docs/security.md).

## Development

```bash
pip install -r backend/requirements-dev.txt
python -m pytest                       # about 360 tests in 5 seconds: a scripted fake model, no GPU, no Ollama
python -m pytest --cov=backend         # with coverage (about 98%)
python -m pytest --run-realmodel       # also the tests marked `realmodel` (need Ollama and the model)
ruff check .                           # lint
cd frontend && npm test && npm run lint && npm run build
```

* **Changing a prompt**: `tests/snapshots/` holds the exact chat the model receives for every role and question. After a deliberate change run `UPDATE_SNAPSHOTS=1 python -m pytest tests/test_prompt_snapshots.py` and review the diff.
* **Comparing models or prompts on real games**: `python scripts/simulate.py --games 20 --players 8` plays complete games against your local model and reports win rates, invalid-output rate, latency and role leaks. `python scripts/benchmark_models.py gemma3:1b gemma3:4b` compares models on fixed scenarios.
* GitHub Actions runs lint, tests and the frontend build on every push; see [docs/ci.md](docs/ci.md).

## Troubleshooting

- **The page says *Ollama is not running***: start Ollama (on Windows it lives in the tray after installation) and press *Retry*. `GET /api/model` shows the same status, and the backend logs it at startup. Creating a game answers 503 with the reason until the model is ready.
- **The page says *the model is not installed***: run `ollama pull gemma3:4b` (or the tag you set in `LLM_MODEL`).
- **The first answer takes up to a minute**: the model is being loaded into memory. After that answers take about a second. The server warms the model up at startup (`LLM_WARMUP`).
- **Games are slow**: check that Ollama uses your GPU (`ollama ps` shows `100% GPU`). Without one use `LLM_MODEL=gemma3:1b`.
- **`ModuleNotFoundError: backend`**: start uvicorn from the project root as `python -m uvicorn backend.main:app`.
- **Port in use**: change `--port` for uvicorn, or run `npm run dev -- --port 3001` for the page (its dev server forwards `/api` and `/ws` to `http://127.0.0.1:8000`, change that with `VITE_BACKEND_URL`).
- **Docker: the backend never starts**: it waits for the model; `docker compose logs model-pull` shows the download.

## License

MIT. Inspired by the board game *The Werewolves of Millers Hollow*; the personality system is based on MBTI.
