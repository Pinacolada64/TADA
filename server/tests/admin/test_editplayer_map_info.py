"""tests/admin/test_editplayer_map_info.py

commands/editplayer.py's Map Information (MI) menu: Room Number's
dot-leader and edit prompt should show the room's actual name (not just
its number), and '?' at the Room Number prompt should list every room on
the player's current dungeon level.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from base_classes import Room
from commands.editplayer import _map_info_menu


def _make_room(number, name):
    return Room(number=number, name=name, desc='')


def _make_server_with_rooms():
    server = MagicMock()
    game_map = MagicMock()
    game_map.levels = {
        1: {
            1: _make_room(1, 'Merchant Lobby'),
            2: _make_room(2, 'Rolling Hills'),
        },
    }
    server.game_map = game_map
    return server


def _action_for(menu, shortcut):
    for item in menu.menu_items:
        if shortcut in item.shortcuts:
            return item
    raise AssertionError(f'no menu item with shortcut {shortcut!r}')


def _make_ctx(player, server, responses):
    ctx = MagicMock()
    ctx.player = player
    ctx.server = server
    ctx.send = AsyncMock()
    it = iter(responses)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    return ctx


def _make_player(map_level=1, map_room=1):
    player = MagicMock()
    player.map_level = map_level
    player.map_room = map_room
    return player


class TestRoomNumberDotLeader(unittest.TestCase):

    def test_dot_leader_shows_room_name_when_loaded(self):
        player = _make_player(map_level=1, map_room=2)
        server = _make_server_with_rooms()
        ctx = _make_ctx(player, server, [])
        menu = _map_info_menu(ctx)
        item = _action_for(menu, 'rn')
        self.assertEqual(item.dot_leader_handler(ctx), '2 (Rolling Hills)')

    def test_dot_leader_falls_back_to_bare_number_when_unloaded(self):
        player = _make_player(map_level=1, map_room=999)
        server = _make_server_with_rooms()
        ctx = _make_ctx(player, server, [])
        menu = _map_info_menu(ctx)
        item = _action_for(menu, 'rn')
        self.assertEqual(item.dot_leader_handler(ctx), '999')


class TestRoomNumberEdit(unittest.IsolatedAsyncioTestCase):

    async def test_setting_a_valid_room_shows_its_name(self):
        player = _make_player(map_level=1, map_room=1)
        server = _make_server_with_rooms()
        ctx = _make_ctx(player, server, ['2'])
        menu = _map_info_menu(ctx)

        await _action_for(menu, 'rn').action(ctx)

        self.assertEqual(player.map_room, 2)
        self.assertTrue(player.unsaved_changes)
        flat = '\n'.join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn('Room Number set to 2 (Rolling Hills).', flat)

    async def test_question_mark_lists_rooms_then_reprompts(self):
        player = _make_player(map_level=1, map_room=1)
        server = _make_server_with_rooms()
        ctx = _make_ctx(player, server, ['?', '2'])
        menu = _map_info_menu(ctx)

        await _action_for(menu, 'rn').action(ctx)

        flat = '\n'.join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn('Merchant Lobby', flat)
        self.assertIn('Rolling Hills', flat)
        self.assertEqual(player.map_room, 2)

    async def test_question_mark_with_no_room_data_reports_that(self):
        player = _make_player(map_level=5, map_room=1)
        server = _make_server_with_rooms()  # no data for level 5
        ctx = _make_ctx(player, server, ['?', ''])
        menu = _map_info_menu(ctx)

        await _action_for(menu, 'rn').action(ctx)

        flat = '\n'.join(str(a) for call in ctx.send.await_args_list for a in call.args)
        self.assertIn('No room data loaded for level 5.', flat)

    async def test_blank_cancels_without_changing_room(self):
        player = _make_player(map_level=1, map_room=1)
        server = _make_server_with_rooms()
        ctx = _make_ctx(player, server, [''])
        menu = _map_info_menu(ctx)

        await _action_for(menu, 'rn').action(ctx)

        self.assertEqual(player.map_room, 1)

    async def test_out_of_range_number_reprompts(self):
        player = _make_player(map_level=1, map_room=1)
        server = _make_server_with_rooms()
        ctx = _make_ctx(player, server, ['1000', '2'])
        menu = _map_info_menu(ctx)

        await _action_for(menu, 'rn').action(ctx)

        self.assertEqual(player.map_room, 2)

    async def test_non_numeric_input_reprompts(self):
        player = _make_player(map_level=1, map_room=1)
        server = _make_server_with_rooms()
        ctx = _make_ctx(player, server, ['abc', '2'])
        menu = _map_info_menu(ctx)

        await _action_for(menu, 'rn').action(ctx)

        self.assertEqual(player.map_room, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
