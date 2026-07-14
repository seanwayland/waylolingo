#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-4}"
MAX_QUEUE="${OLLAMA_MAX_QUEUE:-8}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama CLI not found. Install Ollama first."
  exit 1
fi

cd "$PROJECT_ROOT"

echo "Stopping Ollama..."
if [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
  if brew services list | grep -q '^ollama\s'; then
    brew services stop ollama >/dev/null || true
  fi
fi
pkill -f 'ollama serve' >/dev/null 2>&1 || true

# Wait briefly for old listeners to drop.
for _ in {1..50}; do
  if ! lsof -nP -iTCP:11434 -sTCP:LISTEN >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

echo "Starting Ollama with OLLAMA_NUM_PARALLEL=${NUM_PARALLEL} OLLAMA_MAX_QUEUE=${MAX_QUEUE}"
OLLAMA_NUM_PARALLEL="$NUM_PARALLEL" OLLAMA_MAX_QUEUE="$MAX_QUEUE" nohup ollama serve >/tmp/ollama-serve.log 2>&1 &

# Wait for readiness.
for _ in {1..200}; do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:11434/api/tags || true)"
  if [[ "$code" == "200" ]]; then
    break
  fi
  sleep 0.1
done

final_code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:11434/api/tags || true)"
if [[ "$final_code" != "200" ]]; then
  echo "Ollama did not become ready. Check /tmp/ollama-serve.log"
  exit 1
fi

pid="$(pgrep -f 'ollama serve' | head -n 1 || true)"
echo "Ollama is ready on http://127.0.0.1:11434 (pid=${pid})"

if [[ -n "$pid" ]]; then
  echo "Process env excerpt:"
  ps eww -p "$pid" | tr ' ' '\n' | grep -E '^OLLAMA_(NUM_PARALLEL|MAX_QUEUE)=' || true
fi
