#!/usr/bin/env bash
set -euo pipefail

# Launch run_server.py inside a detached, named screen session so it
# keeps running after you log out, and you can reattach to watch its
# logging output live.
#
# Usage: ./start_server_screen.sh [--host HOST] [--port PORT]
# Reattach with: screen -x tada   (or screen -r tada if not already attached)

SESSION=tada
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if screen -list | grep -q "\.${SESSION}[[:space:]]"; then
  echo "A screen session named '${SESSION}' is already running." >&2
  echo "Reattach with: screen -x ${SESSION}" >&2
  exit 1
fi

# Activate venv if present
PYTHON=python3
if [ -f "${SCRIPT_DIR}/.venv/bin/activate" ]; then
  PYTHON="${SCRIPT_DIR}/.venv/bin/python3"
fi

cd "${SCRIPT_DIR}"
screen -dmS "${SESSION}" "${PYTHON}" run_server.py "$@"
echo "Started '${SESSION}' in a detached screen session."
echo "Attach with: screen -x ${SESSION}"
