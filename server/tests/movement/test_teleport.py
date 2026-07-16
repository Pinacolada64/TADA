"""tests/test_teleport.py"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.teleport import TeleportCommand
from flags import PlayerFlags


def make_ctx(*, is_admin=True, is_dm=False, room=1, rooms=None):
    if rooms is None:
        rooms = {1: object(), 37: object()}

    player = MagicMock()
    player.name = 'TestPlayer'

    def _query_flag(f):
        if f == PlayerFlags.ADMIN:         return is_admin
        if f == PlayerFlags.DUNGEON_MASTER: return is_dm
        return False
    player.query_flag = MagicMock(side_effect=_query_flag)

    server = MagicMock()
    server.game_map.rooms = rooms
    server.game_map.levels = {1: rooms}
    server.game_map.get_room = lambda level, room_no: rooms.get(room_no)
    server._show_room = AsyncMock()

    client = MagicMock()
    client.room = room

    ctx = MagicMock()
    ctx.player   = player
    ctx.server   = server
    ctx.client   = client
    ctx.send     = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


class TestTeleportPermission(unittest.IsolatedAsyncioTestCase):

    async def test_non_privileged_denied(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False, is_dm=False)
        res = await cmd.execute(ctx, '37')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'permission_denied')

    async def test_non_privileged_no_room_change(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False, is_dm=False, room=1)
        await cmd.execute(ctx, '37')
        self.assertEqual(ctx.client.room, 1)

    async def test_admin_allowed(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=True)
        res = await cmd.execute(ctx, '37')
        self.assertTrue(res.success)

    async def test_admin_room_changed(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=True)
        await cmd.execute(ctx, '37')
        self.assertEqual(ctx.client.room, 37)

    async def test_dm_allowed(self):
        """Ryan's request: teleport should work for Dungeon Masters too,
        not just Administrators."""
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False, is_dm=True)
        res = await cmd.execute(ctx, '37')
        self.assertTrue(res.success)
        self.assertEqual(ctx.client.room, 37)


class TestTeleportArgs(unittest.IsolatedAsyncioTestCase):

    async def test_no_args_fails(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'missing_args')

    async def test_bad_room_number_fails(self):
        # Non-numeric input is treated as a name search, not a malformed
        # room number -- "abc" matches no room name, so this fails as
        # 'no_match', not a separate 'bad_args' code.
        cmd = TeleportCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx, 'abc')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'no_match')

    async def test_nonexistent_room_fails(self):
        cmd = TeleportCommand()
        ctx = make_ctx(rooms={1: object()})
        res = await cmd.execute(ctx, '99')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'bad_room')

    async def test_space_separated_variant(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx, '#', '37')
        self.assertTrue(res.success)
        self.assertEqual(ctx.client.room, 37)


def make_multilevel_ctx(*, is_admin=True, current_level=1, current_room=1, levels=None):
    """Like make_ctx() but with real per-level rooms, for #<level> <room>
    teleport tests (make_ctx()'s get_room ignores level entirely)."""
    if levels is None:
        levels = {1: {1: object()}, 5: {18: object()}}

    player = MagicMock()
    player.name = 'TestPlayer'
    player.map_level = current_level
    player.query_flag = MagicMock(
        side_effect=lambda f: f == PlayerFlags.ADMIN and is_admin
    )

    server = MagicMock()
    server.game_map.levels = levels
    server.game_map.get_room = lambda level, room_no: levels.get(level, {}).get(room_no)
    server._show_room = AsyncMock()

    client = MagicMock()
    client.room = current_room

    ctx = MagicMock()
    ctx.player    = player
    ctx.server    = server
    ctx.client    = client
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


class TestTeleportWithLevel(unittest.IsolatedAsyncioTestCase):
    """'#<room>' alone stays on the current level; '#<level> <room>'
    (two numeric args) jumps to a specific level -- Ryan's request."""

    async def test_single_arg_stays_on_current_level(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1)
        res = await cmd.execute(ctx, '1')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.map_level, 1)
        self.assertEqual(ctx.client.room, 1)

    async def test_two_args_jumps_to_specified_level(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1)
        res = await cmd.execute(ctx, '5', '18')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.map_level, 5)
        self.assertEqual(ctx.client.room, 18)

    async def test_two_args_also_updates_client_map_level(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1)
        await cmd.execute(ctx, '5', '18')
        self.assertEqual(ctx.client.map_level, 5)

    async def test_two_args_room_not_on_that_level_fails(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1)
        res = await cmd.execute(ctx, '5', '99')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'bad_room')
        # No partial teleport on failure.
        self.assertEqual(ctx.player.map_level, 1)

    async def test_two_args_same_level_as_current_is_a_no_op_level_change(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1, levels={1: {1: object(), 2: object()}})
        res = await cmd.execute(ctx, '1', '2')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.map_level, 1)
        self.assertEqual(ctx.client.room, 2)


class TestTeleportFlashMessages(unittest.IsolatedAsyncioTestCase):

    async def test_disappear_sent_to_player(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        sent = [str(c.args) for c in ctx.send.await_args_list]
        self.assertTrue(any('disappears' in s for s in sent))

    async def test_appear_sent_to_player(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        sent = [str(c.args) for c in ctx.send.await_args_list]
        self.assertTrue(any('appears' in s for s in sent))

    async def test_disappear_broadcast_to_origin_room(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        room_calls = [str(c.args) for c in ctx.send_room.await_args_list]
        self.assertTrue(any('disappears' in s for s in room_calls))

    async def test_appear_broadcast_to_dest_room(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        room_calls = [str(c.args) for c in ctx.send_room.await_args_list]
        self.assertTrue(any('appears' in s for s in room_calls))

    async def test_flash_messages_include_player_name(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        ctx.player.name = 'Railbender'
        await cmd.execute(ctx, '37')
        all_sends = [str(c.args) for c in ctx.send.await_args_list]
        self.assertTrue(any('Railbender' in s for s in all_sends))

    async def test_send_room_excludes_self(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        for c in ctx.send_room.await_args_list:
            self.assertTrue(c.kwargs.get('exclude_self'))

    async def test_no_flash_on_permission_denied(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False)
        await cmd.execute(ctx, '37')
        ctx.send_room.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
