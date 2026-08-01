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
  were a display-hardware artifact, not a style to preserve. Don't churn
  untouched existing all-caps strings elsewhere just to convert them —
  but converting one *is* fine when it's actually asked for; just ask
  Ryan first rather than doing a drive-by sweep.

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

## SPUR source data

- **`D.LEVEL*.TXT` and `ROOM_LEVEL*.TXT` (in `../SPUR-data/`) are compressed
  GBBS message-database files, not plain text** despite the `.TXT`
  extension — reading them directly (`cat`, `Read`, a plain-text parser)
  gets you binary/7-bit-packed garbage, not room names/descriptions/exit
  data. Decompress them first with `tools/gbbsmsgtool.py`'s logic (also
  reimplemented inline in `../SPUR-data/level-2/tada_level_builder.py`'s
  `_decode_7bit()`/`_follow_chain()`/`extract_messages()`) to get anything
  meaningful out of them.
- **`../programming-notes/spur-variables.md` is the cross-reference for
  every scratch/global variable in `SPUR-code/*.S`.** Classic 1980s BASIC:
  short 1-2-letter (+digit, +`$`) names get reused for unrelated purposes
  across different subroutines, so the same variable can mean two
  different things depending which label you're reading. Check this file
  before assuming what a variable means from local context alone — and
  when porting work resolves a previously-uncertain entry (or turns up a
  variable the file doesn't cover yet), add the finding back into it, in
  the same alphabetical/style convention as the existing entries, so the
  reference stays authoritative rather than each session re-deriving it
  from scratch.

## Bot scripts

- **Once a scripted bot session built on `bot_client.py` (e.g. to drive
  the live server end-to-end for manual/exploratory verification, or to
  reproduce a bug live) actually works, keep it in `tools/` rather than
  a scratch/temp path.** These are cheap to re-run for future regression
  checks or as a reference for the next scripted session — see
  `tools/bot_horse_journey.py` for the established pattern/style to
  follow.
- **The JSON wire protocol's `ctx.prompt(...)` text arrives in the
  message's `"prompt"` field, never in `"lines"`.** `ctx.send(...)` text
  arrives in `"lines"`. A reactive bot pattern-matching on message text to
  decide when to reply (e.g. waiting for "Name your horse" or "Cast which
  spell number") must check `msg["prompt"]`, not `msg["lines"]`, for
  anything sent via `ctx.prompt()` — checking `lines` for prompt text
  silently never matches, since prompts are never in there. This bit a
  live bot session hard: `tools/bot_epic_battle.py`'s LASSO-naming and
  CAST-spell-number waits both checked `lines` for prompt text, so they
  never recognized the prompt at all, kept consuming an unrelated bot's
  ongoing fight broadcasts until their read budget ran out, and left the
  real prompt permanently unanswered — desyncing every command sent on
  that connection for the rest of the run. Grep a command's actual
  `ctx.prompt(...)` call before writing a bot wait condition for it,
  rather than guessing which field its text lands in.
