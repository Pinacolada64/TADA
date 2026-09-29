# TADA C128 client — planning stub

Just started: `client-128.asm` is an early skeleton (BASIC stub at the
native-mode load address `$1c01`, 40/80-column-switch detection, nothing
else wired up yet). Until this has enough scaffolding to be useful, a
real Commodore 128 still connects the same way a C64 does:
`Translation.PETSCII`, one of the "Commodore 128" Client Type presets
(`commands/prefs.py`'s `_client_type_presets()`, 40x25 or 80x25), driven
by `tada-client.asm` unmodified. This file is a running list of what a
real 128-native client could take advantage of that the C64 client
can't, to scope out before building more of one. Escape-code citations
are from
`Compute's 128 Programmer's Guide.pdf` (`/home/ryan/Documents/c128/`),
verified via `pdftotext -layout` against the actual escape-code table
(a naive extract scrambles the two-column layout and misattributes
letters to the wrong function -- don't trust an unverified re-extraction
of this table).

## Why a dedicated client at all

The 128 in native (128) mode has real KERNAL/screen-editor features the
C64 doesn't, all reachable via `CHR$(27)` (ESC) + a letter, the same
"press ESC then a key" mechanism BASIC 7.0's screen editor itself uses.
None of this applies in C64 mode (`GO 64`) or a 40-column PETSCII
session that's just reusing the C64 client unmodified.

## Feature wishlist

### 40/80 key detection at startup -> VIC vs VDC graphics

The 128 has two independent video chips: the VIC-II (40-column, same
chip the C64 uses, bitmap/sprite graphics as already exploited by
`tada_screen_blit_test.asm`'s double-buffering work) and the 8563 VDC
(80-column, its own 16-64K of dedicated display RAM, no sprites, but a
real hardware cursor and much more screen real estate for room text,
map overview, inventory, etc. side by side).

The 128's 40/80 DISPLAY key (a dedicated physical key, not a modifier
combo) is read at boot by the KERNAL and determines which chip powers
the primary screen -- a client could read that same startup state to
decide which graphics path to initialize, rather than asking the player
or assuming 40-column VIC-II behavior unconditionally the way the C64
client does today. Needs research: the exact zero-page/KERNAL flag the
128 startup code checks (not yet looked up here -- research before
implementing, same as the escape-code table above).

### WINDOW-based scroll region instead of screen-stash/restore

The C64 client's status-row/prompt-row mechanism works by manually
saving and restoring chunks of `SCREEN_RAM` around a fixed row (see
`CLIENT_MECHANICS.md`'s screen-stash discussion, and
`tada_screen_blit_test.asm`'s double-buffering exploration of the same
general problem: keeping a status/prompt row visually stable while the
dialogue area above it scrolls).

128 native mode has this built into the screen editor: `ESC-T` sets a
scroll window's top-left corner at the current cursor position, `ESC-B`
sets its bottom-right corner the same way -- two cursor-then-escape
steps define an arbitrary rectangular region that PRINT/scrolling
subsequently confines itself to (the BASIC-level equivalent is the
`WINDOW x1,y1,x2,y2[,clear]` statement, token $FE $1A, "Not available in
BASIC 2.0" -- i.e., 128-only, not on a C64). A window that excludes the
status/prompt row would make dialogue scrolling never touch those rows
at all, instead of stash/restore working around the fact that it does.

### Tab stops (ESC-Y / ESC-Z) -- first piece, server-side only

Not really "future client" work -- this is landing now on the *existing*
PETSCII-mode server side, since it only needs the C128's stock KERNAL
screen editor, already reachable from any C128 running the current
`tada-client.asm` unmodified:

- `ESC-Y` ("Define tab as eight spaces") -- the 128's only tab-enable
  code, hardcoded to an 8-column grid; there is no equivalent to a
  VT100's per-column `HTS`/`TBC` (set/clear stop at cursor) on this
  hardware at all, just this one global on/off.
- `ESC-Z` ("Clear tab") -- disables it.

Sent once at login (and live, if the player switches Client Type via
PREFS mid-session) whenever `ClientSettings.has_tab` is true (i.e., a
128 preset is selected) over a real `PETSCIINetworkContext` connection
-- see `commands/connect.py`'s existing border/blink-color raw-byte-at-
login precedent for the pattern this follows. Also forces
`tab_settings.has_tab_key = True` / `tab_width = 8` to match, since
those can't be anything else on real 128 hardware regardless of what a
player answered under PREFS 'K' before this existed.

### Raw SCREEN_RAM input-line redraw (tabled, not started)

`input_editor.asm` (the ported `sliding-input.asm` line editor -- see
its own header comment) currently draws the input line's contents and
blink cursor (`drwstr`/`rvson`/`rvsoff`) through `PLOT`/`CHROUT`, same
as any ordinary KERNAL text output. This has already caused two real,
live-confirmed bugs this session: `PLOT` needing the scroll window
already widened to reach `INPUT_ROW` (see the window-widen fix,
commit `31cdde8`), and printing a full-width line auto-wrapping/
scrolling the window on every single cursor movement (worked around by
capping `strwin` one column short of the full width rather than fixing
the underlying cause).

The C64 client's own `redraw_status_row`/`draw_status_row` sidestep
this entirely by poking `SCREEN_RAM` directly instead of going through
`CHROUT` at all -- no cursor-advance/wrap logic to trigger, no window-
boundary check to fail. Converting `drwstr`/`rvson`/`rvsoff` the same
way would remove this whole bug class (and be faster), and was
attempted 2026-08-24 -- assembled clean and verified byte-correct via
py65 disassembly, but live testing found a real, gradual 6502 stack-
pointer leak (confirmed via temporary instrumentation: SP drifted from
`$F0` to `$EA` over roughly 124 keystrokes) that eventually corrupted
state badly enough to crash the whole client back to BASIC. Root cause
wasn't found before the attempt was reverted -- see
[[project_c128_client]]'s memory entry for the live-debugging story
(breakpoints kept wedging VICE's remote monitor, had to fall back to
SP-snapshot instrumentation instead) and its own suspicion that
`next_word`/`prev_word`'s nested `jsr cright`/`jsr cleft` loops or
`exkey`'s self-modified `jsr $ffff` dispatch are the most likely
places an imbalance could hide, since neither was individually
re-verified before the revert.

**If this gets picked up again**: budget real time for careful,
incremental verification (convert one routine at a time, live-test
between each, rather than rewriting all three together the way the
first attempt did), and reuse the existing `SCREEN_RAM+INPUT_ROW_OFFSET`
`{const:}` convention `draw_status_row` already established rather than
inventing a new addressing approach.

## 80-column (VDC) text output -- built 2026-09-29

`vdc.asm` (8563 primitives) and `vdc_screen.asm` (dialogue output,
history, scrollback view). Same row layout as 40 columns: dialogue rows
0-22, status row 23, input row 24. Tested by `vice128_vdc_test.py`
(x128 `-80col -VDC16KB`, reads VDC RAM through the monitor's
`bank vdc`, 8/8 passing).

### How the editor ROM drives the VDC (research)

Disassembled from VICE's `C128/kernal-318020-05.bin` ($C000-$FFFF)
rather than recalled; the Programmer's Guide only documents the register
handshake and the fill command.

- **Register access** -- `$CDCC`: `stx $d600` / `bit $d600` / `bpl`
  (wait for bit 7, ready) / `sta $d601`. `$CDDA` is the read twin.
  `$CDCA`/`$CDD8` are the same with X preset to 31 (the data register).
  `$CDE6`/`$CDF9` set R18/R19 (the update address) from the editor's
  line pointers `$E0`/`$E2` + Y.
- **Moving a line** (scrolling) -- `$C40D`, 80-column branch at `$C436`:
  set R24 bit 7 (COPY), R18/R19 = destination, R32/R33 = source, then
  write R30 = byte count, which starts the copy inside the chip. Again
  for the attributes. The editor scrolls a window one line at a time
  this way (`$C3DC` loop), so it works for any window margins. (If CTRL
  is held, `$C3F7` adds a delay after each scroll -- the "slow scroll"
  feature.)
- **Clearing a line** -- `$C4A5`/`$C4C0`: R24 bit 7 clear (WRITE, i.e.
  fill), R18/R19 = start, write one byte to R31, then R30 = count-1
  repeats it. `$C53E` then reads R18/R19 back and writes one more byte
  at a time until the address reaches the end. `vdc_fill` keeps that
  check.
- **No IRQ involvement** -- the editor IRQ (`$C194`) does the VIC raster
  split, SCNKEY, and the 40-column cursor blink (`$C6E7`), which returns
  at once when `$D7` bit 7 (80 columns active) is set. Nothing on the
  IRQ side touches `$D600`, and the editor doesn't SEI around VDC
  access either. Future NMI/IRQ tasks (SwiftLink) must stay off the
  VDC for this to hold.
- **Editor state** -- `$D7` bit 7 = editor on the VDC (used instead of
  the `$D505` switch bit, since ESC-X can swap screens after reset);
  `$0A2E`/`$0A2F` = VDC screen/attribute base high bytes (`$00`/`$08`);
  `$F1` = current attribute. After `CHR$(14)`, `$F1` = `$87` (ALT bit 7
  selects the lowercase half of the 512-character VDC set, plus color
  7). R10 = `$20` turns the hardware cursor off (`$CDAE`).
- **Colors** -- PETSCII color codes at `$CE4C` (VIC order), VDC RGBI
  values at `$CE5C`: `00 0f 08 07 0b 04 02 0d 0a 0c 09 06 01 05 03 0e`.
  Note dark grey = `$06`, grey = `$01`; I'd recalled them the other way
  round and only the ROM caught it.
- **Keys** -- decode tables at `$FA80` (normal), `$FAD9` (shift),
  `$FB32` (C=), `$FB8B` (CTRL), `$FBE4` (caps lock). The top-row arrow
  keys (key numbers 83-86) give `$91/$11/$9d/$1d` in every table, so
  modifiers only show up in `$D3`. The main CRSR key gives `$ff` under
  CTRL (why CTRL+main CRSR never worked for word jump) and `$91` under
  SHIFT or C=.

### Memory map

VDC RAM (16K, stock flat 128): `$0000` screen, `$0800` attributes,
`$1000`/`$1800` scrollback's saved copy of the live dialogue window
(1840 bytes each), `$2000` character set. Every attribute sits `$0800`
above its character, both in the live screen and in the save area.

Main RAM: history ring of 200 rows x (80 chars + 80 attributes), bank 0
`$4000-$7E7F` (chars) and `$8000-$BE7F` (attributes) -- RAM under the
BASIC ROMs, reached by setting `$FF00` = `$0E` (I/O + KERNAL in, BASIC
out; Guide figure 7-5) only inside the copy loops. The client code must
stay below `$4000` for this (today it ends near `$2B00`); if it grows
past that, move `HIST_CHARS_HI` up and shrink `HIST_LINES`.

### Output, history and the scrollback view

- `dlg_putc` keeps its own row/column and writes the VDC directly
  (screen code + attribute per character). It handles CR, RVS on/off,
  CLR, HOME and the 16 color codes. Wrap is deferred, so an exactly
  80-character line followed by CR doesn't leave a blank row.
- Scrolling = two block copies (1760 chars, 1760 attributes) plus a
  fill of row 22. Before each scroll, the top row is read back out of
  VDC RAM into the history ring. CLR first saves every row in use to
  history.
- Scrollback: the first CRSR UP block-copies the live window to the
  save area. Rows above the offset come from history (CPU copy); the
  rest come from the save area (block copy). A one-line step shifts the
  window by block copy (bottom-up, row by row, when moving down: the
  chip only copies upward through memory) and draws one new row. A page
  (C= + CRSR, 20 rows) redraws everything. Any other key, and any
  dialogue output, restores the saved live window. The status row shows
  "Scrollback: NNN of NNN" while scrolled back.
- Speed in x128 at 1 MHz: about 38 scrolled lines/sec (~26 ms per line,
  most of it waiting on the block copies). FAST (2 MHz) mode is an easy
  doubling for the CPU part if it's ever needed, since the VIC screen
  isn't used in 80 columns.

### Not done yet / ideas

- A 64K VDC (C128DCR) could hold ~300 history rows in VDC RAM itself
  (`$4000-$FFFF`) and draw scrollback entirely by block copy, no CPU
  bytes at all -- needs R28 bit 4 (DRAM type) detection and a charset
  reload. The main-RAM ring works on every 128, so it came first.
- VDC hardware scrolling (R12/R13 display start) can't split the
  screen, so it can't keep rows 23/24 still -- not usable here.
- No SwiftLink yet: `fill` and `clock` are local stand-ins for server
  output. Server CLR (`$93`) handling is written but only reachable
  once real server text arrives.
- The 128 has no Page Up/Down keys. If C= + main-keyboard CRSR paging
  (back only) proves awkward, reprogramming F-key strings via PFKEY to
  single bytes would free up F1-F8 as plain keys.

## Open questions

- Does a real 128-native client want its own `Translation` enum member
  (distinct from plain PETSCII), or is reusing `Translation.PETSCII` +
  `ClientSettings.has_tab` (as today) sufficient once more 128-specific
  behavior lands? `network_context.py`'s research note: `has_tab` is
  currently the only persisted signal that distinguishes "this is
  probably a 128" from "this is a C64", and it's a Client-Type-preset
  side effect, not an explicit flag -- may be worth promoting to a real
  `is_c128`-style field if more features here end up gated on it.
- ~~80-column mode's VDC memory layout~~ -- see "80-column (VDC) text
  output" above.
