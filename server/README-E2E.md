E2E Network Tests

This repository contains a small set of network end-to-end (E2E) tests that start an in-process
`simple_server.Server` instance and connect to it using asyncio streams (the existing
`simple_client` helpers). These tests are intentionally self-contained and use a temporary
`run/server` directory so they are safe to run in CI.

Purpose
- Exercise the real server/client protocol (handshake, login/guest, app mode).
- Validate that player state is synchronized (room/level) and persisted on clean quit and abrupt disconnect.

Files
- tests/test_network_e2e_real_login.py  — real handshake, guest login, send bye, verify save
- tests/test_network_e2e_reconnect.py   — login, change/sync room, quit, restart server, reconnect and verify restored room
- tests/test_move_south_room1.py        — move south from room 1 (per level_1.json) to room 13 and save
- tests/test_abrupt_disconnect.py       — abrupt socket close; verify server saves the player

Quick local run (from `server/`):

# create and activate a venv (optional but recommended)
python -m venv .venv
source .venv/bin/activate

# install dependencies (project already contains requirements.txt)
pip install -r requirements.txt

# run the E2E tests only
pytest -q tests/test_network_e2e_real_login.py tests/test_network_e2e_reconnect.py tests/test_move_south_room1.py tests/test_abrupt_disconnect.py

CI advice
- Run the above pytest command on a Linux runner that provides a Python 3.11+ environment.
- Use the repository's `requirements.txt` to install test dependencies.
- If you want to run only a single test file in CI, use the same pytest command but pass only that file.

Notes
- The tests bind to ephemeral ports (port 0) so they do not require special privileges.
- Tests set `net_common.run_server_dir` to a pytest `tmp_path` to avoid polluting the repo with saved player files.
- If your CI has resource limits or runs many workers in parallel, increase the short sleeps/timeouts in the tests slightly.

