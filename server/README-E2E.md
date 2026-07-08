E2E Network Tests

This repository contains a small set of network end-to-end (E2E) tests that start an in-process
`simple_server.Server` instance and connect to it using asyncio streams (the existing
`simple_client` helpers). These tests are intentionally self-contained and use a temporary
`run/server` directory so they are safe to run in CI.

Purpose
- Exercise the real server/client protocol (handshake, terminal negotiation, login, app mode).
- Validate that player state is synchronized (room/level) and persisted on clean quit and abrupt disconnect.

Files
- tests/test_network_e2e_real_login.py  — real handshake, log in with a seeded test account, send bye, verify save
- tests/test_network_e2e_reconnect.py   — login, move/sync room, quit, restart server, reconnect and verify restored room
- tests/test_move_south_room1.py        — move south from room 1 (per level_1.json) to room 13 and save
- tests/test_abrupt_disconnect.py       — abrupt socket close; verify server saves the player

All four log in with a real account (`tests/conftest.py`'s `seed_test_account()` +
`perform_login()`), not `connect guest` — guest sessions are intentionally never
saved (`commands/connect.py`'s `_handle_guest()` tells the client so explicitly),
so a guest login can't be used to test persistence. `conftest.py` also has
`perform_login_as_guest()`/`answer_terminal_negotiation()` for tests that only
need a live session, not a saved one.

Quick local run (from `server/`):

# create and activate a venv (optional but recommended)
python -m venv .venv
source .venv/bin/activate

# install the server's runtime dependencies
pip install -r requirements.txt

# install test tools -- requirements.txt only lists runtime dependencies,
# not pytest itself (a past e2e-tests.yml revision forgot this step and
# the job failed until it was added back)
pip install pytest pytest-asyncio

# run the E2E tests only
pytest -q tests/test_network_e2e_real_login.py tests/test_network_e2e_reconnect.py tests/test_move_south_room1.py tests/test_abrupt_disconnect.py

CI advice
- Run the above pytest command on a Linux runner that provides a Python 3.11+ environment.
- `requirements.txt` only installs the server's runtime dependencies; install
  `pytest`/`pytest-asyncio` separately (both workflows in `.github/workflows/`
  do this).
- If you want to run only a single test file in CI, use the same pytest command but pass only that file.

Notes
- The JSON control port binds to an ephemeral port (port 0), but the PETSCII
  port defaults to the real, hardcoded `simple_server.PETSCII_PORT` (34064)
  unless a test explicitly overrides it. That means these tests (and several
  others under `tests/` that construct a real `Server(...)`) can conflict
  with each other, or with a locally running dev server, if run concurrently
  or in certain orders. If a test fails with "address already in use" or
  `AttributeError: 'NoneType' object has no attribute 'sockets'`, check for
  another process (or test) already bound to port 34064 first — it's rarely
  the test's own logic.
- Every `asyncio.run(...)` call in these four tests is wrapped in
  `asyncio.wait_for(..., timeout=10)`. This test category has hung the whole
  pytest process outright at least twice in this project's history (once
  from a missing terminal-negotiation reply, once from Python 3.12+'s
  `Server.wait_closed()` also waiting on still-open client connections) --
  the timeout turns a silent, whole-suite-killing hang into an ordinary,
  diagnosable test failure. Keep it on any new test in this style.
- Tests set `net_common.run_server_dir` to a pytest `tmp_path` to avoid polluting the repo with saved player files.
- If your CI has resource limits or runs many workers in parallel, increase the short sleeps/timeouts in the tests slightly.

## Continuous Integration (`.github/workflows/`)

Two workflows run on every push/PR to `main`/`master`:

- **`ci.yml`** ("CI - Lint & Tests") — runs `flake8` and the full pytest suite.
  Both are informational only: every command ends in `|| true`, so this job
  always reports success on GitHub regardless of lint or test results. Its
  purpose is to surface style/test output in the Actions log for review, not
  to gate merges. On failure it would try to attach `diagnose_server.py
  --report` output and any files under `server/artifacts`/`server/run/server`
  as downloadable job artifacts — but since the job can't actually fail, this
  step never fires in practice today.
- **`e2e-tests.yml`** ("Server E2E Tests") — runs exactly the four tests
  listed above. Unlike `ci.yml`, this one does **not** swallow failures, so
  it's the one that actually shows red/green on a PR.

Both jobs run `python diagnose_server.py --report` for diagnostics if a step
before it fails; that script (`server/diagnose_server.py`) checks that the
run directory is writable, the core JSON data files parse, and the map
loads, without actually starting the server.
