"""tests/movement/test_level_2_7_exit_resolution.py

Regression test for a real bug Ryan found live: level_2.json through
level_7.json's N/S/E/W exit values were never resolved from the raw
room-database's 0/1 "an exit exists here" flag into an actual
destination room number -- every exit in every direction on those
levels was left as the literal value 1, so moving in ANY direction
from ANY room on levels 2-6 always sent the player to room #1.

SPUR's own formula for resolving these (SPUR-code/SPUR.CONTROL.S lines
527-530; text-listings/t_main.lbl lines 1010/1067-1070, which calls the
current room `cr` -- Ryan's own term for it) is a wraparound grid: N/S
add/subtract the level's row width (`ri`, aka "Room Incr." in the level
editor), E/W add/subtract 1, both wrapping at the grid edge. Fixed by
resolving exits in place in the shipped level_2.json..level_7.json
files (SPUR-data/level-2/tada_level_builder.py's
resolve_exit_destinations(), used by parse_message()).

level_1.json is unaffected -- it's built by a separate pipeline
(convert_map_data.py) that already stores resolved destination numbers.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent.parent

# (ri = map_width/row stride, nr = total room slots), from each level's
# D.LEVEL{n}.TXT header -- see SPUR-data/level-2/tada_level_builder.py's
# LevelHeader.read().
_LEVEL_GRID = {
    2: (15, 225),
    3: (10, 100),
    4: (7, 49),
    5: (20, 400),
    6: (30, 900),
    7: (10, 100),
}

_DIRECTIONS = ('north', 'south', 'east', 'west')


def _load_rooms(level: int) -> list[dict]:
    path = _SERVER_DIR / f'level_{level}.json'
    return json.loads(path.read_text())['rooms']


class TestLevel2Through7ExitsAreResolved(unittest.TestCase):

    def test_not_every_exit_points_to_room_one(self):
        """The bug's exact symptom: every N/S/E/W exit collapsed to the
        literal flag value 1. A fixed level should have exits spread
        across many destination rooms, not universally 1."""
        for level in _LEVEL_GRID:
            rooms = _load_rooms(level)
            destinations = {
                room['exits'][d]
                for room in rooms
                for d in _DIRECTIONS
                if d in room['exits']
            }
            self.assertGreater(
                len(destinations), 5,
                f'level {level}: exits only ever point to '
                f'{sorted(destinations)} -- looks unresolved',
            )

    def test_exits_are_reachable_room_numbers(self):
        """Every resolved exit must land on a room number that's within
        the level's own valid range 1..total_rooms."""
        for level, (ri, nr) in _LEVEL_GRID.items():
            rooms = _load_rooms(level)
            for room in rooms:
                for d in _DIRECTIONS:
                    dest = room['exits'].get(d)
                    if dest is None:
                        continue
                    self.assertTrue(
                        1 <= dest <= nr,
                        f'level {level} room {room["number"]} {d}={dest} '
                        f'out of range 1..{nr}',
                    )

    def test_east_west_are_adjacent_within_a_row(self):
        """An 'east' exit's destination must be exactly +1 (mod wraparound
        at the row edge) -- i.e. moving east actually moves you one room
        over, not to some unrelated room."""
        for level, (ri, nr) in _LEVEL_GRID.items():
            rooms = _load_rooms(level)
            for room in rooms:
                cr = room['number']
                east = room['exits'].get('east')
                if east is not None:
                    expected = cr + 1 - (ri if cr % ri == 0 else 0)
                    self.assertEqual(east, expected,
                                      f'level {level} room {cr} east')
                west = room['exits'].get('west')
                if west is not None:
                    expected = cr + (ri if cr % ri == 1 else 0) - 1
                    self.assertEqual(west, expected,
                                      f'level {level} room {cr} west')

    def test_north_south_are_offset_by_row_width(self):
        """A 'south' exit's destination must be exactly +ri (mod
        wraparound at the bottom edge), matching SPUR's own row-stride
        formula -- Ryan's report: "the ri * ri level dimensions (stride)
        is accounted for ... adding to the room number"."""
        for level, (ri, nr) in _LEVEL_GRID.items():
            rooms = _load_rooms(level)
            for room in rooms:
                cr = room['number']
                south = room['exits'].get('south')
                if south is not None:
                    expected = cr + ri - (nr if cr > (nr - ri) else 0)
                    self.assertEqual(south, expected,
                                      f'level {level} room {cr} south')
                north = room['exits'].get('north')
                if north is not None:
                    expected = (nr if cr <= ri else 0) + cr - ri
                    self.assertEqual(north, expected,
                                      f'level {level} room {cr} north')

    def test_level_1_still_uses_its_own_already_resolved_format(self):
        """level_1.json comes from a different pipeline (convert_map_data.py)
        that already stores resolved destination numbers -- this bug/fix
        never touched it, so it should still load/behave as before."""
        rooms = _load_rooms(1)
        self.assertGreater(len(rooms), 0)
        destinations = {
            room['exits'][d]
            for room in rooms
            for d in _DIRECTIONS
            if d in room['exits']
        }
        self.assertGreater(len(destinations), 5)


if __name__ == '__main__':
    unittest.main()
