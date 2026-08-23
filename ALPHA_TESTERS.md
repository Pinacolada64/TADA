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
