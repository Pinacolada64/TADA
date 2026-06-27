"""tests/test_teleport.py"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.teleport import TeleportCommand
from flags import PlayerFlags


def make_ctx(*, is_admin=True, room=1, rooms=None):
    if rooms is None:
        rooms = {1: object(), 37: object()}

    player = MagicMock()
    player.name = 'TestPlayer'
    player.query_flag = MagicMock(
        side_effect=lambda f: f == PlayerFlags.ADMIN and is_admin
    )

    server = MagicMock()
    server.game_map.rooms = rooms
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

    async def test_non_admin_denied(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False)
        res = await cmd.execute(ctx, '37')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'permission_denied')

    async def test_non_admin_no_room_change(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False, room=1)
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


class TestTeleportArgs(unittest.IsolatedAsyncioTestCase):

    async def test_no_args_fails(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'missing_args')

    async def test_bad_room_number_fails(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx, 'abc')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'bad_args')

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
