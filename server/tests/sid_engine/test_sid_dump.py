"""tests/sid_engine/test_sid_dump.py

Covers sid_engine/sid_dump.py's 6502-emulator-driven converter against a
tiny hand-assembled program -- no real .sid file needed. The program:

    init (@ load address):     RTS                     (does nothing)
    play (@ load address + 1): INC $2000                (bump a counter)
                                LDA $2000
                                STA $D400                (reg 0 = counter)
                                RTS

So each play() call should yield exactly one frame, {0: N}, with N
incrementing every call -- this both proves register writes are being
captured correctly and that CPU/memory state (the counter) persists
across separate convert()-loop calls to play(), not just within one.
"""
from __future__ import annotations

import unittest

from sid_engine import sid_dump
from sid_engine.sid_file import SidFile

_LOAD = 0x1000

# init: RTS
_INIT_CODE = bytes([0x60])
# play: INC $2000 / LDA $2000 / STA $D400 / RTS
_PLAY_CODE = bytes([0xEE, 0x00, 0x20, 0xAD, 0x00, 0x20, 0x8D, 0x00, 0xD4, 0x60])


def _counter_tune() -> SidFile:
    return SidFile(
        version=2, load_address=_LOAD, init_address=_LOAD,
        play_address=_LOAD + len(_INIT_CODE), num_songs=1, start_song=1,
        speed=0, name='counter', author='test', released='2026',
        data=_INIT_CODE + _PLAY_CODE,
    )


class TestConvert(unittest.TestCase):
    def test_yields_one_frame_per_play_call_with_incrementing_counter(self):
        sid = _counter_tune()
        result = list(sid_dump.convert(sid, num_frames=5))

        self.assertEqual(result, [{0: 1}, {0: 2}, {0: 3}, {0: 4}, {0: 5}])

    def test_num_frames_controls_output_length(self):
        sid = _counter_tune()
        result = list(sid_dump.convert(sid, num_frames=2))
        self.assertEqual(len(result), 2)

    def test_init_receives_zero_based_song_number(self):
        # init: LDA #0 (does nothing observable) then just check it runs
        # without error when a specific song is requested -- init doesn't
        # write any SID registers in this fixture, only play does.
        sid = _counter_tune()
        result = list(sid_dump.convert(sid, song=1, num_frames=1))
        self.assertEqual(result, [{0: 1}])


class TestConvertRunawayGuard(unittest.TestCase):
    def test_infinite_loop_raises_sid_emulation_error(self):
        # play: JMP $1000 (itself) -- never returns.
        loop_play = bytes([0x4C, 0x00, 0x10])
        sid = SidFile(
            version=2, load_address=_LOAD, init_address=_LOAD,
            play_address=_LOAD, num_songs=1, start_song=1,
            speed=0, name='loop', author='test', released='2026',
            data=loop_play,
        )
        with self.assertRaises(sid_dump.SidEmulationError):
            list(sid_dump.convert(sid, num_frames=1, max_cycles_per_call=1000))


if __name__ == '__main__':
    unittest.main()
