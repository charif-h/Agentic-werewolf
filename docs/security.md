# Security notes

This is a local prototype and is **not** ready to be exposed on the internet. This file lists the current state, not a certification.

## Known issues (tracked on GitHub)

- **Error details leak.** Several endpoints in `backend/main.py` return `detail=f"... {str(e)}"` in 500 responses. An earlier version of this document said this was fixed; it is not in the current code.
- **CORS is wide open.** `allow_origins=["*"]` together with `allow_credentials=True`. Restrict it to your frontend origin before any shared deployment.
- **Roles are exposed.** `GET /api/game/state` and `GET /api/players` return every player's secret role to any client.
- **No authentication, no rate limiting.** Anyone who can reach the API can create games and trigger paid LLM calls.
- **One global game.** All clients share and can overwrite the same game.
- **Weak input validation.** `num_players` is capped at 12 but has no lower bound.

## What is in place

- API keys are read from environment variables / `.env`; `.env` is git-ignored and `.env.example` contains placeholders.
- Request bodies are validated by Pydantic.
- No database, no cookies, no user accounts, no persistent storage: games live in memory.
- Prompts are built only from game state and generated profiles; there is no free-text user input going into prompts.

## Data sent to third parties

While cloud providers are used, game content (player names, roles, discussion text) is sent to the selected provider (OpenAI, Google or Mistral) under that provider's data policy. This goes away with the planned local-model migration.

## Before any public deployment

1. Fix the issues above (error messages, CORS, role exposure, sessions).
2. Add authentication and rate limiting; serve over HTTPS.
3. Run `pip audit` and `npm audit`.
4. Rotate and separate API keys per environment.

## Reporting a vulnerability

Open a GitHub issue, or contact the maintainer privately if it is sensitive.
