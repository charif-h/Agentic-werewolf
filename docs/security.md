# Security notes

This is a local prototype and is **not** ready to be exposed on the internet. This file lists the current state, not a certification.

## Known issues (tracked on GitHub)

- **No authentication, no rate limiting.** Anyone who can reach the API can create games and trigger paid LLM calls.

## What is in place

- **Separate games.** Every game has an unguessable random id (UUID); one client cannot see or change another game without knowing its id. Idle games expire and the number of games is capped.
- **Generic errors.** 500 responses only say what failed (e.g. `Failed to create game`); details are logged on the server.
- **Roles are hidden.** `GET /api/games/{id}`, `GET /api/games/{id}/players` and the night results sent by `next-phase` or the WebSocket do not reveal roles of living players, nor guard or seer information. Roles of dead players are shown. `REVEAL_ROLES=true` shows everything (debug / spectator).
- **Restricted CORS.** Only the origins in `CORS_ORIGINS` (default `http://localhost:3000`), `GET`/`POST`/`DELETE` methods, `Content-Type` header, no credentials.
- **Input validation.** `num_players` must be an integer from 1 to 1000 (otherwise 422) and is clamped to `MIN_PLAYERS`..`MAX_PLAYERS` (4..12 by default).
- API keys are read from environment variables / `.env`; `.env` is git-ignored and `.env.example` contains placeholders.
- Request bodies are validated by Pydantic.
- No database, no cookies, no user accounts, no persistent storage: games live in memory.
- Prompts are built only from game state and generated profiles; there is no free-text user input going into prompts.

## Data sent to third parties

While cloud providers are used, game content (player names, roles, discussion text) is sent to the selected provider (OpenAI, Google or Mistral) under that provider's data policy. This goes away with the planned local-model migration.

## Before any public deployment

1. Add authentication and rate limiting; serve over HTTPS.
3. Run `pip audit` and `npm audit`.
4. Rotate and separate API keys per environment.

## Reporting a vulnerability

Open a GitHub issue, or contact the maintainer privately if it is sensitive.
