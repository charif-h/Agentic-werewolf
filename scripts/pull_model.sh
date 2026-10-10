#!/bin/sh
# Download the model used by the game into Ollama.
#   scripts/pull_model.sh            -> model from LLM_MODEL (.env or environment), default gemma3:4b
#   scripts/pull_model.sh gemma3:1b  -> a specific model
# Uses the local `ollama` command, or the ollama container if it is not installed.
set -e

cd "$(dirname "$0")/.."

MODEL="$1"
if [ -z "$MODEL" ] && [ -f .env ]; then
    MODEL=$(grep -E '^LLM_MODEL=' .env | tail -n 1 | cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d '\r')
fi
MODEL="${MODEL:-${LLM_MODEL:-gemma3:4b}}"

echo "Pulling $MODEL ..."
if command -v ollama >/dev/null 2>&1; then
    ollama pull "$MODEL"
elif command -v docker >/dev/null 2>&1; then
    docker compose up -d ollama
    docker compose exec ollama ollama pull "$MODEL"
else
    echo "Neither 'ollama' nor 'docker' was found. Install Ollama from https://ollama.com" >&2
    exit 1
fi
echo "Done. Check with: ollama list"
