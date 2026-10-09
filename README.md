# Agentic Werewolf

An AI-driven version of *The Werewolves of Millers Hollow*. Every player is an LLM agent with a random profile (name, sex, age, one of the 16 MBTI personalities) and a secret role. A rule-based Game Master (templates, no LLM) narrates. You watch the game in a React UI.

> **Status:** prototype. It runs on cloud LLM APIs today. A move to a local Gemma model is planned (see the open issues and milestones on GitHub).

## How it works

1. `POST /api/game/create` generates players, assigns roles and creates one `PlayerAgent` per player.
2. The UI advances the game with `POST /api/game/next-phase`: **night** (werewolves, seer, guard act) -> **day** (deaths announced) -> **discussion** (up to 5 rounds, players may speak or stay silent) -> **voting** -> next night, until a team wins.
3. Villagers win when no werewolf is left. Werewolves win when they equal or outnumber everyone else.

Role distribution depends on player count: werewolves = max(2, n // 6); Seer from 8 players, Witch from 10, Hunter from 12, Guard from 16; the rest are villagers.

**Roles:** Werewolf (kills at night, knows its teammates), Villager, Seer (inspects one player per night and remembers the results), Guard (protects one player per night, never the same one twice in a row), Witch (one healing and one poison potion for the whole game), Hunter (shoots someone when killed). Cupid and Little Girl were removed: they were never implemented.

**Known limitations** (tracked as GitHub issues): only one werewolf decides the night kill; the API blocks while the LLM is working.

## Requirements

- Python 3.11+
- Node.js 18+
- An API key for at least one of OpenAI, Google Gemini or Mistral
- Docker + Docker Compose (optional)

## Quick start

```bash
git clone https://github.com/charif-h/Agentic-werewolf.git
cd Agentic-werewolf
cp .env.example .env        # then edit .env: add a key and set AI_PROVIDER
```

### With Docker

```bash
docker-compose up --build
```

### Without Docker

```bash
# Backend (from the project root)
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm start
```

Then open:

- Frontend: http://localhost:3000
- API: http://localhost:8000, interactive docs at http://localhost:8000/docs

### Configuration (`.env`)

All settings live in `backend/config.py` and can be set in `.env` or as environment variables (see `.env.example` for the full list).

| Variable | Default | Meaning |
|---|---|---|
| `AI_PROVIDER` | `openai` | `openai`, `gemini` or `mistral` |
| `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `MISTRAL_API_KEY` | | key for the chosen provider |
| `OPENAI_MODEL`, `GEMINI_MODEL`, `MISTRAL_MODEL` | `gpt-4`, `gemini-2.5-pro`, `mistral-small-latest` | model names |
| `DEFAULT_PLAYERS`, `MIN_PLAYERS`, `MAX_PLAYERS` | 8, 4, 12 | player count (requests are clamped to the min/max) |
| `DISCUSSION_MAX_ROUNDS` | 5 | maximum discussion rounds |
| `REVEAL_ROLES` | `false` | show every role in the API (debug); by default only dead players' roles are visible |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | allowed frontend origins (JSON list) |
| `REACT_APP_API_URL` | `http://localhost:8000` | backend URL used by the frontend |

The `.env` file must be in the project root.

## API

Each game has its own id, so several games can run at once. Idle games are removed after `SESSION_TTL_MINUTES` and at most `MAX_SESSIONS` exist (the least recently used one is dropped).

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/games` | create a game, body `{"num_players": 8, "ai_provider": null}`; returns `game_id` |
| GET | `/api/games/{id}` | phase, day, players, last 20 log lines |
| POST | `/api/games/{id}/start` | start the first night |
| POST | `/api/games/{id}/next-phase` | run the current phase and move on (409 if one is already running) |
| GET | `/api/games/{id}/players` | player profiles |
| DELETE | `/api/games/{id}` | delete the game |
| GET | `/api/providers` | configured AI providers |
| WS | `/ws/{id}` | events of one game (`phase_change`); currently also echoes messages |

```bash
curl -X POST http://localhost:8000/api/games   -H "Content-Type: application/json" -d '{"num_players": 8}'
```

## Project layout

```
backend/
  main.py                 FastAPI app (REST + WebSocket)
  prompts/                prompt templates sent to the LLM (player.py)
  roles/                  one module per role (team, prompts, night action); add a role = add a file
  engine/rules.py         pure game rules (roles, night, voting, win condition): no LLM, no I/O
  game/game_logic.py      WerewolfGame: asks the agents for decisions and applies them via the engine
  game/game_master.py     template-based Game Master (no LLM)
  agents/                 player_agent, profile_generator, ai_provider
  models/game_models.py   Pydantic models and enums
frontend/src/             React app (App.js, components/, services/api.js)
tests/                    pytest tests (no LLM needed)
docs/                     architecture.md, security.md
```

See [docs/architecture.md](docs/architecture.md) and [docs/security.md](docs/security.md).

## Tests

```bash
pip install -r backend/requirements-dev.txt
python -m pytest tests
```

## Troubleshooting

- **"... API_KEY not found in environment"**: `.env` is missing, not in the project root, or `AI_PROVIDER` does not match the key you set.
- **Python import errors**: run uvicorn from the project root, as `python -m uvicorn backend.main:app`.
- **Port in use**: change `--port` for uvicorn, or `PORT=3001 npm start` for the frontend.
- **Frontend cannot reach the backend**: check that the backend is running and `REACT_APP_API_URL` is correct.
- **429 / rate-limit messages**: the provider is throttling you; players fall back to default answers. Use fewer players.
- **Docker build problems**: `docker-compose down` then `docker-compose up --build`.

## License

MIT. Inspired by the board game *The Werewolves of Millers Hollow*; the personality system is based on MBTI.
