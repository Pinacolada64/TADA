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

## Monetary standard

- **This port is moving off SPUR's gold standard onto a silver standard** —
  player-facing currency language (and, going forward, new/rewritten code)
  should say "silver" rather than "gold". Other period-accurate complementary
  denominations (copper, etc.) may be introduced later, so don't assume
  silver is the only unit forever — but for now, treat "gold" as the term
  being phased out.
- **Whenever "gold" is encountered going forward, change it to "silver"** —
  in new player-facing strings, in code you're touching anyway (variable
  names, messages, comments), and in fresh porting work from the SPUR BASIC
  source. This is a live, in-progress rename, not a one-time sweep: don't go
  do a drive-by pass converting every untouched "gold" reference across the
  codebase in one shot — ask Ryan before a repo-wide sweep — but any file you
  are already editing for other reasons should get its "gold" references
  updated to "silver" as part of that edit.

## Player data

- **New player log/stat field → chat with Ryan about an editplayer entry.**
  Whenever a new persisted per-player statistic gets added (e.g. a win/loss
  counter, a history list, a new tracked total), don't silently leave it
  un-editable — bring up with Ryan where it should live in
  `commands/editplayer.py`'s menus before considering the field done.

## Testing

- **Always use `.venv`, never the bare system `python3`.** Run tests (and
  any other Python invocation in this repo) via `.venv/bin/python3 -m
  pytest ...` or activate it first (`source .venv/bin/activate`) — don't
  fall back to a bare `python3`/`pytest` from PATH. The system
  interpreter is missing `colorama` and `cbmcodecs2`, which `.venv` has
  installed; running outside `.venv` produces hundreds of spurious
  `ModuleNotFoundError` failures/collection errors that look like real
  regressions but aren't. If `.venv` doesn't exist yet, set it up rather
  than working around the missing packages.
- **Local runs skip e2e tests by default.** `pyproject.toml`'s `addopts`
  already includes `-m "not e2e"`, so a plain `pytest` / `pytest -q` (no
  extra flags) finishes in ~20s instead of ~60-130s. The 6 tests marked
  `@pytest.mark.e2e` start a real `Server` and real sockets
  (`tests/e2e/test_abrupt_disconnect.py`, `tests/e2e/test_duel_disconnect_forfeit_e2e.py`,
  `tests/e2e/test_graceful_shutdown.py`, `tests/e2e/test_network_e2e_real_login.py`,
  `tests/e2e/test_network_e2e_reconnect.py`, `tests/movement/test_move_south_room1.py`).
  CI (`.github/workflows/ci.yml` and `e2e-tests.yml`) overrides with `-m ""`
  so pushes/PRs still cover them.
- To run everything locally (same as CI), use `pytest -q -m ""`. To run
  only the e2e tests, use `pytest -q -m e2e`.
- As of 8/13/26, the full suite (`pytest -q -m ""`) passes clean: 4149
  passed, 2 skipped, 0 failures (the 20 pre-existing failures noted as
  of 7/16/26 are gone — confirm against a fresh run rather than trusting
  this count going stale again). A clean run is now the expectation; a
  failure means investigate, not "matches baseline."

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

## Server operations

- **Before restarting the live server, show Ryan the `who` command's output**
  so he can see who (if anyone) is currently connected before it happens.
  Connect as admin (bot_client.py, same pattern as tools/bot_config_check.py)
  and run `who`, then report those results, before stopping/restarting the
  `tada` screen session's `run_server.py` process.

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

## C64 keyboard matrix / SFDX key-number layout

- **`SFDX` ($cb, keyboard_rollover.asm's own live "matrix coordinate of
  the key currently held") uses the SAME canonical 0-63 "key-number"
  order as the stock KERNAL's own unshifted keyboard-decode table** —
  confirmed 2026-09-22 by reading the actual table bytes straight out
  of `~/Documents/c64/JiffyDOS/Jiffydos-Kernal.rom` (offset 2945) rather
  than trusting recalled references (a real PDF, "Mapping the Commodore
  64," is also available in `~/Documents/c64` if the ROM ever isn't
  handy — reading the ROM directly turned out to be just as easy and
  is authoritative for *this exact* KERNAL, JiffyDOS included, not just
  a stock one). $40 = no key held. Table (index, key, unshifted
  PETSCII/screen byte):
  ```
   0 INST/DEL     $14    16 5            $35    32 9            $39    48 POUND        $5c
   1 RETURN       $0d    17 R            $52    33 I            $49    49 *            $2a
   2 CRSR RIGHT   $1d    18 D            $44    34 J            $4a    50 ;            $3b
   3 F7           $88    19 6            $36    35 0            $30    51 HOME/CLR     $13
   4 F1           $85    20 C            $43    36 M            $4d    52 RIGHT SHIFT  $01*
   5 F3           $86    21 F            $46    37 K            $4b    53 =            $3d
   6 F5           $87    22 T            $54    38 O            $4f    54 UP ARROW     $5e
   7 CRSR DOWN    $11    23 X            $58    39 N            $4e    55 /            $2f
   8 3            $33    24 7            $37    40 +            $2b    56 1            $31
   9 W            $57    25 Y            $59    41 P            $50    57 LEFT ARROW   $5f
  10 A            $41    26 G            $47    42 L            $4c    58 CTRL         $04*
  11 4            $34    27 8            $38    43 -            $2d    59 2            $32
  12 Z            $5a    28 B            $42    44 .            $2e    60 SPACE        $20
  13 S            $53    29 H            $48    45 :            $3a    61 COMMODORE    $02*
  14 E            $45    30 U            $55    46 @            $40    62 Q            $51
  15 LEFT SHIFT   $01*   31 V            $56    47 ,            $2c    63 RUN/STOP     $03
  ```
  `*` = an internal KERNAL modifier-flag byte, not a real PETSCII
  character (SHIFT/CTRL/CBM keys have no "unshifted char" of their
  own). **RETURN is key-number 1, RUN/STOP is key-number 63** — the two
  constants that actually mattered for the keymap editor's macro-
  trigger capture (`keymap_menu.asm`'s `capture_macro_combo`, rejecting
  RETURN as a bindable trigger and canceling capture on RUN/STOP),
  needed because GETIN's own *decoded* byte collides two different
  physical keys onto the same value (CTRL+M and a bare RETURN both
  decode to `$0d`) in a way SFDX's matrix position never does.
- To re-derive or extend this table (e.g. the shifted/Commodore-key
  decode tables) directly from a ROM file: search for a byte run
  matching the expected sequence (fuzzy-match is fine — the 4
  modifier-key slots above are typically the only mismatches against a
  hand-built reference, since their real ROM bytes are internal flag
  values rather than 0). See this memory's own commit history / the
  2026-09-22 session for the exact Python one-liner used.

## GitHub CLI

- **`gh pr edit` errors on this repo** with `GraphQL: Projects (classic)
  is being deprecated ... (repository.pullRequest.projectCards)` and the
  edit silently does not apply (e.g. `--body-file` leaves the PR's body
  unchanged) — confirmed live 2026-09-19 editing PR #53's description.
  Use the REST API directly instead: `gh api repos/<owner>/<repo>/pulls/
  <n> -X PATCH -f "body=$(cat file.md)"` (note: `-f body=@file.md` does
  NOT read the file the way curl's `@` syntax does — it sets the field
  to the literal string `@file.md` — use command substitution instead).
