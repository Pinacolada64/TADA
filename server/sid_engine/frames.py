"""sid_engine/frames.py — encode SID register-write frames for streaming.

Wire format (consumed by tada-client.asm's sid_play/binary-mode receiver):

    stream  := STREAM_START frame* STREAM_END
    frame   := (reg val)* FRAME_END

Each frame carries only the registers that changed that tick -- most
frames touch a handful of the 25 SID registers, so this stays compact
compared to a fixed 25-byte-per-frame snapshot. FRAME_END ($ff) is safe
as a sentinel because SID only has registers 0-24 (offsets from $D400).

STREAM_START/STREAM_END ($01/$02) are also safe to multiplex onto the
same connection as the existing CR-terminated PETSCII text protocol --
neither byte can appear in a normal text line.
"""
from __future__ import annotations

from typing import Iterable, Mapping

STREAM_START = 0x01
STREAM_END   = 0x02
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
    complete STREAM_START...STREAM_END framed byte stream."""
    body = bytearray([STREAM_START])
    for frame in tune:
        body.extend(encode_frame(frame))
    body.append(STREAM_END)
    return bytes(body)
