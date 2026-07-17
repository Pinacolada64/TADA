# CLAUDE.md — TADA server conventions

## Code style

- **Preserve existing comments** when rewriting or extending a file. Inline
  comments explain non-obvious constraints and history that would otherwise be
  lost. Restore them verbatim; only remove a comment if the code it described
  is also being deleted.
- **Prefer `pathlib.Path` over `os.path`** for filesystem paths in new or
  rewritten code (e.g. `Path(__file__).parent / '..' / 'objects.json'` instead
  of `os.path.join(os.path.dirname(__file__), '..', 'objects.json')`). Don't
  churn untouched files just to convert existing `os.path` usage.
- **Sentence-case new player-facing strings, not SPUR's ALL-CAPS.** When
  porting flavor/narration text from the SPUR BASIC source, write it as
  `'You are caught off guard!'`, not `'YOU ARE CAUGHT OFF GUARD!'` — this
  port's existing tone is sentence case, and the source's screaming caps
  were a display-hardware artifact, not a style to preserve. Applies to
  new/rewritten strings only; don't churn untouched existing all-caps
  strings elsewhere just to convert them.

## Testing

- **Local runs skip e2e tests by default.** `pyproject.toml`'s `addopts`
  already includes `-m "not e2e"`, so a plain `pytest` / `pytest -q` (no
  extra flags) finishes in ~20s instead of ~60-130s. The 4 tests marked
  `@pytest.mark.e2e` start a real `Server` and real sockets
  (`tests/e2e/test_abrupt_disconnect.py`, `tests/e2e/test_network_e2e_real_login.py`,
  `tests/e2e/test_network_e2e_reconnect.py`, `tests/movement/test_move_south_room1.py`).
  CI (`.github/workflows/ci.yml` and `e2e-tests.yml`) overrides with `-m ""`
  so pushes/PRs still cover them.
- To run everything locally (same as CI), use `pytest -q -m ""`. To run
  only the e2e tests, use `pytest -q -m e2e`.
- As of 7/16/26, the full suite (`pytest -q -m ""`) has exactly 20
  pre-existing baseline failures unrelated to any in-session work —
  confirm a change hasn't introduced new failures by diffing against
  that count/list, not by expecting a clean run.

## Bot scripts

- **Once a scripted bot session built on `bot_client.py` (e.g. to drive
  the live server end-to-end for manual/exploratory verification, or to
  reproduce a bug live) actually works, keep it in `tools/` rather than
  a scratch/temp path.** These are cheap to re-run for future regression
  checks or as a reference for the next scripted session — see
  `tools/bot_horse_journey.py` for the established pattern/style to
  follow.
