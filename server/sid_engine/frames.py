"""sid_engine/frames.py — encode SID register-write frames for streaming.

Wire format (consumed by tada-client.asm's sid_play/binary-mode receiver):

    stream  := STREAM_START length_lo length_hi body
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

STREAM_START ($01) is still an in-band scan, checked against every byte
of ordinary game text while not already mid-stream -- also technically
collision-prone, but real chat/game text essentially never contains a
raw $01 byte, unlike SID payload data, so it's a much lower-probability
edge case left as-is for now.
"""
from __future__ import annotations

from typing import Iterable, Mapping

STREAM_START = 0x01
FRAME_END    = 0xff

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
    complete STREAM_START + length-prefixed byte stream."""
    body = bytearray()
    for frame in tune:
        body.extend(encode_frame(frame))
    if len(body) > 0xffff:
        raise ValueError(f'encoded stream too long ({len(body)} bytes) for a 16-bit length prefix')
    header = bytes([STREAM_START, len(body) & 0xff, (len(body) >> 8) & 0xff])
    return header + bytes(body)
