"""sid_engine/stub_tune.py — placeholder tune, no real SID emulation yet.

Generates a simple C4-E4-G4-C5 arpeggio on voice 1 (triangle wave), while
voices 2 and 3 hold E4 and G4 respectively -- a sustained C major chord
underneath the melody, so all three voices sound together as a full
triad. Per-tick register-write frames, in the format frames.py expects.
This exists purely to prove the server -> SwiftLink -> IRQ player pipe
end-to-end; it is not meant to sound good. Once real SID rendering exists
(playing an actual .sid file's init/play routine in an emulator and
recording its register writes), this module goes away.
"""
from __future__ import annotations

from typing import Iterator, Mapping

from sid_engine.frames import (
    AD, CONTROL, FREQ_HI, FREQ_LO, GATE, MODE_VOL, SR, VOICE_OFFSET,
    WAVE_TRIANGLE,
)

# PAL SID clock (985248 Hz); reg = freq_hz * 16777216 / clock.
_NOTES_HZ = (261.63, 329.63, 392.00, 523.25)  # C4, E4, G4, C5
_PAL_CLOCK = 985248

_NOTE_TICKS = 25   # ~0.5s per note at 50Hz
_GAP_TICKS  = 5    # brief gate-off silence between notes

# Chord voices: (voice index 1/2 -- added to VOICE_OFFSET, since voice 1
# is 0 -- , frequency). Voice 1 arpeggiates through all four _NOTES_HZ on
# its own below; voices 2/3 just hold the E4/G4 that complete the C major
# triad against voice 1's own C4/C5.
_CHORD_VOICES = ((1, _NOTES_HZ[1]), (2, _NOTES_HZ[2]))  # voice 2 = E4, voice 3 = G4


def _freq_reg(hz: float) -> int:
    return round(hz * 16777216 / _PAL_CLOCK)


def generate() -> Iterator[Mapping[int, int]]:
    """Yield one dict per tick: voice 1's arpeggio plus a sustained
    two-voice chord underneath."""
    # Master volume, filter off.
    yield {MODE_VOL: 0x0f}
    # Voice 1 attack/decay and sustain/release, set once -- held for the
    # whole tune.
    yield {AD: 0x09, SR: 0xa0}

    # Voices 2/3: gate on once, held for the whole tune, released only at
    # the very end alongside voice 1's final mute.
    for voice_index, hz in _CHORD_VOICES:
        offset = VOICE_OFFSET * voice_index
        reg = _freq_reg(hz)
        yield {FREQ_LO + offset: reg & 0xff, FREQ_HI + offset: (reg >> 8) & 0xff,
               AD + offset: 0x09, SR + offset: 0xa0,
               CONTROL + offset: WAVE_TRIANGLE | GATE}

    for hz in _NOTES_HZ:
        reg = _freq_reg(hz)
        yield {FREQ_LO: reg & 0xff, FREQ_HI: (reg >> 8) & 0xff,
               CONTROL: WAVE_TRIANGLE | GATE}
        for _ in range(_NOTE_TICKS - 1):
            yield {}
        yield {CONTROL: WAVE_TRIANGLE}  # gate off, let it release
        for _ in range(_GAP_TICKS - 1):
            yield {}

    for voice_index, _hz in _CHORD_VOICES:
        yield {CONTROL + VOICE_OFFSET * voice_index: WAVE_TRIANGLE}  # gate off
    yield {MODE_VOL: 0x00}  # mute at the end
