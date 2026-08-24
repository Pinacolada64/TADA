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

## Open questions

- Does a real 128-native client want its own `Translation` enum member
  (distinct from plain PETSCII), or is reusing `Translation.PETSCII` +
  `ClientSettings.has_tab` (as today) sufficient once more 128-specific
  behavior lands? `network_context.py`'s research note: `has_tab` is
  currently the only persisted signal that distinguishes "this is
  probably a 128" from "this is a C64", and it's a Client-Type-preset
  side effect, not an explicit flag -- may be worth promoting to a real
  `is_c128`-style field if more features here end up gated on it.
- 80-column mode's VDC has its own separate character/color RAM the
  VIC-II 40-column path doesn't -- any 80-column-specific rendering work
  will need its own memory-layout section here once started, the same
  level of detail `CLIENT_MECHANICS.md` has for the C64 client's zero
  page/interrupt/SwiftLink layout.
