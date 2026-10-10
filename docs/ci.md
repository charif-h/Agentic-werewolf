# Continuous integration

## What runs on every push and pull request (`.github/workflows/ci.yml`)

| Job | Steps | Needs |
|---|---|---|
| Backend | `pip install` (runtime + dev requirements), `ruff check .`, `pytest --cov=backend` | Python 3.11 only. The tests use a scripted fake model: **no GPU, no Ollama**. |
| Frontend | `npm ci`, `npm run lint`, `npm run build` | Node 20 |

A new push to the same branch cancels the run that is still going. Pip and npm downloads are cached.

You can run exactly the same checks locally:

```bash
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
ruff check . && python -m pytest --cov=backend
cd frontend && npm ci && npm run lint && npm run build
```

## Optional: smoke test against the real model (`.github/workflows/real-model-smoke.yml`)

GitHub's hosted runners have no GPU, so a test with the real Gemma model needs **your own machine as a self-hosted runner**. The workflow is manual (Actions tab, "Run workflow") and never runs by itself.

1. Install Ollama on that machine and pull the model (`ollama pull gemma3:4b`).
2. In the repository: Settings, Actions, Runners, New self-hosted runner, and follow the instructions. When asked for labels, add `ollama`.
3. Run the workflow and choose the number of games, players and optionally a model. It plays the games with `scripts/simulate.py`, prints the report in the job summary and uploads `simulation.json` and `simulation.md`.

Only use a self-hosted runner on a **private** repository or with workflows you trust: a pull request from a fork could otherwise run code on your machine. This workflow is manual-only for that reason.
