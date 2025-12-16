#!/usr/bin/env bash
set -euo pipefail

# Run the network E2E tests in this server directory.
# Usage: ./run_e2e_tests.sh

PYTEST_FILES=(
  tests/test_network_e2e_real_login.py
  tests/test_network_e2e_reconnect.py
  tests/test_move_south_room1.py
  tests/test_abrupt_disconnect.py
)

# Activate venv if present
if [ -f .venv/bin/activate ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

pytest -q "${PYTEST_FILES[@]}"

