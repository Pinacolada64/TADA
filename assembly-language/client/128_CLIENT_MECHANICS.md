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

(Superseded 2026-10-01: the 40-column dialogue now draws and scrolls
itself, like 80 columns, so it can keep a scrollback history -- see
"40-column scrollback in VDC RAM" below. The KERNAL window is the whole
screen and only matters to the input row's line editor now.)

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

Main RAM: history ring of 150 rows x (80 chars + 80 attributes), bank 0
`$6000-$8EDF` (chars) and `$9000-$BEDF` (attributes) -- RAM under the
BASIC ROMs (Guide figure 7-5). It started as 200 rows at `$4000`, back
when only the copy loops switched `$FF00` to `$0E`; since the Keymap
Editor moved in (below), the client runs with `$FF00` = `$0E` the whole
time, the program extends past `$4000`, and the ring moved up to make
room. `check_128_layout.py` (run by the build) fails if the program
reaches `$6000`.

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
  (20 rows -- the keymap's Page Up/Page Down, Alt + the grey arrows by
  default) redraws everything. Any other key, and any dialogue output,
  restores the saved live window. While scrolled back the status row
  shows "Scrollback: NNN of NNN -- CRSR: a line, Alt+Grey Up/Alt+Grey
  Down: a page", the page keys looked up in the keymap and named by the
  Keymap Editor's `describe_combo` (`sb_append_page_key`), so a
  rebinding shows there -- as it does in the startup banner and the
  online hint (`out_page_keys`).
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
- ~~No SwiftLink yet~~ -- see "SwiftLink" below; `fill` and `clock`
  stay as offline-demo commands. Server CLR (`$93`) handling is now
  reachable from real server text but not yet exercised by a test.
- ~~The 128 has no Page Up/Down keys~~ -- paging is now two bindable
  keymap actions (below), Alt + the grey top-row arrows by default;
  the old hardwired C= + CRSR paging is gone.

## 40-column scrollback in VDC RAM -- built 2026-10-01

In 40 columns the VDC isn't on screen, so its RAM is spare storage:
`vic_screen.asm` keeps the 40-column dialogue's scrollback history
there. A 40-column row is 80 bytes (40 screen codes, then 40 colors),
half an 80-column row's 160, so the same RAM holds twice the rows.

### VDC RAM size: `vdc_detect_ram` (`vdc.asm`)

A translation of "Fred's nifty program to determine size of 8563 dram"
(BASIC, via Ryan):

1. Save R28, set its bit 4 (DRAM type: 0 = 4416s/16K, 1 = 4164s/64K)
   so the chip drives 64K addressing.
2. Write `$55` to `$4200`; read `$4200` and `$4300`. Write `$AA` to
   `$4200`; read both again.
3. 16K chips ignore the address bit that separates the two, so `$4300`
   echoes both writes; on 64K chips it holds still. Only a double echo
   counts as 16K.
4. Restore R28 and call DLCHR (`$FF62`) from BANK 15 (`$FF00 = $00`,
   as BASIC does) to put the font back -- on 16K chips the probe write
   landed somewhere in VDC RAM. With BASIC's ROMs over `$4000-$BFFF`
   during that call, the routine has to live below `$4000`.

Carry set = 64K; `vdc_ram_64k` keeps the answer. In VICE 3.8, x128
`-VDC64KB` detects 64K, but `-VDC16KB` *also* says 64K: VICE bug #1981
("x128 always reports 64k" for this exact Twin Cities 128 test), fixed
in r45100 (April 2024), after 3.8 shipped. Under 3.8 a 16K session
therefore gets the 64K layout, whose ring wraps onto the save area and
font after ~50 rows -- a VICE-only problem. The test forces the 16K
layout by hand to cover it; real 16K detection still wants a flat 128
(or a newer VICE).

### Layout

| VDC RAM | Save area (live window) | History ring | Rows |
|---|---|---|---|
| 64K | `$1000-$172F` | `$4000-$FFFF` | 614 |
| 16K | `$0000-$072F` | `$0800-$3FFF` | 179 |

- **64K:** R28 stays in 64K addressing for the session. That reshuffles
  what the 16K layout left in VDC RAM, so `vic_screen_init` runs DLCHR
  again and blanks the VDC screen/attributes: an 80-column monitor left
  plugged in shows a clean empty screen, with the VDC's own screen,
  attributes and font (`$0000-$3FFF`) untouched after that.
- **16K:** only `$1000-$1FFF` is spare beside the screen and font (28
  rows after the save area), so this takes all 16K. The VDC display is
  garbage until the next reset -- nobody's looking at it in 40-column
  mode.

The ring position, count and offset are words here (614 > 255), unlike
`vdc_screen.asm`'s bytes; the status row reads "Scrollback: 001 of
614" (shorter than 80 columns' message, which wouldn't fit beside the
clock).

### Output and the view

`vic_putc` replaces CHROUT for 40-column dialogue: its own row, column,
color (VIC-II color number -- `dlg_color_codes` is already in VIC-II
order) and reverse flag, written straight into `SCREEN_RAM`/color RAM,
with the same control codes and deferred wrap as `dlg_putc`. A scroll
pushes row 0 to the ring (80 VDC writes) and moves rows 1-22 up with a
CPU copy (three pages + 112 bytes, screen and color together). CLR
pushes the rows in use first, as in 80 columns.

Scrollback: the first back key copies rows 0-22 into the save area;
every move then redraws all 23 rows from VDC RAM (ring rows and saved
rows alike, 1840 VDC reads); leaving copies the save area back. Same
keys as 80 columns -- CRSR UP/DOWN a line, the keymap's Page Up/Page
Down a page -- and output or any other key returns to the live view.

Knock-on changes in `client-128.asm`: `out_begin`/`out_end` are no-ops
on both screens (no window to narrow, no cursor/color to swap);
`set_window_narrow` is gone; `relocate_prompt` blanks the dialogue row
directly (`dlg_blank_cur_row`); the scrollback checks in
`editor_idle_hook`, `editor_key_hook` and `draw_status_row`, and the
keymap's Page Up/Down, go through mode dispatchers at the end of
`vic_screen.asm` (`sb_any_offset`, `sb_exit_any`, `scroll_key_hook`,
...). `vdc_screen.asm`'s own 80-column code is unchanged.

Test: `vice128_vic_scrollback_test.py` (both RAM sizes; the 16K run
also overruns the ring).

### Not done yet

- Real hardware: detection is only verified in VICE so far, and only
  the 64K answer (see the VICE 3.8 bug above) -- a flat 128 should
  report 16K, a 128DCR 64K.
- Since 40-column scrollback arrived, a keymap binding on plain CRSR
  UP/DOWN (the defaults' Home/End) is shadowed in 40 columns too, as it
  already was in 80.
- The bank-0 RAM ring 80 columns uses (`$6000-$BEDF`) sits idle in 40
  columns; it could add another 300 40-column rows if ever wanted.

## Keymap Editor -- built 2026-09-29

The C64 client's Keymap Editor popup, built into this client. It
started out built from the C64's own `keymap_menu.asm`; the same day
Ryan split the two -- separate editors and separate files -- so the 128
now has its own copy, free to diverge: the ALT modifier, Page Up/Page
Down, the 128's extra keys. The C64 client's `keymap_menu.asm`,
`keymap.asm` and `constants.asm` are back to what they were, and it
keeps `KEYMAP.CFG`. Tested by `vice128_keymap_test.py` (9/9), which
runs the client with a scratch `.d64` on drive 8, so `KEYMAP128.CFG`
really goes through KERNAL SAVE/LOAD.

### Files

- `keymap_menu_128.asm` -- the popup, forked from `keymap_menu.asm`
  (row for row, so the C64 file's comments still describe most of it).
  Adds Page Up/Page Down rows, ALT in the modifier names and masks, the
  128's key numbers 64-87 in `key_num_unshifted` (the grey arrows as
  pseudo-codes `$F0-$F3`, named "Grey Up" etc.), and saves
  `KEYMAP128.CFG`.
- `constants_128.asm` -- what the popup reads from its host: `KM_SHFLAG`
  (`$D3`), `KM_SFDX` (`$D4`), `KM_KEY_NONE` (88), `KM_MOD_MASK` (15:
  SHIFT/C=/CTRL/ALT).
- `keymap_host_128.asm` -- the nine `JT_*` entry points the popup calls,
  as real labels (the C64's jump table lives at `$C000`, ROM on the 128):
  save/restore screen, resume, status line, and the popup's cursor.
- `keymap_128.asm` -- `keymap_table` + `KEYMAP_TABLE_PTR`, the defaults,
  `init_keymap` (LOAD `KEYMAP128.CFG` or copy the defaults), and
  `km_dispatch`, which runs the actions on `input_editor.asm`
  (prev_word/next_word/home, a new `km_end`, macro text typed in through
  the editor's own `insert`/`cright`, Page Up/Page Down on the
  scrollback).

### `KEYMAP128.CFG`

17 slots of 27 bytes (modifier, key, action, 24 bytes of macro text):
0-5 the nav functions and the "open the editor" key (F7), 6-14 macros,
15-16 Page Up/Page Down (actions 6/7). Slots 0-14 match the C64's
`KEYMAP.CFG` layout, but the files are separate. Modifier bits: SHIFT 1,
C= 2, CTRL 4, ALT 8. Nav keys are GETIN bytes; macro triggers and the
page keys are matrix key numbers (`$D4`), captured by the popup's
`capture_macro_combo` -- the only way to tell the grey top-row arrows
(key numbers 83/84) from the main CRSR key, which GETIN reports
identically. Defaults: Page Up = ALT + grey up (83), Page Down = ALT +
grey down (84). ALT decodes as a modifier flag like SHIFT, so it sets
`$D3` bit 3 without taking `$D4`.

### Drawing in 40 and 80 columns

The popup is written for a 40x25 VIC-II screen and pokes `$0400`/`$D800`
directly.

- **40 columns:** it draws on the real screen. `JT_SAVE_SCREEN` backs up
  screen + colors to `$1300` (free RAM, "reserved for foreign language
  systems and function key software") and greys the colors, like the
  C64's `save_screen`.
- **80 columns:** the VIC screen still exists, it just isn't on the
  monitor. The popup keeps drawing there, and `km_present_tick`, run
  from the IRQ while the popup is open, copies VIC rows 2-23 to VDC
  columns 20-59, three rows per tick (a full pass every ~130 ms),
  translating colors through the editor's own table. A shadow copy at
  `$1300` means only changed cells are written, so an idle popup is
  just a compare loop. The dialogue is block-copied to the scrollback
  save area and greyed; closing block-copies it back.
- While the popup is open in 80 columns the IRQ owns the VDC: the status
  row goes to VIC row 23 (40 wide) instead, and `JT_RESTORE_SCREEN`
  stops the IRQ copy before touching the VDC itself.

### MMU and memory

The program ends past `$4000` (near `$4E70` with SwiftLink), so the
client sets `$FF00` = `$0E`
(RAM at `$4000-$BFFF`, I/O and KERNAL in) at startup and keeps it.
Checked against the ROMs first: the editor never writes `$FF00`, and the
KERNAL only does in save/restore pairs (INDFET/INDSTA used by LOAD/SAVE,
DMA, the IRQ/NMI/BRK stubs) or in JSRFAR/JMPFAR, which the client never
calls. The KERNAL IRQ runs `irq_handler` with `$FF00` = `$00`, so all
IRQ-reachable code and data sits before the popup include in
`client-128.asm`; `check_128_layout.py` fails the build if that part
crosses `$4000`.

### 128-specific keyboard fixes (`km_init_keyboard`)

- **Function keys:** the editor expands F1-F8 into strings ("LIST"+RETURN
  for F7) before GETIN sees a key, so the shared default "F7 opens the
  editor" could never fire. PFKEY (`$FF65`) reprograms F1-F8 to
  single bytes, the C64's own codes `$85-$8C`. BASIC's strings come back
  with a reset.
- **CTRL + main CRSR keys:** the 128's CTRL decode table (`$FB8B`) maps
  them to `$FF` -- the same KERNAL quirk the C64 client fixed. The
  editor reads its decode tables through RAM pointers at `$033E`
  (normal, shift, C=, CTRL, ALT, caps; SCNKEY `$C647`), so a RAM copy
  of the CTRL table with CRSR RIGHT/DOWN patched to `$1D/$11` is hooked
  in at `$0344`.
- LOAD/SAVE need `SETBNK` (`$FF68`) on the 128; `init_keymap` sets
  bank 0 for data and filename once, and the KERNAL keeps it.

### Key priority in `editor_key_hook`

Any key first clears a status message ("Saved keymap."). In 80 columns
plain (or SHIFTed) CRSR UP/DOWN scroll the dialogue a line
(`vdc_key_hook`); with C=, CTRL or ALT held they go to the keymap, like
every other key. Keys the keymap doesn't turn into Page Up/Page Down
then leave scrollback -- after the keymap, not before, or every Page Up
would snap back to the live view first and never page more than once
(`km_paged`). So the defaults' Home/End on plain CRSR UP/DOWN don't
work in either mode now (40 columns got scrollback 2026-10-01); CLR/HOME
still gives Home. Page Up/Page Down page the scrollback in both. The old hardcoded
CTRL+CRSR word jump in `input_editor.asm` is gone -- the keymap does
it.

### Bugs fixed on the way

- `prev_word` (from sliding-input.asm) moved two characters per step
  (`dec cpos` plus `jsr cleft`) and only tested every other one, so
  word-left jumped past spaces depending on word length. Rewritten as
  skip-spaces then skip-word, one `cleft` per character.
- `call_sliding_input` never reset `strlen`, so word-right on a fresh
  empty line after a submitted one spun forever.

### Not done yet

- ~~Output arriving while the popup is open must be held back~~ --
  it is, by construction: the popup is modal and only the line
  editor's idle hook drains `rx_buf`, so server bytes wait there
  (swiftlink.asm's RTS flow control holds the server off once it fills)
  until the popup closes. Not yet exercised live with a server talking
  while the popup is open.
- `read_error_channel` (in both clients' editors) loops until EOI, which
  never comes if no drive answers at all -- a real 128 or C64 with the
  drive switched off would hang on Save. Exiting on ST bit 7 too would
  fix it.
- The popup's F-key/CTRL fixes stay in place after the client exits.

## SwiftLink -- built 2026-09-29

Tested by `vice128_swiftlink_test.py` (8/8, 80 and 40 columns) against
its own `simple_server.py` on spare ports, with a JSON guest bot for the
mid-line case. `make vice128` now attaches the same emulated cartridge
(ACIA at `$DE00`, SwiftLink mode, NMI, IP232 to `SL_HOST:SL_PORT`).

- **Transport**: the C64 client's own `swiftlink.asm`, built with
  `{def: c128}`. The 128 KERNAL's NMI entry (`$FF05`, read out of
  kernal-318020-05.bin) already pushes A/X/Y and `$FF00` and sets
  `$FF00 = $00` before `jmp ($0318)`, and handlers leave through
  `$FF33` -- so the 128 variant skips the C64's own register saves and
  ends in `jmp $ff33`. `$FF00 = $00` puts BASIC ROM over `$4000+`, so
  the handler, `rx_buf` and its indexes sit below `$4000`
  (check_128_layout.py). The C64 build is byte-identical apart from its
  build timestamp.
- **Connect**: status row "Connecting... RUN/STOP to go offline" until
  the server's first byte or RUN/STOP. Offline = the old local demo
  (banner, echo, `fill`, `clock`, Keymap Editor) -- what the three older
  `vice128_*` tests now drive, after poking RUN/STOP.
- **Negotiation**: the 40/80 menu is shown until quiet (~0.25 s), then
  answered `8` on the VDC or `4` on the VIC-II, echoed after the menu's
  prompt. The server then records the Client Type as Commodore 128.
- **Receive while typing**: `input_editor.asm`'s key-poll loops call
  `editor_idle_hook`, which drains `rx_buf` to the dialogue (settles
  ~30 ms, max 256 bytes a go so typing never starves), then the editor
  redraws its line. 40 columns: `out_begin`/`out_end` swap the ESC-T/
  ESC-B window, cursor and text color between dialogue and input row.
  80 columns: nothing to swap; while scrolled back the bytes stay
  buffered instead of snapping the view to live.
- **Prompt on the input row**: once a drain settles, a partial dialogue
  line ending in `> ` (the server's prompts, pager prompts too) moves to
  the start of the input row and the editor's input area starts after
  it (`strcol`); RETURN echoes prompt + line into the dialogue. Port of
  tada-client.asm's relocate_prompt_to_row24/commit_input_line.
- **Framed streams** (`$01`, confirm, 16-bit length, body): Hourglass
  clock -> `clock_reset/putc/commit`; the login-time apply -> VIC-II
  border/background in 40 columns, VDC R26 background (via the editor's
  own VIC->RGBI table) in 80, blink speed either way; Video Settings and
  the canvas editor -> skipped with a cancel reply (`$01 $58/$43 $00
  $00`) so the server doesn't sit in `readexactly` until its timeout,
  plus a "(Popup not on the 128 client yet.)" note (Help gets the note
  only); SID music and `SID_STOP` -> skipped silently. `$8e` (uppercase
  charset) is dropped so CHR$(14) sticks.

### Not done yet

- A 128 Video Settings popup (and Help, canvas editor, SID playback).
- The login-time apply is untested live: guests don't get one, and the
  test has no saved account. Needs a real login.
- No disconnect/carrier detection, same as the C64 client.
- Disk I/O while online (Keymap Editor Save) with SwiftLink NMIs live
  hasn't been tried -- the C64 client needed the server quiet during
  KERNAL LOAD; the 128's fast serial may be pickier still. Pausing the
  ACIA (RTS off, RX IRQ off) around the KERNAL call would be the fix.
- Server text is displayed as-is in 40 columns (KERNAL CHROUT, quote
  mode cleared per byte) -- a server ESC-T/ESC-B would redefine the
  window. Only the Commodore 128 Client Type preset's ESC-Y/ESC-Z are
  expected today.

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
