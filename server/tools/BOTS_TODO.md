8/8/26:
- Reduce code repetition across tools/bot_*.py scripts: move more of the
  shared plumbing (connect/login, terminal-type negotiation, draining the
  post-login News board, the "More" pager dance) into bot_client.py so
  individual bot scripts import it instead of re-implementing their own
  copy every time.
  - Concretely: bot_client.py already has `_handshake()` (answers the
    terminal-type prompt with 'A' for ANSI, hardcoded), but several
    scripts (e.g. tools/bot_ammo_carrier_check.py, tools/
    bot_stat_weapon_ally_check.py) define their own near-identical
    `_robust_recv()` to handle the News board's "More" pager prompt
    (which also contains '>', so a naive `_recv_all()`-style "stop at
    the first prompt with '>'" check stops there instead of at the real
    login/main prompt -- see tools/bot_stat_weapon_ally_check.py's
    docstring for how this bit a live run's `reload` command, which got
    silently swallowed as pager input and never actually executed).
  - tools/bot_stat_weapon_ally_check.py also had to write its own
    `_handshake_plain()` (copy-pasted from bot_client._handshake, just
    swapping 'A' for 'P') because the ANSI-vs-plain choice isn't a
    parameter on the shared helper.
  - Fix: give bot_client.py's `_handshake()` a `terminal_type` parameter
    (default 'A', but callers can pass 'P'), and export a shared
    `_robust_recv()` / `step()` pair that already knows how to dismiss
    the More pager, so new bot scripts don't reinvent this. Every
    existing bot_*.py that copy-pasted its own version should get
    migrated to the shared one as a follow-up cleanup pass, not just new
    scripts going forward.
  - tools/setup_bot_accounts.py (offline account seeding -- botdummy/
    botlasso/botdruid/railbender, run before a bot script connects) is a
    separate concern from this and doesn't need to change, but is worth
    remembering by name since "bot_account.py" gets misremembered for it.
