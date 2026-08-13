"""tests/test_visited_rooms.py — Unit tests for visited_rooms.py: the
per-level "have you been here" bitfield, packed MSB-first per byte and
hex-encoded, same convention GBBS's own message-store header uses (see
LEVEL_AUDIT.md's room-renumbering investigation for that precedent).
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from visited_rooms import (
    GRID_WIDTH, grid_capacity, mark_visited, is_visited, visited_room_numbers,
)


def make_player():
    p = MagicMock()
    p.visited_rooms = {}
    p.unsaved_changes = False
    return p


class TestGridCapacity(unittest.TestCase):

    def test_all_seven_levels_known(self):
        for level in range(1, 8):
            self.assertIn(level, GRID_WIDTH)

    def test_capacity_is_ri_squared(self):
        self.assertEqual(grid_capacity(6), 900)   # 30x30
        self.assertEqual(grid_capacity(4), 49)    # 7x7

    def test_unknown_level_returns_none(self):
        self.assertIsNone(grid_capacity(99))


class TestMarkAndIsVisited(unittest.TestCase):

    def test_unvisited_room_is_false(self):
        p = make_player()
        self.assertFalse(is_visited(p, 4, 1))

    def test_marking_makes_it_visited(self):
        p = make_player()
        mark_visited(p, 4, 1)
        self.assertTrue(is_visited(p, 4, 1))

    def test_marking_sets_unsaved_changes(self):
        p = make_player()
        mark_visited(p, 4, 1)
        self.assertTrue(p.unsaved_changes)

    def test_marking_already_visited_is_a_noop(self):
        p = make_player()
        mark_visited(p, 4, 1)
        p.unsaved_changes = False
        mark_visited(p, 4, 1)
        self.assertFalse(p.unsaved_changes)

    def test_marking_does_not_affect_other_rooms(self):
        p = make_player()
        mark_visited(p, 4, 1)
        self.assertFalse(is_visited(p, 4, 2))

    def test_marking_does_not_affect_other_levels(self):
        p = make_player()
        mark_visited(p, 4, 1)
        self.assertFalse(is_visited(p, 5, 1))

    def test_lazily_creates_visited_rooms_dict(self):
        p = MagicMock()
        p.visited_rooms = None  # simulate a Player without one yet
        mark_visited(p, 4, 1)
        self.assertIn('4', p.visited_rooms)

    def test_out_of_range_room_number_ignored(self):
        p = make_player()
        mark_visited(p, 4, 50)  # level 4's grid only has 49 rooms
        self.assertEqual(p.visited_rooms, {})

    def test_room_at_capacity_boundary(self):
        p = make_player()
        mark_visited(p, 4, 49)  # last room on a 7x7 grid
        self.assertTrue(is_visited(p, 4, 49))

    def test_room_one_past_capacity_is_ignored(self):
        p = make_player()
        self.assertFalse(is_visited(p, 4, 50))

    def test_unknown_level_ignored(self):
        p = make_player()
        mark_visited(p, 99, 1)
        self.assertEqual(p.visited_rooms, {})


class TestVisitedRoomNumbers(unittest.TestCase):

    def test_empty_when_nothing_visited(self):
        p = make_player()
        self.assertEqual(visited_room_numbers(p, 4), set())

    def test_returns_every_marked_room(self):
        p = make_player()
        for room in (1, 8, 49):
            mark_visited(p, 4, room)
        self.assertEqual(visited_room_numbers(p, 4), {1, 8, 49})

    def test_hex_round_trips_across_byte_boundaries(self):
        # Level 6's grid is 900 rooms (113 bytes) -- exercise bit
        # positions spanning several byte boundaries, including the
        # very first and very last bit.
        p = make_player()
        rooms = {1, 8, 9, 113, 500, 900}
        for room in rooms:
            mark_visited(p, 6, room)
        self.assertEqual(visited_room_numbers(p, 6), rooms)

    def test_hex_string_length_matches_grid_capacity(self):
        p = make_player()
        mark_visited(p, 6, 1)
        # ceil(900/8) = 113 bytes = 226 hex characters.
        self.assertEqual(len(p.visited_rooms['6']), 226)


if __name__ == '__main__':
    unittest.main()
