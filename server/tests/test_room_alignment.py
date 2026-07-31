"""tests/test_room_alignment.py — room_alignment.py's turf-capture
persistence: per-level sidecar files, re-applied onto a freshly-loaded
Map at startup (see simple_server.py's apply_overrides() call).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from base_classes import Map, Room, RoomAlignment


class _TempStateDir(unittest.TestCase):
    def setUp(self):
        import room_alignment
        self._orig_dir = room_alignment._STATE_DIR
        room_alignment._STATE_DIR = Path('run') / 'server' / 'test_room_alignment'
        if room_alignment._STATE_DIR.exists():
            for f in room_alignment._STATE_DIR.glob('*.json'):
                f.unlink()
            room_alignment._STATE_DIR.rmdir()

    def tearDown(self):
        import room_alignment
        if room_alignment._STATE_DIR.exists():
            for f in room_alignment._STATE_DIR.glob('*.json'):
                f.unlink()
            room_alignment._STATE_DIR.rmdir()
        room_alignment._STATE_DIR = self._orig_dir


def _make_map(level: int, room_number: int, alignment=RoomAlignment.NEUTRAL) -> Map:
    game_map = Map()
    room = Room(number=room_number, name='Test Room', desc='A room.', alignment=alignment)
    game_map.levels[level] = {room_number: room}
    return game_map


class TestRecordAndLoad(_TempStateDir):
    def test_record_capture_persists_per_level_file(self):
        from room_alignment import record_capture, load_overrides, _state_file
        record_capture(3, 42, RoomAlignment.CLAW)
        self.assertTrue(_state_file(3).exists())
        self.assertEqual(load_overrides(3), {'42': 'claw'})

    def test_different_levels_get_separate_files(self):
        from room_alignment import record_capture, _state_file
        record_capture(1, 5, RoomAlignment.FIST)
        record_capture(2, 5, RoomAlignment.SWORD)
        self.assertNotEqual(_state_file(1), _state_file(2))
        self.assertTrue(_state_file(1).exists())
        self.assertTrue(_state_file(2).exists())

    def test_multiple_captures_on_same_level_accumulate(self):
        from room_alignment import record_capture, load_overrides
        record_capture(4, 10, RoomAlignment.FIST)
        record_capture(4, 11, RoomAlignment.CLAW)
        overrides = load_overrides(4)
        self.assertEqual(overrides, {'10': 'fist', '11': 'claw'})

    def test_recapturing_a_room_overwrites_its_entry(self):
        from room_alignment import record_capture, load_overrides
        record_capture(1, 7, RoomAlignment.FIST)
        record_capture(1, 7, RoomAlignment.SWORD)
        self.assertEqual(load_overrides(1), {'7': 'sword'})


class TestApplyOverrides(_TempStateDir):
    def test_applies_persisted_capture_onto_fresh_map(self):
        from room_alignment import record_capture, apply_overrides
        record_capture(1, 9, RoomAlignment.CLAW)
        game_map = _make_map(1, 9, alignment=RoomAlignment.NEUTRAL)
        apply_overrides(game_map)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.CLAW)

    def test_hq_room_is_never_overridden(self):
        from room_alignment import record_capture, apply_overrides
        record_capture(1, 9, RoomAlignment.CLAW)
        game_map = _make_map(1, 9, alignment=RoomAlignment.HQ)
        apply_overrides(game_map)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.HQ)

    def test_free_fire_room_is_never_overridden(self):
        from room_alignment import record_capture, apply_overrides
        record_capture(1, 9, RoomAlignment.CLAW)
        game_map = _make_map(1, 9, alignment=RoomAlignment.FREE_FIRE)
        apply_overrides(game_map)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.FREE_FIRE)

    def test_missing_room_is_skipped_without_error(self):
        from room_alignment import record_capture, apply_overrides
        record_capture(1, 999, RoomAlignment.CLAW)
        game_map = _make_map(1, 9)
        apply_overrides(game_map)  # should not raise

    def test_no_overrides_is_a_no_op(self):
        from room_alignment import apply_overrides
        game_map = _make_map(1, 9, alignment=RoomAlignment.NEUTRAL)
        apply_overrides(game_map)
        self.assertEqual(game_map.get_room(1, 9).alignment, RoomAlignment.NEUTRAL)

    def test_none_game_map_is_a_no_op(self):
        from room_alignment import record_capture, apply_overrides
        record_capture(1, 9, RoomAlignment.CLAW)
        apply_overrides(None)  # should not raise


if __name__ == '__main__':
    unittest.main()
