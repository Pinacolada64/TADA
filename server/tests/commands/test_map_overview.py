"""tests/commands/test_map_overview.py — Unit tests for commands/map.py's
`map #overview [<level>]` subcommand: a Debug-Mode-gated, compressed
birds-eye grid of an entire level -- one reverse-video square per room,
with arrow glyphs marking which of north/east/south/west have an exit.
No monster/item/weapon/food markers and no up/down exits (see
render_ansi_grid() for the nearby-rooms box view that has those).
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from commands.map import MapCommand, render_overview, _OVERVIEW_GRID_WIDTH
from terminal import ClientSettings, Translation


def run(coro):
    return asyncio.run(coro)


class _FakeRoom:
    def __init__(self, number, exits=None):
        self.number = number
        self.exits = exits or {}


def make_player(*, debug=True, map_level=4, map_room=1, translation=Translation.ANSI):
    p = MagicMock()
    p.map_level = map_level
    p.map_room = map_room
    p.query_flag.side_effect = lambda flag: debug
    p.visited_rooms = {}  # real dict -- mark_visited() needs this, not a MagicMock
    cs = ClientSettings()
    cs.translation = translation
    p.client_settings = cs
    return p


def make_ctx(player, levels: dict):
    game_map = MagicMock()
    game_map.levels = levels
    ctx = MagicMock()
    ctx.player = player
    ctx.server.game_map = game_map
    sent = []

    async def _send(msg, **kw):
        sent.extend(msg) if isinstance(msg, list) else sent.append(msg)
    ctx.send = _send
    ctx._sent = sent
    return ctx


def sent_text(ctx) -> str:
    return '\n'.join(ctx._sent)


class TestDebugGate(unittest.TestCase):

    def test_non_debug_player_rejected(self):
        player = make_player(debug=False)
        ctx = make_ctx(player, {4: {1: _FakeRoom(1)}})
        result = run(MapCommand().execute(ctx, '#overview'))
        self.assertFalse(result.success)
        self.assertIn('Debug Mode', sent_text(ctx))

    def test_debug_player_allowed(self):
        player = make_player(debug=True)
        ctx = make_ctx(player, {4: {1: _FakeRoom(1)}})
        result = run(MapCommand().execute(ctx, '#overview'))
        self.assertTrue(result.success)


class TestLevelArgument(unittest.TestCase):

    def test_defaults_to_players_own_level(self):
        player = make_player(debug=True, map_level=4)
        ctx = make_ctx(player, {4: {1: _FakeRoom(1)}})
        result = run(MapCommand().execute(ctx, '#overview'))
        self.assertTrue(result.success)
        self.assertIn('Level 4 overview', sent_text(ctx))

    def test_explicit_level_argument(self):
        player = make_player(debug=True, map_level=4)
        ctx = make_ctx(player, {3: {1: _FakeRoom(1)}})
        result = run(MapCommand().execute(ctx, '#overview', '3'))
        self.assertTrue(result.success)
        self.assertIn('Level 3 overview', sent_text(ctx))

    def test_non_numeric_level_rejected(self):
        player = make_player(debug=True)
        ctx = make_ctx(player, {4: {1: _FakeRoom(1)}})
        result = run(MapCommand().execute(ctx, '#overview', 'banana'))
        self.assertFalse(result.success)

    def test_level_with_no_room_data(self):
        player = make_player(debug=True, map_level=4)
        ctx = make_ctx(player, {})
        result = run(MapCommand().execute(ctx, '#overview'))
        self.assertFalse(result.success)
        self.assertIn('No overview data', sent_text(ctx))


class TestRenderOverview(unittest.TestCase):
    """Direct tests of render_overview()'s grid layout, using level 4
    (ri=7, small enough for hand-checked positions)."""

    def test_all_seven_levels_have_a_known_grid_width(self):
        for level in range(1, 8):
            self.assertIn(level, _OVERVIEW_GRID_WIDTH)

    def test_player_room_marked_with_at_sign(self):
        # Rooms 1 and 2 are adjacent on row 0 (ri=7): room 1 has an east
        # exit to room 2; room 2 has no west exit back, so it's one-way.
        rooms = {
            1: _FakeRoom(1, exits={'east': 2}),
            2: _FakeRoom(2),
        }
        player = make_player(debug=True, map_level=4, map_room=1)
        ctx = MagicMock()
        ctx.player = player
        lines = render_overview(ctx, MagicMock(levels={4: rooms}), 4, player)
        self.assertIsNotNone(lines)
        # Room row is line 0 (no room above row 0 needs a north-arrow row).
        self.assertIn('@', lines[0])
        self.assertIn('→', lines[0])

    def test_mutual_exit_gets_double_headed_arrow_on_ansi(self):
        rooms = {
            1: _FakeRoom(1, exits={'east': 2}),
            2: _FakeRoom(2, exits={'west': 1}),
        }
        player = make_player(debug=True, map_level=4, map_room=1,
                              translation=Translation.ANSI)
        ctx = MagicMock()
        ctx.player = player
        lines = render_overview(ctx, MagicMock(levels={4: rooms}), 4, player)
        self.assertIn('↔', lines[0])
        self.assertNotIn('→', lines[0])
        self.assertNotIn('←', lines[0])

    def test_mutual_exit_falls_back_to_single_arrow_on_petscii(self):
        # ri=7 for level 4, so room 8 (row 1, col 0) sits directly south
        # of room 1 (row 0, col 0) -- room 2 would be room 1's *east*
        # neighbor, not south.
        rooms = {
            1: _FakeRoom(1, exits={'south': 8}),
            8: _FakeRoom(8, exits={'north': 1}),
        }
        player = make_player(debug=True, map_level=4, map_room=1,
                              translation=Translation.PETSCII)
        ctx = MagicMock()
        ctx.player = player
        lines = render_overview(ctx, MagicMock(levels={4: rooms}), 4, player)
        joined = '\n'.join(lines)
        self.assertNotIn('↕', joined)
        self.assertIn('v', lines[1])  # the arrow-gap row between the two rooms

    def test_no_exit_no_arrow(self):
        rooms = {1: _FakeRoom(1)}
        player = make_player(debug=True, map_level=4, map_room=1)
        ctx = MagicMock()
        ctx.player = player
        lines = render_overview(ctx, MagicMock(levels={4: rooms}), 4, player)
        self.assertIsNotNone(lines)
        # Only check the grid canvas itself, not the legend line below it
        # (which always shows the arrow glyphs as a key).
        grid = lines[:lines.index('')]
        for glyph in ('↑', '↓', '→', '←'):
            self.assertNotIn(glyph, '\n'.join(grid))

    def test_petscii_client_gets_ascii_arrows(self):
        rooms = {
            1: _FakeRoom(1, exits={'east': 2}),
            2: _FakeRoom(2),
        }
        player = make_player(debug=True, map_level=4, map_room=1,
                              translation=Translation.PETSCII)
        ctx = MagicMock()
        ctx.player = player
        lines = render_overview(ctx, MagicMock(levels={4: rooms}), 4, player)
        joined = '\n'.join(lines)
        self.assertIn('>', joined)
        self.assertNotIn('→', joined)

    def test_returns_none_for_unknown_level(self):
        player = make_player(debug=True)
        ctx = MagicMock()
        ctx.player = player
        lines = render_overview(ctx, MagicMock(levels={}), 4, player)
        self.assertIsNone(lines)

    def test_legend_samples_are_reverse_video_like_the_real_grid(self):
        # Ryan found: the legend's '=room' sample was a bare space with
        # no |reverse_on|/|reverse_off| wrapping, so it looked like
        # nothing next to the label -- an anomaly, since the actual grid
        # cells (see the `@`/color-cell assignment above) are always
        # reverse-video wrapped via _serialize_canvas_row(). Both legend
        # samples ('=you' and '=room') must carry the same markup pair
        # the real cells do.
        rooms = {1: _FakeRoom(1)}
        player = make_player(debug=True, map_level=4, map_room=1)
        ctx = MagicMock()
        ctx.player = player
        lines = render_overview(ctx, MagicMock(levels={4: rooms}), 4, player)
        legend = lines[lines.index('') + 1]
        self.assertIn('|reverse_on|@|reverse_off|', legend)
        self.assertIn('|reverse_on| |reverse_off|', legend)

    def test_allowed_filter_excludes_unlisted_rooms(self):
        rooms = {
            1: _FakeRoom(1, exits={'east': 2}),
            2: _FakeRoom(2, exits={'west': 1}),
        }
        player = make_player(debug=True, map_level=4, map_room=1)
        ctx = MagicMock()
        ctx.player = player
        lines = render_overview(ctx, MagicMock(levels={4: rooms}), 4, player,
                                 allowed={1})
        # Room 2 excluded -- only a one-way arrow toward it (room 1's own
        # east exit exists), never the mutual double-headed one, since a
        # room outside `allowed` can't tell us it has an exit back.
        self.assertIn('@', lines[0])
        self.assertIn('→', lines[0])
        self.assertNotIn('↔', lines[0])

    def test_allowed_filter_empty_returns_none(self):
        rooms = {1: _FakeRoom(1)}
        player = make_player(debug=True, map_level=4, map_room=1)
        ctx = MagicMock()
        ctx.player = player
        lines = render_overview(ctx, MagicMock(levels={4: rooms}), 4, player,
                                 allowed=set())
        self.assertIsNone(lines)


class TestVisitedSubcommand(unittest.TestCase):
    """`map #visited [<level>]` -- unlike #overview, available to every
    player regardless of Debug Mode, and only ever shows rooms actually
    marked visited (visited_rooms.py)."""

    def test_available_without_debug_mode(self):
        player = make_player(debug=False, map_level=4, map_room=1)
        ctx = make_ctx(player, {4: {1: _FakeRoom(1)}})
        from visited_rooms import mark_visited
        mark_visited(player, 4, 1)
        result = run(MapCommand().execute(ctx, '#visited'))
        self.assertTrue(result.success)

    def test_nothing_visited_yet(self):
        player = make_player(debug=False, map_level=4, map_room=1)
        player.visited_rooms = {}
        ctx = make_ctx(player, {4: {1: _FakeRoom(1)}})
        result = run(MapCommand().execute(ctx, '#visited'))
        self.assertFalse(result.success)
        self.assertIn("haven't explored", sent_text(ctx))

    def test_defaults_to_players_own_level(self):
        player = make_player(debug=False, map_level=4, map_room=1)
        ctx = make_ctx(player, {4: {1: _FakeRoom(1)}})
        from visited_rooms import mark_visited
        mark_visited(player, 4, 1)
        result = run(MapCommand().execute(ctx, '#visited'))
        self.assertTrue(result.success)
        self.assertIn('Level 4', sent_text(ctx))

    def test_explicit_level_argument(self):
        player = make_player(debug=False, map_level=4, map_room=1)
        ctx = make_ctx(player, {3: {1: _FakeRoom(1)}})
        from visited_rooms import mark_visited
        mark_visited(player, 3, 1)
        result = run(MapCommand().execute(ctx, '#visited', '3'))
        self.assertTrue(result.success)
        self.assertIn('Level 3', sent_text(ctx))

    def test_non_numeric_level_rejected(self):
        player = make_player(debug=False)
        ctx = make_ctx(player, {4: {1: _FakeRoom(1)}})
        result = run(MapCommand().execute(ctx, '#visited', 'banana'))
        self.assertFalse(result.success)

    def test_only_visited_rooms_render(self):
        rooms = {
            1: _FakeRoom(1, exits={'east': 2}),
            2: _FakeRoom(2, exits={'west': 1}),
        }
        player = make_player(debug=False, map_level=4, map_room=1)
        ctx = make_ctx(player, {4: rooms})
        from visited_rooms import mark_visited
        mark_visited(player, 4, 1)  # room 2 deliberately left unvisited
        result = run(MapCommand().execute(ctx, '#visited'))
        self.assertTrue(result.success)
        # Grid content is the line right after the header/blank -- the
        # legend below always mentions both glyph kinds as a key.
        grid_line = ctx._sent[2]
        self.assertIn('→', grid_line)     # room 1's own exit still shown
        self.assertNotIn('↔', grid_line)  # but not the mutual, unverifiable one


if __name__ == '__main__':
    unittest.main()
