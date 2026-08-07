"""tests/commands/test_map.py — Unit tests for commands/map.py.

Ports SPUR.MISC5.S:13's '#'-bound Ranger `ranger` ability under the
'map' command name (this port's '#' already belongs to the admin debug
TeleportCommand). Renders nearby rooms via BFS over live .exits links
instead of SPUR-data/level-1/map_explorer.py's grid-math
render_minimap(), which needs a map_width the live server has never
loaded for any level.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from base_classes import PlayerClass
from commands.map import MapCommand, _nearby_rooms, _dwarf_hint
from flags import PlayerFlags
from network_context import GameContext


def run(coro):
    return asyncio.run(coro)


class _FakeRoom:
    def __init__(self, number, name, exits=None, monster=0, item=0, weapon=0, food=0):
        self.number = number
        self.name = name
        self.exits = exits or {}
        self.monster = monster
        self.item = item
        self.weapon = weapon
        self.food = food


def make_player(*, char_class=PlayerClass.RANGER, xp_level=3,
                map_level=1, map_room=1, admin=False, dm=False) -> MagicMock:
    p = MagicMock()
    p.char_class = char_class
    p.xp_level = xp_level
    p.map_level = map_level
    p.map_room = map_room

    def _query_flag(flag):
        if flag == PlayerFlags.ADMIN:         return admin
        if flag == PlayerFlags.DUNGEON_MASTER: return dm
        return False

    p.query_flag.side_effect = _query_flag
    return p


def make_game_map(rooms: dict) -> MagicMock:
    gm = MagicMock()
    gm.get_room.side_effect = lambda level, n: rooms.get(n)
    return gm


def make_ctx(player, game_map) -> MagicMock:
    ctx = MagicMock()
    ctx.player = player
    ctx.server.game_map = game_map
    ctx.send = AsyncMock()
    return ctx


def sent_text(ctx) -> str:
    parts = []
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


# A small 3x3-ish grid, room 1 in the center-ish, for BFS tests.
#   4
#   |
# 2-1-3
#   |
#   5-6
def _sample_rooms():
    return {
        1: _FakeRoom(1, 'Center', exits={'north': 4, 'south': 5, 'east': 3, 'west': 2}),
        2: _FakeRoom(2, 'West Room', exits={'east': 1}),
        3: _FakeRoom(3, 'East Room', exits={'west': 1}, monster=5),
        4: _FakeRoom(4, 'North Room', exits={'south': 1}, item=10),
        5: _FakeRoom(5, 'South Room', exits={'north': 1, 'east': 6}),
        6: _FakeRoom(6, 'Southeast Room', exits={'west': 5}),
    }


class TestGating(unittest.TestCase):
    def test_non_ranger_is_refused(self):
        player = make_player(char_class=PlayerClass.FIGHTER)
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        result = run(MapCommand().execute(ctx))
        self.assertFalse(result.success)
        self.assertIn('Ranger', sent_text(ctx))

    def test_ranger_below_level_3_is_refused(self):
        player = make_player(xp_level=2)
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        result = run(MapCommand().execute(ctx))
        self.assertFalse(result.success)
        self.assertIn('level 3', sent_text(ctx))

    def test_ranger_at_level_3_succeeds(self):
        player = make_player(xp_level=3)
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        result = run(MapCommand().execute(ctx))
        self.assertTrue(result.success)

    def test_missing_room_data_fails_gracefully(self):
        player = make_player(map_room=999)
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        result = run(MapCommand().execute(ctx))
        self.assertFalse(result.success)
        self.assertIn('no map data', sent_text(ctx))


class TestNearbyRoomsBFS(unittest.TestCase):
    def test_depth_1_finds_direct_neighbors_only(self):
        rooms = _sample_rooms()
        gm = make_game_map(rooms)
        visited = _nearby_rooms(gm, 1, 1, depth=1)
        self.assertEqual(set(visited.keys()), {1, 2, 3, 4, 5})

    def test_depth_2_reaches_further_rooms(self):
        rooms = _sample_rooms()
        gm = make_game_map(rooms)
        visited = _nearby_rooms(gm, 1, 1, depth=2)
        self.assertEqual(set(visited.keys()), {1, 2, 3, 4, 5, 6})
        self.assertEqual(visited[6], ['S', 'E'])

    def test_start_room_has_empty_path(self):
        rooms = _sample_rooms()
        gm = make_game_map(rooms)
        visited = _nearby_rooms(gm, 1, 1, depth=1)
        self.assertEqual(visited[1], [])

    def test_rc_rt_exits_are_not_traversed(self):
        rooms = {
            1: _FakeRoom(1, 'Lobby', exits={'south': 13, 'rc': 2}),
            13: _FakeRoom(13, 'Passage', exits={'north': 1}),
        }
        gm = make_game_map(rooms)
        visited = _nearby_rooms(gm, 1, 1, depth=3)
        # rc:2 isn't a real room number in this level's exits -- only the
        # real cardinal 'south' link should be followed.
        self.assertEqual(set(visited.keys()), {1, 13})


class TestMapOutput(unittest.TestCase):
    def test_shows_current_room_name(self):
        player = make_player()
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        run(MapCommand().execute(ctx))
        self.assertIn('Center', sent_text(ctx))

    def test_lists_nearby_room_names_and_directions(self):
        player = make_player()
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        run(MapCommand().execute(ctx))
        text = sent_text(ctx)
        self.assertIn('North Room', text)
        self.assertIn('East Room', text)
        self.assertIn('South Room', text)
        self.assertIn('West Room', text)

    def test_monster_and_item_markers_shown(self):
        player = make_player()
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        run(MapCommand().execute(ctx))
        text = sent_text(ctx)
        self.assertIn('|red|M|reset|', text)   # East Room has a monster
        self.assertIn('|orange|I|reset|', text)  # North Room has an item

    def test_legend_is_shown(self):
        player = make_player()
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        run(MapCommand().execute(ctx))
        text = sent_text(ctx)
        self.assertIn('monster', text)
        self.assertIn('item', text)
        self.assertIn('weapon', text)
        self.assertIn('food', text)

    def test_no_dwarf_hint_on_other_levels(self):
        player = make_player(map_level=2)
        rooms = {1: _FakeRoom(1, 'Some Room')}
        ctx = make_ctx(player, make_game_map(rooms))
        run(MapCommand().execute(ctx))
        text = sent_text(ctx)
        self.assertNotIn('Dwarf', text)


class TestRoomNumberPrivacy(unittest.TestCase):
    """Room numbers are only shown to privileged players (Admin/DM) --
    an ordinary player gets the direction path and room name only."""

    def test_ordinary_player_does_not_see_room_numbers(self):
        player = make_player()  # admin=False, dm=False by default
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        run(MapCommand().execute(ctx))
        text = sent_text(ctx)
        self.assertNotIn('#1', text)
        self.assertNotIn('#3', text)
        self.assertNotIn('#4', text)
        self.assertNotIn('#5', text)
        # still shows the path/name/markers
        self.assertIn('North Room', text)

    def test_admin_sees_room_numbers(self):
        player = make_player(admin=True)
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        run(MapCommand().execute(ctx))
        text = sent_text(ctx)
        self.assertIn('Room #1', text)
        self.assertIn('#3', text)
        self.assertIn('#4', text)

    def test_dungeon_master_sees_room_numbers(self):
        player = make_player(dm=True)
        ctx = make_ctx(player, make_game_map(_sample_rooms()))
        run(MapCommand().execute(ctx))
        self.assertIn('Room #1', sent_text(ctx))


class TestDwarfHint(unittest.TestCase):
    def test_no_hint_when_dwarf_not_placed(self):
        with unittest.mock.patch('encounters.dwarf.is_placed', return_value=False):
            hint = _dwarf_hint(make_game_map(_sample_rooms()), 1, 1)
        self.assertIsNone(hint)

    def test_no_hint_on_other_levels(self):
        hint = _dwarf_hint(make_game_map(_sample_rooms()), 2, 1)
        self.assertIsNone(hint)

    def test_hint_when_dwarf_is_in_the_same_room(self):
        with unittest.mock.patch('encounters.dwarf.is_placed', return_value=True), \
             unittest.mock.patch('encounters.dwarf.current_room', return_value=1):
            hint = _dwarf_hint(make_game_map(_sample_rooms()), 1, 1)
        self.assertIn('right here', hint)

    def test_hint_when_dwarf_is_close(self):
        with unittest.mock.patch('encounters.dwarf.is_placed', return_value=True), \
             unittest.mock.patch('encounters.dwarf.current_room', return_value=3):
            hint = _dwarf_hint(make_game_map(_sample_rooms()), 1, 1)
        self.assertIn('close by', hint)

    def test_hint_when_dwarf_is_unreachable(self):
        rooms = {1: _FakeRoom(1, 'Isolated Room')}
        with unittest.mock.patch('encounters.dwarf.is_placed', return_value=True), \
             unittest.mock.patch('encounters.dwarf.current_room', return_value=99):
            hint = _dwarf_hint(make_game_map(rooms), 1, 1)
        self.assertIn('no trace', hint)


if __name__ == '__main__':
    unittest.main()
