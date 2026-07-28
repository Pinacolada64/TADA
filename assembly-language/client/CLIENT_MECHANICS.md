# TADA C64 client — mechanics reference

How `tada-client.asm` actually works under the hood: memory layout,
interrupt structure, the SwiftLink transport, and the SID streaming
protocol layered on top of it. Written up after a long debugging session
where several of these mechanisms turned out to have non-obvious failure
modes — see the "Hard-won lessons" section at the end before touching
anything here.

## Program layout

- Loads as a normal BASIC program (`orig $0801`, `10 SYS2061` stub),
  code starts at `start` ($080d).
- Free RAM for new code/data starts right after the last data block
  (`SID_BUF`, currently ending around $0fd5 — check
  `tada-client-vice-labels`'s `__extendedasmblock` entry after a build
  for the current top).
- Screen RAM is the default $0400; never relocated.
- BASIC + KERNAL ROM stay banked in throughout — nothing here touches
  `$01` (the 6510 I/O port), so ROM routines (CHROUT, GETIN, the stock
  IRQ handler) are always reachable normally.

## Zero page usage

Only `$f9`/`$fa` (`rx_head`/`rx_tail`, the NMI receive ring buffer
indices) and `$fb`/`$fc` (`scr_ptr_lo`/`scr_ptr_hi`) are in zero page.
Everything SID-related deliberately is **not** — see "Hard-won lessons"
below for why. Default to ordinary memory for any new variable; only use
zero page for a genuine `(zp),Y`/`(zp,X)` indirect pointer, and verify
safety against the real KERNAL/BASIC ROM binaries first (technique also
below).

## Two interrupt sources

**NMI** (`$0318`/`$0319`, installed by `init_nmi`): the SwiftLink
cartridge raises NMI when a byte arrives at the ACIA. `nmi_handler`
drains it into `rx_buf` (256 bytes, wraps for free) the instant it
arrives, regardless of what mainline is doing, then chains to whatever
NMI handler was there before (`nmi_orig`) if the NMI wasn't ours (i.e.
RESTORE key). Flow control: once `rx_buf` crosses `RX_HIGH_WATER` (200)
bytes buffered, `nmi_handler` deasserts RTS, which makes VICE's ACIA
core stop draining its TCP socket — genuine backpressure all the way to
the server's `write()`/`drain()`, not just a local buffer swap. `sl_recv`
(mainline) re-asserts RTS once drained back under `RX_LOW_WATER` (32).

**IRQ** (`$0314`/`$0315`, installed by `init_irq`): hooked the same way,
chaining to the stock KERNAL IRQ (`irq_orig`) at the end via
`jmp (irq_orig)`. Two tiers, in `irq_handler`:
1. `sid_play` — unconditional, every single tick. SID playback tempo
   must never depend on how many other jobs are registered, so this
   always runs first, before anything else.
2. `irq_dispatch_next` — a round-robin jump table (`irq_task_table`),
   ImageBBS `irqhn.asm`-style: one job serviced per tick, self-modified
   index advancing by 2 (one word entry) each time. Currently just a
   placeholder heartbeat counter; a real candidate would be an
   interrupt-driven SwiftLink TX queue (`sl_send` is still a busy-wait
   today).

Since the hardware IRQ vector runs through the KERNAL's own entry stub
first (`$FF48`, pushes A/X/Y before jumping through `$0314`), neither
`irq_handler` nor anything it calls needs to save/restore registers
itself — chaining to `irq_orig` at the end does the final
`pla/tax/pla/tay/pla/rti`.

## SwiftLink transport

19200 baud originally, now **38400** (`SL_CTRL_38K`, `$1f` in the ACIA
control register's low nibble). SwiftLink's crystal makes these nibble
values differ from a stock 6551 datasheet's own baud table — `$0e` is
19200 here, `$0f` is 38400 (per Craig Bruce's `swiftlib.s`
`slNormBauds` table). 38400 is the fastest a *plain* SwiftLink (not the
Turbo232 variant) supports without its external clock generator
register. `Makefile`'s `SL_BAUD` must stay in lockstep, since VICE's
`-rsdev3baud` needs to match what the guest ACIA is actually configured
for.

`sl_send` is a plain busy-wait on TDRE. `sl_recv` just drains `rx_buf`
(populated asynchronously by `nmi_handler`) — never touches the ACIA
directly.

## Text protocol vs. SID binary stream

Everything rides the same connection. `handle_recv_byte` (called from
both `wait_for_data` and `sid_service_background`, see below) is the
dispatcher: normally every byte just goes to `display_char`, except:

- **`SID_STREAM_START` ($01) + `SID_STREAM_CONFIRM` ($53)** — two
  specific bytes back-to-back, not one. A lone `$01` isn't trusted:
  this is a multiplayer server, unsolicited text (ally/room/ambient
  messages) can land on the connection independent of anything the
  player typed, interleaved with a command's response. A single-byte
  marker collided with ordinary text in exactly this way during
  development. `sid_mode = 4` is the tentative "saw the first byte"
  state; if the very next byte isn't the confirm byte, both are
  replayed as ordinary text instead of silently mistaking later bytes
  for SID data.
- Once confirmed (`sid_mode = 1`), the next two bytes are a 16-bit
  little-endian **length prefix** (`sid_mode = 2` then `3`) — the byte
  length of the frame body that follows. The client counts this down
  (`sid_remaining_lo`/`hi`) rather than scanning for an end marker,
  because an in-band end marker is fundamentally ambiguous here: a SID
  register *value* is an arbitrary 0-255 byte, and real tune data
  eventually contains a literal match. (`FRAME_END` = `$ff`, terminating
  one tick's register writes, does *not* have this problem — it's only
  ever checked at a register-index position, and valid indices are
  0-24, never ambiguous with `$ff`.)
- **`SID_STOP` ($03)** — a one-byte control signal, not a stream (`play
  #stop`). Silences the SID immediately (all 25 registers zeroed, not
  just "stop taking further updates" — anything currently sustaining
  goes quiet right away) and resets playback state, via `sid_stop`
  (shared with `init_sid` at boot).

See `sid_engine/frames.py` (server side) for the matching encoder and
its own, more detailed protocol-ambiguity notes.

## SID_BUF and playback

`SID_BUF` (256 bytes, wraps for free, same convention as `rx_buf`) is
the frame-data ring buffer: `handle_recv_byte_store` (mainline) is the
producer, `sid_play` (IRQ) is the consumer.

**Flow control**: `handle_recv_byte_store` spin-waits for room
(`sid_wr + 1 == sid_rd` → full, one-slot-sacrificed convention) before
storing each byte. Without this, bytes can arrive off the wire far
faster than `sid_play` drains them (throttled to one frame per IRQ
tick, i.e. the tune's real playback rate) — a real tune's burst can
fill this 256-byte buffer in well under 100ms while taking most of a
second to finish arriving, and the producer would lap the consumer,
overwriting frame data before it's ever read. Spinning here is safe:
interrupts stay enabled, so `sid_play` keeps draining while mainline
waits, and a long enough stall cascades naturally into `rx_buf`'s own
RTS-based backpressure.

`sid_play` itself: one frame per call, never more, never less. First
scans forward from `sid_rd` for a `FRAME_END` without touching any
registers; if it hits `sid_wr` first, the frame hasn't fully arrived
yet, so it just returns and holds last tick's sound rather than reading
stale bytes. Only once a complete frame is confirmed present does it
apply the `(reg, val)` pairs for real.

## Background playback

Long tunes (Ultima III subtunes run up to ~2 minutes, using HVSC's
community-verified loop lengths) meant the player would otherwise be
stuck unable to type anything until an entire stream finished arriving.
Two pieces work together:

- `wait_for_data` returns to the prompt as soon as `sid_mode` reaches 1
  (a stream just confirmed, before any length/body bytes) instead of
  waiting out the whole transfer via its usual settle-countdown. Nothing
  textual is ever left unshown at that point — the server always sends
  its status text before the raw stream.
- `sid_service_background`, polled from `read_line`'s loop every
  iteration, keeps draining `rx_buf` into `SID_BUF` (feeding `sid_play`)
  while the player types — but *only* while `sid_mode != 0`. If it's 0
  (plain text, or nothing yet confirmed), the byte is left untouched in
  `rx_buf` for `wait_for_data` to display normally next round-trip,
  since calling `display_char` here would corrupt whatever the player
  is mid-typing.
- `sid_background` (0 = foreground/`wait_for_data`, 1 =
  background/`read_line`) gates the TEMP diagnostic prints in
  `handle_recv_byte_store` so they can't fire mid-keystroke either.

**Known limitation**: if the player submits a new command *while* the
previous stream is still mid-transfer (`sid_mode` back to 3, not a
fresh 1), `wait_for_data`'s early-return doesn't trigger again — it
falls through to the normal full-blocking drain for the rest of that
old tail (plus whatever text was queued behind it on the wire, e.g. the
next prompt string) before it can get to the new command's response.
Typing while a stream plays in the background works; submitting while
it's *still arriving* blocks until it catches up. Not yet fixed:
buffering trailing text and flushing it once a line is submitted would
close this gap.

## Hard-won lessons

- **CHROUT does not reliably preserve X.** Any loop that keeps an index
  in X across a `jsr CHROUT` (or anything that calls it, like
  `sid_print_hex_byte`) will get silently clobbered. Keep loop counters
  in a plain memory byte, reload into X only right before the indexed
  access — same fix used for `read_line`'s `linelen` and later for
  `sid_print_bufdump`'s own counter (which hit this exact bug once,
  despite the lesson already being documented here).
- **"Not used elsewhere in this file" is not sufficient justification
  for a zero-page address.** Zero page here is real KERNAL/BASIC
  territory. Two separate SID-engine variables ($f3/$f4, then $f5/$f6)
  both turned out to collide with the *stock KERNAL IRQ handler's own
  internal pointers* (keyboard-decode-table pointer and a related one,
  both around `$ea31`-`$eae2`) — silently corrupted every single tick,
  since this client chains into that handler. Confirmed via direct ROM
  disassembly (py65, loading `$(VICE_ROMS)/kernal-901246-01.bin` /
  `basic-901226-01.bin`), not guessing. Fixed for good by moving those
  variables out of zero page entirely, since none of them are ever used
  as indirect pointers — see the Zero page section above. Before adding
  a new zero-page byte, verify with the same disassembly technique;
  before that, ask whether it needs to be zero page at all.
- **c64list syntax gotchas**: no `ds`/reserve-space directive (write out
  `byte 0,0,0,...`); accumulator shifts must be bare (`lsr`, not
  `lsr a`); the `@:`/`<@`/`>@` anonymous local label scheme only
  resolves to the single nearest previous/next `@:`, so use plain named
  labels once a routine needs more than one loop-back point.
