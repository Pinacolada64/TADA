"""tests/test_vinny.py

Tests for broadcast_area additions in bar/main.py _vinny().
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


def make_ctx(name='TestPlayer') -> MagicMock:
    ctx               = MagicMock()
    ctx.player.name   = name
    ctx.send          = AsyncMock()
    ctx.send_room     = AsyncMock()
    ctx.server.clients = {}
    return ctx


_PATCH_BROADCAST = patch('bar.main.broadcast_area', new_callable=AsyncMock)


class TestVinnyBroadcasts(unittest.IsolatedAsyncioTestCase):

    @_PATCH_BROADCAST
    async def test_approach_broadcast_sent(self, mock_ba):
        from bar.main import _vinny
        ctx = make_ctx()
        await _vinny(ctx, bar=None)
        approach = [c for c in mock_ba.await_args_list if 'walks up' in str(c.args)]
        self.assertTrue(approach, f'No approach broadcast; calls: {mock_ba.await_args_list}')

    @_PATCH_BROADCAST
    async def test_approach_broadcast_includes_player_name(self, mock_ba):
        from bar.main import _vinny
        ctx = make_ctx(name='Railbender')
        await _vinny(ctx, bar=None)
        approach = next(c for c in mock_ba.await_args_list if 'walks up' in str(c.args))
        self.assertIn('Railbender', approach.args[2])

    @_PATCH_BROADCAST
    async def test_approach_broadcast_targets_bar_area(self, mock_ba):
        from bar.main import _vinny
        ctx = make_ctx()
        await _vinny(ctx, bar=None)
        approach = next(c for c in mock_ba.await_args_list if 'walks up' in str(c.args))
        self.assertEqual(approach.args[1], 'bar')

    @_PATCH_BROADCAST
    async def test_leave_broadcast_sent(self, mock_ba):
        from bar.main import _vinny
        ctx = make_ctx()
        await _vinny(ctx, bar=None)
        leave = [c for c in mock_ba.await_args_list if 'backs away' in str(c.args)]
        self.assertTrue(leave, f'No leave broadcast; calls: {mock_ba.await_args_list}')

    @_PATCH_BROADCAST
    async def test_leave_broadcast_includes_player_name(self, mock_ba):
        from bar.main import _vinny
        ctx = make_ctx(name='Rulan')
        await _vinny(ctx, bar=None)
        leave = next(c for c in mock_ba.await_args_list if 'backs away' in str(c.args))
        self.assertIn('Rulan', leave.args[2])

    @_PATCH_BROADCAST
    async def test_both_broadcasts_fired(self, mock_ba):
        from bar.main import _vinny
        ctx = make_ctx()
        await _vinny(ctx, bar=None)
        self.assertEqual(mock_ba.await_count, 2)


if __name__ == '__main__':
    unittest.main()
