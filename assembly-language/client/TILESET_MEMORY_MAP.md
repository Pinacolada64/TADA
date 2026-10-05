# Tileset editor -- memory map (design draft, 2026-10-02)

Status: **design only, nothing built.** This maps where an RPG tileset
(16x16-pixel tiles, 2x2 characters each), sprites, and a tile/text
raster split would live in both clients, on top of what each client
already uses today. Addresses marked *existing* were read from the
source/symbol files on `feature/drive-scan` (2026-10-02); everything
marked *proposed* is new.

Decisions so far (Ryan, 2026-10-02):

- **Multicolor tiles** (8x16 double-wide pixels per 16x16 tile, 4
  colors per char).
- **Tiles go on the VIC screen on both machines.** On the 128 that
  means 40-column mode. The VDC isn't used for tiles, so the VDC
  section below is kept only as reference.
- **The editor is a loadable module on both machines**, not resident.

First conversion tests: see [Art conversion](#art-conversion) below and
`tiles/tile_convert.py`.

Contents:

1. [C64: CPU view](#c64-cpu-view)
2. [C64: VIC bank 3 view](#c64-vic-bank-3-view)
3. [C64: `$d018` values](#c64-d018-values)
4. [C64: raster split](#c64-raster-split)
5. [Art conversion](#art-conversion)
6. [C128 80-column: VDC RAM](#c128-80-column-vdc-ram) (reference only)
7. [C128: main RAM](#c128-main-ram)
8. [C128 40-column (VIC)](#c128-40-column-vic)
9. [Open questions](#open-questions)

---

## C64: CPU view

`$01` stays `$37` (BASIC, KERNAL, I/O all in) except during
`switch_to_bank3_with_charset`'s one-time boot copy.

| Range | Size | Use | Status |
|---|---|---|---|
| `$0000-$00ff` | 256 | Zero page. Client owns only `$f9/$fa` (`rx_head`/`rx_tail`) and `$fb/$fc` (`scr_ptr`) | existing |
| `$0100-$03ff` | 768 | Stack, KERNAL work area, vectors (`$0314` IRQ, `$0318` NMI hooked) | existing |
| `$0400-$07ff` | 1K | Stock screen. **Unused**: the VIC shows bank 3. CPU-only scratch, invisible to the VIC | free |
| `$0801-$26ff` | ~7.9K | Resident client code + data | existing |
| `$2700-$27ff` | 256 | `rx_buf`, the NMI receive ring | existing |
| `$2800-$28ff` | 256 | `sid_buf`, SID stream buffer | existing |
| `$2900-$30ff` | 2K | `gothic_charset` image. It's copied to `$d000` at boot, then reused as `BACKUP_CHARS`/`BACKUP_COLORS` (popup screen save) | existing |
| `$3100-$37ff` | 1.75K | Margin under `OVERLAY_BUF` (`check_overlay_margin.py` guards it) | free |
| `$3800-$4cb0` | 5.2K | `OVERLAY_BUF`: one overlay at a time. Largest today is `keymap_menu` (to `$4cb0`); `petscii_editor` ends at `$4887` | existing |
| `$3800-$4fff` | ~6K | **Tile editor overlay** (`TILEEDIT.PRG`), loaded like `PETSCII.ED`. Loadable on both machines (decided 2026-10-02). It can grow to `$8fff` if needed; the working copy below would move up with it | proposed |
| `$5000-$57ff` | 2K | **Tile editor working copy** of the live tileset (the editor reads this, never `$e000`) | proposed |
| `$5800-$8fff` | 14K | Free | free |
| `$9000-$905f` | 96 | `BORDER_STATE`: Border style flag + Gothic box-glyph backup. Kept above every overlay (`check_overlay_margin.py --modules` guards it), so the tile editor must end below `$9000` | existing (PR #64) |
| `$9060-$9dff` | ~3.4K | Free | free |
| `$9e00-$9fff` | 512 | Where the KERNAL puts RS-232 buffers if device 2 is ever opened. Avoid | avoid |
| `$a000-$bfff` | 8K | BASIC ROM; RAM underneath. **Tileset library** (up to 4 sets x 2K): writes go straight through, reads need `$01=$36`. That's NMI-safe because the KERNAL stays mapped | proposed |
| `$c000-$c038` | 57 | `JT_BASE` jump table, `PROTO_TABLE`, `KEYMAP_TABLE_PTR`, `CONFIG_SETTINGS_PTR`, `JT_SET_BORDER_STYLE` (`$c036`, PR #64) | existing |
| `$c039-$c3ff` | ~970 | Unclaimed today. Leave it as growth room for the jump table (the tile editor will want entries here, e.g. raster split on/off) | reserve |
| `$c400-$c7ff` | 1K | `SCREEN_BUF_A`. Sprite pointers at `$c7f8-$c7ff` | existing / proposed ptrs |
| `$c800-$cbff` | 1K | `SCREEN_BUF_B`. Sprite pointers at `$cbf8-$cbff` | existing / proposed ptrs |
| `$cc00-$cfff` | 1K | **Sprite blocks 48-63** (16 shapes) | proposed |
| `$d000-$d7ff` | 2K | I/O to the CPU; RAM underneath holds the VIC's copy of `gothic_charset` (text font) | existing |
| `$d800-$dfff` | 2K | Color RAM / CIA / SwiftLink `$de00` to the CPU. RAM underneath is VIC-visible but needs `$01=$34` to write. **Avoid** | avoid |
| `$e000-$e7ff` | 2K | **Tile charset A** (RAM under KERNAL) | proposed |
| `$e800-$efff` | 2K | **Tile charset B** (second set / animation frame), *or* sprite blocks 160-191 | proposed |
| `$f000-$f7ff` | 2K | **Sprite blocks 192-223** (32 shapes) | proposed |
| `$f800-$ffbf` | ~2K | Sprite blocks 224-254, spare | proposed |
| `$ffc0-$ffff` | 64 | Block 255. Holds the RAM-side `$fffa-$ffff` vectors. **Never use** | avoid |

**Why `$e000`+ for VIC data:** the CPU *writes* to `$a000-$bfff` and
`$e000-$ffff` always reach the RAM underneath, whatever `$01` is set to.
Only *reads* need banking. So updating the tile charset or sprite shapes
never has to change `$01`, and the SwiftLink NMI never meets a missing
vector. `$d800` would need `$01=$34`, which pages out the KERNAL's NMI
vector. That's the same hazard the boot copy avoids by running before
`init_nmi`.

---

## C64: VIC bank 3 view

`$dd00` bits 0-1 = `00` (bank 3, `$c000-$ffff`). The VIC always reads
RAM here; character ROM isn't visible in bank 3.

```
VIC rel  absolute   1K slot  2K char slot   use
$0000    $c000      0        0              JT / proto (CPU data, not shown)
$0400    $c400      1        |              SCREEN_BUF_A
$0800    $c800      2        1              SCREEN_BUF_B
$0c00    $cc00      3        |              sprites 48-63
$1000    $d000      4        2              gothic_charset  (text)
$1800    $d800      6        3              (avoid)
$2000    $e000      8        4              TILE CHARSET A
$2800    $e800      10       5              TILE CHARSET B / sprites 160-191
$3000    $f000      12       6              sprites 192-223
$3800    $f800      14       7              sprites 224-254 / spare
```

Sprite pointer value = `(address - $c000) / 64`. It has to be written
into **both** screen buffers' pointer bytes (`$c7f8+n` and `$cbf8+n`),
because `flip_screen_buffer` swaps which one the VIC reads.

### Tile charset layout (256 chars = 64 tiles)

Tile *t* (0-63) uses chars `4t .. 4t+3` in reading order: top-left,
top-right, bottom-left, bottom-right. Drawing a tile at cell (x, y)
pokes `4t` and `4t+1` into row y, and `4t+2` and `4t+3` into row y+1.
That's what `tile_convert.py` writes today.

**Better (proposed): a tile table with shared chars.** Real tiles repeat
quarters a lot (plain grass, water, wood grain). In the first test, 62
tiles = 248 char slots held only **139 distinct chars** (char + color
RAM value). A tile table maps each tile to its 4 char codes (and 4
color RAM values), so identical quarters are stored once and one 2K
charset fits roughly **100+ tiles**. Costs 8 bytes per tile (4 chars +
4 colors): 1K for 128 tiles, in normal RAM. Drawing reads the table
instead of computing `4t`.

Reserved slots (proposed):

| Chars | Tile # | Reserved for |
|---|---|---|
| `$20-$23` | 8 | Blank tile. Char `$20` must stay blank so a space row reads the same in both charsets (the divider row, below) |
| `$a0-$a3` | 40 | Divider: char `$a0` solid (`$ff` bytes), like the ROM font's reverse space, so a row of it in color 0 is solid black in both charsets and both modes (added 2026-10-03 with the editor) |
| `$fc-$ff` | 63 | Cursor / selection-frame tile for the editor |

That leaves **61 user tiles per charset** (122 using both `$e000` and
`$e800`).

### Color (multicolor -- decided)

Each 8x8 char has 4x8 double-wide pixels, and each pixel's bit pair
picks one of 4 colors:

| Bits | Color | Scope |
|---|---|---|
| `00` | `$d021` background | whole tile region |
| `01` | `$d022` | whole tile region |
| `10` | `$d023` | whole tile region |
| `11` | color RAM, low 3 bits (0-7) | per char |

Color RAM bit 3 must be set (value 8-15) for a cell to display as
multicolor. Needs `$d016` bit 4 set for the tile region only, so the
split also toggles `$d016`. Colors 8-15 (orange, brown, light red, the
greys, light green, light blue) can only appear through the three
shared registers. That's the main constraint the art runs into (see Art
conversion).

Per-tile colors are stored beside the pixel data (4 bytes per tile, one
per quarter; 256 bytes per set). Drawing a tile writes color RAM as well
as screen RAM.

---

## C64: `$d018` values

Screen nibble (bits 4-7): A = `$c400` -> 1, B = `$c800` -> 2.
Char bits (1-3): text `$d000` -> 2 (`$04`), tiles A `$e000` -> 4
(`$08`), tiles B `$e800` -> 5 (`$0a`).

| | text (`$d000`) | tiles A (`$e000`) | tiles B (`$e800`) |
|---|---|---|---|
| Screen A | `$14` (= today's `VIC_D018_INIT`) | `$18` | `$1a` |
| Screen B | `$24` | `$28` | `$2a` |

**Required change:** `flip_screen_buffer` currently does a
read-modify-write of the live `$d018` and keeps its char bits. Under a
split, the live char bits depend on where the raster happens to be. The
flip has to update two **shadow** bytes instead (`d018_top`,
`d018_bottom`), and the raster IRQs write those.

---

## C64: raster split

Visible text row *r* starts on raster line `51 + 8r` (`$d011` YSCROLL
= 3, the default). A raster line is 63 cycles on PAL, 65 on NTSC (64 on
old NTSC). On the first line of each row (the badline) the VIC takes
about 40 of them away from the CPU.

### Proposed game-view layout (one option)

```
row  0-15   tile viewport: 20 x 8 tiles     [tile charset, MC on]
row  16     divider, blank or char $20s     [switch happens in here]
row 17-22   dialogue (6 rows)               [gothic text, MC off]
row  23     status   (STATUS_ROW)
row  24     prompt   (PROMPT_ROW)
```

The dialogue window shrinks from 23 rows to 6 while the map is up. A
12-row viewport (6 tiles tall) gives back 4 more dialogue rows. Note
that the status row floats up (`STATUS_ROW_FLOOR` = 21) when input
wraps. The split row must sit above anything that moves.

### Two raster IRQs per frame

| Raster line | When | Writes |
|---|---|---|
| `51 + 8*16 = 179` (`$b3`) | Start of divider row | `$d018 <- d018_bottom` (text), `$d016` MC off, `$d021` text bg |
| `251` (`$fb`) | Bottom border, after row 24 | `$d018 <- d018_top` (tiles), `$d016` MC on, `$d021` map bg |

The divider row gives the first write **8 raster lines (~500 cycles)
of slack**. The write only has to land somewhere inside a row whose
glyphs look the same in both charsets. Without a divider, it has to land
in the single line between row 15's last pixel line and row 16's first.

### Interrupt priority and jitter

```
NMI  (SwiftLink RX)  -- can't be masked; preempts everything; short
IRQ  raster (VIC)    -- tiny handler: ack $d019, write 2-3 regs, rti
IRQ  CIA1 timer      -- existing irq_handler: sid_play, dispatcher,
                        UDTIM, kr_scan, exits via $ea7e
```

- **NMI cost:** at 38400 baud a byte arrives every ~266 cycles (~4
  raster lines). One `nmi_handler` pass delays a pending raster IRQ by
  well under one line. Fine inside an 8-line band.
- **CIA tick cost:** this is the real risk. `irq_handler` runs with the
  I flag set for several raster lines, so a raster IRQ that comes due
  meanwhile waits for it to finish. Fix: in `irq_handler`, after the
  CIA has been acknowledged (read `$dc0d` first), `cli` before
  `sid_play`, so the raster IRQ can nest. The CIA can't refire for
  ~16 ms, so the tick can't re-enter itself.
- **Dispatch:** one `$0314` handler checks `$d019` bit 0 first. If it's
  a raster IRQ, handle the split, write `#$01` to `$d019`, and leave
  through `$ea81` (the register restore + `rti`, skipping the CIA
  ack/jiffy tail). Otherwise fall into today's tick.
- Raster IRQ enable: `$d01a` bit 0; compare line in `$d012` plus
  `$d011` bit 7 (line 251 < 256, so bit 7 stays 0 for both lines).

Turning the map off: disable `$d01a`, and set `d018_top = d018_bottom`
(text) and MC off, so a stray IRQ can't flash tiles.

---

## Art conversion

First test, 2026-10-02: ArMM1998's "Zelda-like Tilesets and Sprites"
(OpenGameArt, **CC0**, 16x16 tiles, `Overworld.png` 640x576),
converted with `tiles/tile_convert.py` (run with `server/.venv`'s
python; Pillow):

```
# whole sheet, or a 20x8-tile viewport, as a before/after preview
tile_convert.py sheet Overworld.png --crop 0,4,20,8 --under 5,10 -o viewport.png
# a real charset: charset.bin (2K), colors.bin (256), tiles.json, preview.png
tile_convert.py tileset Overworld.png --cells "0,4,9,20" --under 5,10 -o ts_grass
```

How it converts: each pair of source pixels becomes one fat pixel, in
the C64 color closest to *both* (not an average, which smears
outlines). Then one search picks the shared `$d021/$d022/$d023` for the
whole set, with every char also picking its best 0-7 color. `--colors
bg,mc1,mc2` forces the shared three instead.

Findings:

- **Recognizable, C64-looking.** Grass, logs, rocks, buildings and
  shorelines survive the 2:1 fat pixels. A decode of `charset.bin` +
  `colors.bin` with the VIC's own multicolor rules matched the preview
  on all 7,936 fat pixels.
- **One set of shared colors can't cover a whole varied sheet.** Over
  all of `Overworld.png` the search picks light red / dark grey / light
  grey, and grass and water flatten. **Themed tilesets** (outdoor, cave,
  indoor), each with its own `$d021/$d022/$d023`, work far better. For
  the grass/water/path set it picked **green / light red / light
  blue**.
- **Wood needs a shared slot.** Forcing green / light green / light
  blue (better grass) flattens every log and rock to one red per char.
  The search's pick was better.
- **Water reads purple.** Pepto's light blue (`$6C5EB5`) is violet-ish.
  Worth checking in VICE's actual palette and on real hardware before
  tuning further.
- **The pack is layered.** Objects (logs, rocks, flowers) have
  transparent edges meant to sit on a separate ground tile. A char map
  has no layers, so `--under x,y` bakes a ground tile underneath. The
  same object on two different grounds = two tiles.
- **Per-tileset shared colors fit the raster split.** The split's IRQ
  already writes `$d021` and `$d016`; writing `$d022/$d023` there too
  is 2 more stores.

---

## C128 80-column: VDC RAM

**Reference only:** tiles are VIC-only (decided 2026-10-02), so none of
this is planned now. Kept in case 80-column tiles come up later.

The VDC needs **no raster split**. It has 512 characters, and attribute
bit 7 (ALT) picks the upper 256 per cell. The client prints all its
text with ALT set (lowercase set, `CHR$(14)`), so the non-ALT half is
free for tiles.

| VDC RAM | 16K VDC | 64K VDC | Use | Status |
|---|---|---|---|---|
| `$0000-$07cf` | yes | yes | Screen (80x25) | existing |
| `$0800-$0fcf` | yes | yes | Attributes | existing |
| `$1000-$172f` | yes | yes | Scrollback save area (live window chars) | existing |
| `$1800-$1f2f` | yes | yes | Scrollback save area (attributes) | existing |
| `$2000-$2fff` | yes | yes | Chars 0-255 (non-ALT), 16 bytes/char (8 used). **Tile charset**, replacing the ROM uppercase/graphics set | proposed |
| `$3000-$3fff` | yes | yes | Chars 256-511 (ALT). Lowercase text font, keep | existing |
| `$4000-$47ff` | -- | yes | **Sprite source shapes + masks** (2 x 32 bytes per 16x16 hires shape: 32 shapes) | proposed |
| `$4800-$ffff` | -- | yes | Tileset library (several 4K sets in 16-byte-stride form, ready for a VDC block copy into `$2000`) | proposed |

Notes:

- **The 40-column scrollback already claims `$4000-$FFFF`** (64K) or
  `$0800-$3FFF` (16K) of VDC RAM, but only in 40-column mode. In
  80-column mode the history ring is in main RAM, so the 64K rows above
  are only free if the 80-column path also switches R28 to 64K
  addressing (and re-runs DLCHR, as `vic_screen_init` does).
- **VDC tiles are hires only.** One foreground color per cell (attribute
  bits 0-3) over the global background (R26). VIC multicolor tiles can't
  show as-is on the VDC. That's a reason to pick hires tiles if both
  screens should look alike.
- **Software sprites:** reserve chars `$f0-$ff` (4 tiles) as
  compositing cells. A grid-aligned 16x16 sprite covers exactly 2x2
  chars. For each byte: take the tile byte (from a **main-RAM** copy;
  reading back VDC RAM is slow), AND it with the mask, OR in the shape,
  then write the 8 bytes x 4 chars = 32 VDC writes. Point the 4 screen
  cells at the compositing chars. That gives 4 sprites on screen at
  once; reserving more chars trades away tiles. Sprites off the grid
  need 3x3 = 9 chars each.

---

## C128: main RAM

The client runs with `$FF00 = $0E` (RAM `$4000-$BFFF`, KERNAL + I/O in).

| Bank 0 range | Use | Status |
|---|---|---|
| `$1c01-$5e2c` | Client program (last build; `check_128_layout.py` fails at `$6000`) | existing |
| `$5e2d-$5fff` | **~470 bytes left** | free |
| `$6000-$8edf` | 80-column history ring, chars | existing |
| `$8ee0-$8fff` | gap (288 bytes) | free |
| `$9000-$bedf` | 80-column history ring, attributes | existing |
| `$bee0-$bfff` | gap (288 bytes) | free |

**There isn't room to build a tile editor into bank 0.** The C64 side
loads overlays on demand; the 128 side `{include:}`s its popups and
loads no overlays at all today.

**Decision (Ryan, 2026-10-02): the tile editor is a loadable module on
both machines.** It's used rarely (fixing tiles as errors turn up), so
it shouldn't cost resident memory. On the 128 that means the first
overlay load path, rather than shrinking the ring or moving to bank 1.

### C128 editor load area: over the history ring

| Bank 0 range | While the editor is open | Status |
|---|---|---|
| `$6000-$8edf` | Editor code (`TILEED128.PRG`), up to ~11.7K | proposed |
| `$9000-$97ff` | Working copy of the tileset (2K, 8 bytes/char) | proposed |
| `$9800-$bedf` | Editor scratch: undo buffer, per-tile colors, file I/O buffer | proposed |

Since tiles are VIC-only, **the editor runs in 40-column mode**, where
the ring is free: the 40-column scrollback lives in VDC RAM, so the
main-RAM ring isn't in use. Started from 80 columns, the editor should
say "switch to 40 columns" (or the client switches modes) rather than
load over a live 80-column ring.

(Only if an 80-column launch is ever wanted: on a 64K VDC, stash the
ring into VDC RAM `$4000+` first and copy it back on exit; on a 16K
VDC, clear it.)

Constraints:

- **Mainline only.** `irq_handler` runs with `$FF00 = $00` (BASIC ROMs
  over `$4000-$BFFF`), so nothing IRQ-reachable may live in the editor.
  A 40-column raster split's handler has to stay in the resident part
  below `$4000`. It gets turned on and fed shadow values by the editor,
  but not owned by it.
- Load via KERNAL `LOAD` with `SETBNK` (`$FF68`) bank 0, which the
  keymap code already does for its config file. The disk device comes
  from the drive picker's selection.
- A RUN/STOP-RESTORE or crash while the editor is in memory leaves the
  ring trashed. The resident side should treat "editor was loaded" as
  "ring invalid" until it's re-stashed or cleared.

---

## C128 40-column (VIC)

Now the 128's **only** tile screen (decided 2026-10-02), so this
section needs a real investigation before the 128 side gets built.
Still the least settled part; **verify everything here against the 128 ROMs
and `vic_screen.asm` before building on it.** Today the 40-column
dialogue is VIC bank 0, `SCREEN_RAM = $0400`, color RAM `$d800`, using
the ROM character set.

Differences from the C64 plan:

- The 128 screen editor's IRQ rewrites `$d018` from its shadow
  (`$0A2C`, VM1) every frame. A raster split has to own that shadow, or
  take over the editor's raster handling, instead of just writing
  `$d018`.
- The VIC's 16K bank is picked by `$dd00` *and* its 64K RAM bank by MMU
  `$d506`. Bank 0's low 16K is crowded (`$1c01`+ program), and char ROM
  shows up in the VIC's view of banks 0/2.
- A likely home: VIC bank 3 of RAM bank 0 under `$FF00 = $0E`'s KERNAL
  (`$e000`+, the same "writes go through" trick as the C64), or RAM
  bank 1. Not checked yet.

---

## Open questions

- [x] **Hires or multicolor tiles?** **Decided 2026-10-02:
      multicolor, on the VIC screen on both machines** (128: 40-column).
- [ ] **Where tilesets are stored:** on the server (like
      `server/petscii_editor/store.py` canvases; this would also let
      the server send room maps) or on disk (`disk.asm`, drive picker)?
- [ ] **Game view or editor only?** The divider-row layout above
      assumes a map viewport in normal play. The editor alone could use
      a simpler split.
- [ ] Map viewport size vs. dialogue rows (8 vs. 6 tiles tall).
- [x] C128: where the editor's code goes. **Decided 2026-10-02:
      loadable on both machines; on the 128 it loads over the history
      ring** (see C128: main RAM).
- [x] ~~C128 VDC tiles (64K addressing, non-ALT chars)~~ -- moot, tiles
      are VIC-only.
- [ ] Tile table with shared chars (~100+ tiles per charset) vs. the
      fixed `4t` layout?
- [ ] One themed tileset per map region (own `$d021/$d022/$d023`)?
      Probably yes, from the conversion test.
- [ ] C128 40-column: where the VIC's tile charset and sprites live
      (see that section), and how a split coexists with the screen
      editor's `$0A2C` shadow.
- [ ] Check the water color in VICE's actual palette and on real
      hardware.

**First demo, 2026-10-02: `tiles/tile_demo.asm`** (`make run` in
`tiles/`). An 80x48-char meadow map (`demo_map.json`, built by
`make_demo_map.py` from stamps of the CC0 sheet; 195 unique chars, with
`overworld_remap.json` forcing foliage to light green so trees don't
melt into the grass) scrolls a char at a time under the cursor keys.
Rows 0-22 show multicolor tiles from `$e000`, row 23 is the solid divider
(`$a0`, color 0), and row 24 is a status line in the ROM lowercase font
copied to `$e800`. Raster IRQs at lines 235 and 251 do the switching,
with CIA1's timer IRQ off and SCNKEY called from the line-251 IRQ.
`vice_tile_demo_test.py` checks the window against the map data
(screen + color RAM), scrolling, clamping and quit: 14/14 pass in
x64sc. Full redraw per step, so fast scrolling can tear a little: the
redraw races the beam, and color RAM can't be double-buffered.

**Tile editor, 2026-10-03: `tiles/tile_editor.asm`** (`make run-editor` in
`tiles/`, which boots `tile_editor.d64`: the editor plus a `TILESET`
file). Standalone for now; the client's loadable editor can grow out of
it. Same bank-3 map and split as the demo, with the split moved up to
line 115:

```
rows 0-7   palette: tile t at col (t%16)*2, row (t/16)*2  | cols 34-39:
           (tile charset, multicolor)                      | tile repeated 3x4
row 8      divider ($a0, color 0), white under the selected tile
rows 9-24  zoomed tile, fat pixel = 2x1 solid cells       | panel + messages
           (ROM lowercase font, hires, black bg)           | (cols 18-39)
```

Keys: CRSR move, SPACE plot, 1-4 pen, E pick, F1/F3/F5 shared colors, F7
char color of the quarter under the cursor, +/- tile, C/V copy/paste a
tile, U undo/redo (one level: the last change's tile + shared colors),
S/L save/load `TILESET` on the current drive (`$ba`, 8 if unset), Q quit.

- **`TILESET` file** (`tiles/tileset_file.py` packs/unpacks it): `TS` +
  version 1, 2048-byte charset (tile t = chars 4t..4t+3), 256 color RAM
  values (`8 | color`), then bg/mc1/mc2: 2310 bytes, saved as a PRG.
  Loads are relocated into `$4000` and checked (size, magic) before they
  replace the working copy.
- **Working copy in normal RAM, write-through to `$e000`**, as planned
  above: the VIC copy under the KERNAL can be written but not read back
  without banking.
- **Reserved tiles:** 8 (blank, char `$20`) and 40 (divider, char `$a0`
  solid) can't be edited. The divider's reservation is new:
  `tile_convert.py` now keeps tile 40 free and writes `$a0` solid, so
  every tileset carries the split's divider char (the demo's
  `make_demo_map.py` already did this for its own charset).
- Tested: `vice_tile_editor_test.py` in x64sc, booting the `.d64`:
  drawing (palette, divider, zoomed grid against the tileset decoded in
  Python), plot / undo / redo, char and shared colors, tile select +
  preview, reserved-tile refusal, copy/paste, save (drive status `00,
  ok`), load after further edits, quit, and the file on the disk image
  matching memory.

Next step: a **raster-split stress demo** (in the
style of `tada_screen_blit_test.asm`) with tiles above, text below, and
sprites moving, while the server floods the SwiftLink. It measures the
jitter numbers above for real before any editor code gets written.
