# Alpha Tester Bug Log

Bugs reported by alpha testers that aren't reproduced/confirmed yet, tracked
here until someone gets a solid repro and either fixes them or rules them out.

## Open

### PREFS 'h<key>' help text needs mixed-case letters to trigger (PETSCII)

- **Reported by:** tester, secondhand via Ryan (2026-08-22)
- **Symptom:** tester said they needed to type in mixed case (e.g. "hX") to
  trigger a prefs option's help text at the PREFS 'h<key>' prompt
  (`server/commands/prefs.py`). No exact repro steps, client, or which case
  combos worked/failed.
- **Investigation so far:** audited the PETSCII input path
  (`server/network_context.py`'s `_petscii_input_to_ascii()`) and
  `commands/prefs.py`'s `h<key>` matching (and its submenus) --
  `ans = raw.strip().lower()` is applied before every comparison, so case
  should already be normalized away. No server-side bug found.
- **Leading theory:** client-side keyboard scan/rollover quirk on real
  hardware (shift-transition between two quick keypresses mis-scanned),
  not a server logic bug -- speculative, not confirmed. Possibly related
  to the in-progress N-key-rollover work on
  `feature/c64-prompt-row-status-bar`
  (`assembly-language/3-key-rollover-source.asm`,
  `assembly-language/client/tada-client.asm`).
- **Next step:** get a precise repro from the tester (exact keys/case typed,
  exact client/hardware, exact prefs option) before investigating further.

### `ctx.prompt()` prompt text needs to stay short or it overflows narrow columns

- **Reported by:** Ryan (2026-08-22)
- **Symptom:** `ctx.prompt(prompt_text, preamble_lines=...)` calls (e.g. in
  `server/commands/prefs.py`) don't wrap/truncate `prompt_text` itself --
  it's appended to `' > '` and written on one line. Anything over ~40
  characters can run past a narrow client's column width instead of
  wrapping, unlike `preamble_lines`, which does go through normal line
  formatting/wrapping.
- **Rule of thumb going forward:** keep `prompt_text` short (fits well
  within the narrowest supported width); move any longer explanatory text
  into `preamble_lines` instead, which wraps properly.
- **Narrowest supported width:** Ryan's recollection is a 22-column
  minimum, but `commands/prefs.py`'s `_MIN_COLS` is actually **20**
  (`_MIN_COLS, _MAX_COLS = 20, 132`, `commands/prefs.py:952`) -- worth
  double-checking which number is authoritative before relying on either.
- **Next step:** confirm whether `ctx.prompt()` should gain real wrapping/
  truncation for `prompt_text` itself, or whether "keep it short" is
  sufficient going forward; audit existing `ctx.prompt()` call sites for
  ones already over the limit.

### More Prompt doesn't trigger when output is split across separate `send()` calls

- **Reported by:** Ryan (2026-08-22)
- **Symptom:** if a command's output comes from two (or more) separate
  `ctx.send()` calls -- e.g. one function handling a help request, then
  immediately displaying a menu right after -- and each individual call is,
  say, 20 lines, More Prompt never triggers even though the *combined*
  output (40 lines) should exceed the page size and pause.
- **Root cause (confirmed by reading the code):**
  `network_context.py`'s `_wants_pagination()` (`:175-181`) checks
  `len(formatted) > page_size` against the lines passed to *that single*
  `send()` call only. `send()` (`:149`) and `_wants_pagination()`/
  `_paginate()` have no memory of previous `send()` calls within the same
  command, so pagination is decided per-call, not per-command-turn --
  two 20-line `send()` calls in a row each individually stay under
  `page_size` and both go out unpaginated even on a `screen_rows` small
  enough that their sum should have paginated.
- **Proposed fix direction:** accumulate output across a command's multiple
  `send()` calls and only decide on/apply pagination once, against the
  combined total, at the end of the command's dispatch -- semantically
  sound, and matches how a real terminal's "screenful" concept should work
  (it's the player's cumulative unread output that matters, not which
  function happened to emit which lines).
  - **Recommended approach: buffer inside `GameContext`.** Keep every
    command's `ctx.send()` call sites exactly as they are today -- no
    command code changes. `GameContext` itself quietly appends each
    `send()` call's lines to an internal per-turn buffer instead of
    sending immediately, then flushes/paginates the combined buffer once
    at the natural end-of-turn point (next `ctx.prompt()` call, or an
    explicit end-of-dispatch flush). Lowest-risk option since it's
    contained entirely inside `network_context.py`.
  - **Alternative considered: generators.** Command handlers could
    `yield` lines instead of `await ctx.send(...)`, letting a wrapper one
    level up collect everything yielded and paginate once. Rejected as
    the lead approach -- it's a broad, systemic rewrite of every command
    handler's control flow for no benefit over the buffering approach
    above, which gets the same combined-pagination result without
    touching command code at all.
  - Need to make sure a genuinely long-running command that WANTS
    incremental output *while it runs* (e.g. combat round-by-round text)
    doesn't get held back until the very end -- may need an explicit
    "flush now" escape hatch, or a size/time threshold, rather than
    buffering unconditionally until the command fully returns.
- **Next step:** unscoped -- needs a design decision on the buffering
  approach above before implementation.
