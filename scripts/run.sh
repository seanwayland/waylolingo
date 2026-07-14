#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -f "$PROJECT_ROOT/.env.local" ]]; then
	# Local machine overrides (for example, LAN host binding).
	source "$PROJECT_ROOT/.env.local"
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

cd "$PROJECT_ROOT"
exec make run HOST="$HOST" PORT="$PORT" "$@"