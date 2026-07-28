"""sid_engine/frames.py — encode SID register-write frames for streaming.

Wire format (consumed by tada-client.asm's sid_play/binary-mode receiver):

    stream  := STREAM_START STREAM_CONFIRM length_lo length_hi body
    body    := frame*
    frame   := (reg val)* FRAME_END

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
as a stream, makes an accidental collision astronomically less likely
without needing a longer/costlier marker.

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
STREAM_CONFIRM = 0x53  # 'S' -- arbitrary, just distinctive
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


def encode_stream(tune: Iterable[Mapping[int, int]]) -> bytes:
    """Encode a full tune (an iterable of per-tick write dicts) as a
    complete STREAM_START+STREAM_CONFIRM + length-prefixed byte stream."""
    body = bytearray()
    for frame in tune:
        body.extend(encode_frame(frame))
    if len(body) > 0xffff:
        raise ValueError(f'encoded stream too long ({len(body)} bytes) for a 16-bit length prefix')
    header = bytes([STREAM_START, STREAM_CONFIRM, len(body) & 0xff, (len(body) >> 8) & 0xff])
    return header + bytes(body)
