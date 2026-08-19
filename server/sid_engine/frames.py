"""sid_engine/frames.py — encode SID register-write frames for streaming.

Wire format (consumed by tada-client.asm's sid_play/binary-mode receiver):

    transmission := stream+
    stream       := STREAM_START STREAM_CONFIRM length_lo length_hi body
    body         := frame*
    frame        := (reg val)* FRAME_END

A transmission is one or more streams back-to-back, not necessarily
exactly one -- see encode_stream()'s own comment for why (the 16-bit
length prefix caps a single stream well under most real tunes' full
length) and how the client handles the boundary between two of them
with no changes of its own.

`length` (16-bit, little-endian) is the byte length of `body` -- the
client counts down from it rather than scanning for an end marker.
That's deliberate, not incidental: an in-band end marker (an earlier
version of this format used a literal $02 byte) is fundamentally
ambiguous here, because a SID register *value* is an arbitrary 0-255
byte and will eventually contain that same value somewhere in a real
tune's data. A hand-picked stub tune can dodge that by luck (as this
project's original stub arpeggio did, for a while); real, dense register
data cannot. FRAME_END ($ff) doesn't have this problem despite being an
in-band sentinel too, because it's only ever checked at a register-index
position, and valid indices are 0-24 -- never ambiguous with $ff.

STREAM_START + STREAM_CONFIRM together are an in-band scan, checked
against every byte of ordinary game text while not already mid-stream.
This is a multiplayer server -- unsolicited text (ally/room/ambient
messages) can land on the same connection independent of anything the
player typed, interleaved with a play response. A single STREAM_START
byte was confirmed live to collide with ordinary text this way,
corrupting later text into bogus SID data. Requiring a specific *second*
byte immediately after, before the client commits to treating anything
as a stream, makes an accidental collision astronomically less likely --
*provided* that second byte is chosen from a range ordinary PETSCII text
never produces. STREAM_CONFIRM used to be 0x53 ('S'), and the sibling
confirms in petscii_editor/canvas.py and commands/c64_display.py were
0x42/0x44/0x41 ('B'/'D'/'A') -- all in the 0x41-0x5A range that
cbmcodecs2's petscii_c64en_lc codec maps to ordinary lowercase letters,
which are common in this project's sentence-case player-facing text.
'A' in particular (commands/c64_display.py's APPLY_STREAM_CONFIRM) hung
a live client on 2026-08-17: a stray STREAM_START followed by an
in-band lowercase 'a' misfired the apply-confirm handler, which then
blocked forever waiting for 5 protocol bytes nobody was sending. All
four confirm bytes now live in the 0x02-0x0f gap, which cbmcodecs2 never
maps to a printable character and this codebase never uses as a color/
cursor control code -- see each sibling module's own STREAM_CONFIRM for
its assigned value.

STOP ($03) is a separate, instantaneous one-byte control signal (not a
stream) -- sent by `play #stop` to silence playback and reset the
client's SID state immediately. It's only meaningful while the client is
in text mode (not mid-stream) -- see tada-client.asm's handle_recv_byte
for why that's always true in practice: the request/response prompt loop
can't even accept a new command until the previous stream has already
fully landed.
"""
from __future__ import annotations

from typing import Iterable, Mapping

STREAM_START   = 0x01
STREAM_CONFIRM = 0x02  # unused C64 control code -- never appears in
                        # ordinary PETSCII text, unlike a printable
                        # letter (see this module's docstring)
STOP           = 0x03
FRAME_END      = 0xff

NUM_REGISTERS = 25  # $D400-$D418

# SID register offsets from $D400, voice 1 (voice 2/3 repeat at +7/+14).
FREQ_LO  = 0
FREQ_HI  = 1
PW_LO    = 2
PW_HI    = 3
CONTROL  = 4  # waveform select (high nibble) + gate/sync/ring/test (low nibble)
AD       = 5  # attack/decay
SR       = 6  # sustain/release
VOICE_OFFSET = 7  # add this * (voice - 1) to the above for voice 2/3

FCUTOFF_LO = 21
FCUTOFF_HI = 22
RES_FILT   = 23
MODE_VOL   = 24

# CONTROL register waveform bits (high nibble)
WAVE_TRIANGLE = 0x10
WAVE_SAWTOOTH = 0x20
WAVE_PULSE    = 0x40
WAVE_NOISE    = 0x80
GATE          = 0x01


def encode_frame(writes: Mapping[int, int]) -> bytes:
    """Encode one tick's register writes as (reg, val) pairs + FRAME_END.

    Raises ValueError if a register index or value is out of range --
    catching a bad write here is cheaper than debugging garbled audio
    on real hardware.
    """
    out = bytearray()
    for reg, val in writes.items():
        if not 0 <= reg < NUM_REGISTERS:
            raise ValueError(f'SID register offset out of range: {reg}')
        if not 0 <= val <= 0xff:
            raise ValueError(f'SID register value out of range: {val}')
        out.append(reg)
        out.append(val)
    out.append(FRAME_END)
    return bytes(out)


MAX_CHUNK_BODY = 0xffff  # length prefix is 16 bits -- see encode_stream's own comment


def encode_stream(tune: Iterable[Mapping[int, int]]) -> bytes:
    """Encode a full tune (an iterable of per-tick write dicts) as one or
    more STREAM_START+STREAM_CONFIRM length-prefixed chunks, concatenated
    back-to-back.

    A single chunk's body is capped at MAX_CHUNK_BODY bytes by the 16-bit
    length prefix -- for a long and/or register-write-dense tune (dense
    chip music can run ~47 bytes/frame; at 50Hz that's under 30 real
    seconds per 0xffff-byte chunk) that's nowhere near enough to hold an
    entire tune, so this splits across as many chunks as needed instead
    of raising. The split only ever happens on a whole-FRAME boundary --
    a single encode_frame() output (one tick's (reg,val) pairs +
    FRAME_END) is never itself split across two chunks -- so no chunk
    boundary can land mid-frame.
    Confirmed live (2026-08-19) that the client needs no changes to play
    a chunked stream seamlessly: handle_recv_byte's sid_mode already
    resets to 0 -- "watching for a fresh STREAM_START" -- the instant one
    chunk's length countdown reaches zero, so the next chunk's header
    just looks like an ordinary new stream starting immediately behind
    the last one. The few header bytes between chunks cost a handful of
    ACIA-speed byte-times, not a perceptible playback gap.
    """
    out = bytearray()
    body = bytearray()

    def flush_chunk() -> None:
        header = bytes([STREAM_START, STREAM_CONFIRM, len(body) & 0xff, (len(body) >> 8) & 0xff])
        out.extend(header)
        out.extend(body)
        body.clear()

    for frame in tune:
        frame_bytes = encode_frame(frame)
        if body and len(body) + len(frame_bytes) > MAX_CHUNK_BODY:
            flush_chunk()
        body.extend(frame_bytes)
    # Always emit at least one chunk, even a zero-length one for an empty
    # tune -- matches encode_stream()'s pre-chunking behavior (an empty
    # tune still produced one header+zero-length-body stream, not nothing).
    if not out or body:
        flush_chunk()
    return bytes(out)
