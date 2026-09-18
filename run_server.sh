#!/usr/bin/env bash
set -e

# Load virtual environment if present
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set default port and host
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"

echo "Starting GridWise LLM Optimization Service on http://${HOST}:${PORT}..."
exec uvicorn app.main:app --host "${HOST}" --port "${PORT}"
