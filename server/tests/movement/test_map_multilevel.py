"""tests/test_map_multilevel.py

Unit tests for base_classes.Map's multi-level support, added so rooms from
different dungeon floors (SPUR's cl 1-7) don't collide -- room numbers are
only unique within a single level (e.g. level 1's room 42 is "Underground
Forest"; level 4's room 42 is "A Maze Of Alleys").

Coverage:
  - read_map(level=1) still populates .rooms for backward compatibility
  - read_map(level=N>1) populates .levels[N] without touching .rooms
  - rooms with the same number on different levels don't collide
  - get_room(level, number) looks up the right level
  - both JSON alignment shapes ('room_alignment' from convert_from_gbbs_tool.py,
    and level_1.json's bare 'alignment' string) parse to a real RoomAlignment
  - missing file logs and leaves that level unpopulated (no crash)

Run with:
    python -m pytest tests/test_map_multilevel.py -v
"""
import json
import tempfile
import unittest
from pathlib import Path

from base_classes import Map, RoomAlignment


def _write_level_json(path: Path, rooms: list) -> None:
    path.write_text(json.dumps({'rooms': rooms}))


class TestMapMultiLevel(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_level1_populates_rooms_alias(self):
        f = self.tmp_path / 'level_1.json'
        _write_level_json(f, [{'number': 42, 'name': 'Underground Forest', 'exits': {}, 'desc': 'x'}])
        m = Map()
        m.read_map(str(f), level=1)
        self.assertEqual(m.rooms[42].name, 'Underground Forest')
        self.assertIs(m.rooms, m.levels[1])

    def test_level_n_does_not_touch_rooms_alias(self):
        level1 = self.tmp_path / 'level_1.json'
        level4 = self.tmp_path / 'level_4.json'
        _write_level_json(level1, [{'number': 42, 'name': 'Underground Forest', 'exits': {}, 'desc': 'x'}])
        _write_level_json(level4, [{'number': 42, 'name': 'A Maze Of Alleys', 'exits': {}, 'desc': 'y'}])
        m = Map()
        m.read_map(str(level1), level=1)
        m.read_map(str(level4), level=4)
        # .rooms still reflects level 1 only
        self.assertEqual(m.rooms[42].name, 'Underground Forest')
        self.assertEqual(m.levels[4][42].name, 'A Maze Of Alleys')

    def test_get_room_looks_up_correct_level(self):
        level4 = self.tmp_path / 'level_4.json'
        _write_level_json(level4, [{'number': 42, 'name': 'A Maze Of Alleys', 'exits': {}, 'desc': 'y'}])
        m = Map()
        m.read_map(str(level4), level=4)
        room = m.get_room(4, 42)
        self.assertEqual(room.name, 'A Maze Of Alleys')
        self.assertIsNone(m.get_room(1, 42))     # level 1 never loaded
        self.assertIsNone(m.get_room(4, 999))    # room doesn't exist

    def test_room_alignment_new_shape_parses(self):
        """convert_from_gbbs_tool.py's 'room_alignment' key."""
        f = self.tmp_path / 'level_x.json'
        _write_level_json(f, [
            {'number': 1, 'name': 'Fist HQ', 'exits': {}, 'desc': 'x', 'room_alignment': 'fist'},
            {'number': 2, 'name': 'Free Fire Zone', 'exits': {}, 'desc': 'x', 'room_alignment': 'free_fire'},
            {'number': 3, 'name': 'Neutral Ground', 'exits': {}, 'desc': 'x', 'room_alignment': 'neutral'},
        ])
        m = Map()
        m.read_map(str(f), level=9)
        self.assertEqual(m.levels[9][1].alignment, RoomAlignment.FIST)
        self.assertEqual(m.levels[9][2].alignment, RoomAlignment.FREE_FIRE)
        self.assertEqual(m.levels[9][3].alignment, RoomAlignment.NEUTRAL)

    def test_room_alignment_old_shape_parses(self):
        """level_1.json's bare lowercase 'alignment' string (no room_alignment key)."""
        f = self.tmp_path / 'level_y.json'
        _write_level_json(f, [
            {'number': 1, 'name': 'Cavern Peak', 'exits': {}, 'desc': 'x', 'alignment': 'sword'},
            {'number': 2, 'name': 'Ruby Room', 'exits': {}, 'desc': 'x', 'alignment': 'claw'},
        ])
        m = Map()
        m.read_map(str(f), level=10)
        self.assertEqual(m.levels[10][1].alignment, RoomAlignment.SWORD)
        self.assertEqual(m.levels[10][2].alignment, RoomAlignment.CLAW)

    def test_room_alignment_missing_defaults_to_neutral(self):
        f = self.tmp_path / 'level_z.json'
        _write_level_json(f, [{'number': 1, 'name': 'Unmarked Room', 'exits': {}, 'desc': 'x'}])
        m = Map()
        m.read_map(str(f), level=11)
        self.assertEqual(m.levels[11][1].alignment, RoomAlignment.NEUTRAL)

    def test_missing_file_does_not_crash(self):
        m = Map()
        m.read_map(str(self.tmp_path / 'does_not_exist.json'), level=5)
        self.assertNotIn(5, m.levels)


if __name__ == '__main__':
    unittest.main(verbosity=2)
