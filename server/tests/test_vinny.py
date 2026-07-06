"""tests/test_vinny.py

Tests for broadcast_area additions in bar/main.py _vinny().
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


def make_ctx(name='TestPlayer') -> MagicMock:
    ctx               = MagicMock()
    ctx.player.name   = name
    ctx.player.loan_amount = 0   # real int so vinny.py's loan-greeting math works
    ctx.player.loan_days   = 0
    ctx.send          = AsyncMock()
    ctx.send_room     = AsyncMock()
    ctx.server.clients = {}
    # bar/vinny.py's interaction loop only broadcasts "leaves Vinny's
    # table" on an explicit 'l'/'q' -- a bare disconnect (prompt() -> None)
    # breaks the loop silently with no leave broadcast at all. These tests
    # want the leave broadcast, so simulate typing 'q' immediately.
    ctx.prompt        = AsyncMock(return_value='q')
    return ctx


# bar/vinny.py imports broadcast_area directly ("from presence import
# broadcast_area") and calls it in its own module namespace -- patching
# bar.main.broadcast_area has no effect on those calls, since bar/main.py's
# _vinny() just delegates to bar.vinny.main() without going through
# anything in bar.main's namespace.
_PATCH_BROADCAST = patch('bar.vinny.broadcast_area', new_callable=AsyncMock)


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
        leave = [c for c in mock_ba.await_args_list if 'leaves' in str(c.args)]
        self.assertTrue(leave, f'No leave broadcast; calls: {mock_ba.await_args_list}')

    @_PATCH_BROADCAST
    async def test_leave_broadcast_includes_player_name(self, mock_ba):
        from bar.main import _vinny
        ctx = make_ctx(name='Rulan')
        await _vinny(ctx, bar=None)
        leave = next(c for c in mock_ba.await_args_list if 'leaves' in str(c.args))
        self.assertIn('Rulan', leave.args[2])

    @_PATCH_BROADCAST
    async def test_both_broadcasts_fired(self, mock_ba):
        from bar.main import _vinny
        ctx = make_ctx()
        await _vinny(ctx, bar=None)
        self.assertEqual(mock_ba.await_count, 2)


if __name__ == '__main__':
    unittest.main()
