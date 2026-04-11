#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

find_free_port() {
  local start_port="$1"
  python3 - "$start_port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
while port < 65535:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            port += 1
            continue
        print(port)
        break
PY
}

if [[ ! -x "$BACKEND_DIR/.venv/bin/python" ]]; then
  echo "Missing backend virtualenv. Run the first-time setup from README first."
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Missing frontend dependencies. Run 'cd frontend && npm install' first."
  exit 1
fi

BACKEND_PORT="${BACKEND_PORT:-$(find_free_port 8000)}"
FRONTEND_PORT="${FRONTEND_PORT:-$(find_free_port 5173)}"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo "Starting backend on http://127.0.0.1:${BACKEND_PORT}"
(
  cd "$BACKEND_DIR"
  source .venv/bin/activate
  exec python -m uvicorn app.main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "Starting frontend on http://127.0.0.1:${FRONTEND_PORT}"
cd "$FRONTEND_DIR"
exec env VITE_API_BASE_URL="http://127.0.0.1:${BACKEND_PORT}" npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT"
