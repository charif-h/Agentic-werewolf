# Security notes

This is a local game and is **not** ready to be exposed on the internet. This file lists the current state, not a certification. The design is local-only on purpose: the model, the games and the logs live on one machine.

## Known issues (tracked on GitHub)

- **No authentication, no rate limiting.** Anyone who can reach the API can create games and use your GPU.

## What is in place

- **Separate games.** Every game has an unguessable random id (UUID); one client cannot see or change another game without knowing its id. Idle games expire and the number of games is capped.
- **Generic errors.** 500 responses only say what failed (e.g. `Failed to create game`); details are logged on the server.
- **Roles are hidden.** `GET /api/games/{id}`, `GET /api/games/{id}/players` and the night results sent by `next-phase` or the WebSocket do not reveal roles of living players, nor guard or seer information. Roles of dead players are shown. `REVEAL_ROLES=true` shows everything (debug / spectator).
- **Restricted CORS.** Only the origins in `CORS_ORIGINS` (default `http://localhost:3000`), `GET`/`POST`/`DELETE` methods, `Content-Type` header, no credentials.
- **Input validation.** `num_players` must be an integer from 1 to 1000 (otherwise 422) and is clamped to `MIN_PLAYERS`..`MAX_PLAYERS` (4..12 by default).
- No API keys are needed. Settings come from environment variables / `.env` (git-ignored).
- Request bodies are validated by Pydantic.
- No database, no cookies, no user accounts, no persistent storage: games live in memory.
- Prompts are built only from game state and generated profiles; there is no free-text user input going into prompts.

## Data sent to third parties

None. The language model runs on your machine through Ollama; names, roles and everything the players say stay there (unless you point `OLLAMA_HOST` at another computer). There are no API keys, no accounts and no telemetry. The only downloads are the model itself (`ollama pull`) and the usual `pip` and `npm` packages.

## Before any public deployment

1. Add authentication and rate limiting in front of the API, and serve it over HTTPS.
2. Keep Ollama's port (11434) reachable only from the backend, never from the network.
3. Run `pip audit` and `npm audit` (the production frontend has no known vulnerability today; the remaining advisories are in development tools, see [frontend.md](frontend.md)).
4. Set `CORS_ORIGINS` to your real address.

## Reporting a vulnerability

Open a GitHub issue, or contact the maintainer privately if it is sensitive.
