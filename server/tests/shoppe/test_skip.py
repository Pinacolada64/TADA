"""tests/test_skip.py

Tests for bar/skip.py broadcast_area additions:
  - approach broadcast after the once-per-day gate
  - leave broadcast on l/q exit
  - no approach broadcast when turned away (already visited today)
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from flags import PlayerFlags


_NPC = "Skip"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(*, name='TestPlayer', hp=20, once_per_day=None,
                expert=False, debug=False):
    p = MagicMock()
    p.name           = name
    p.hit_points     = hp
    p.once_per_day   = once_per_day if once_per_day is not None else []
    p.party          = []
    p.subtract_silver = MagicMock(return_value=True)

    def query_flag(flag):
        if flag == PlayerFlags.EXPERT_MODE:
            return expert
        if flag == PlayerFlags.DEBUG_MODE:
            return debug
        return False

    p.query_flag = query_flag
    return p


def make_ctx(player, prompts: list) -> MagicMock:
    ctx               = MagicMock()
    ctx.player        = player
    ctx.send          = AsyncMock()
    ctx.send_room     = AsyncMock()
    ctx.server.clients = {}
    it = iter(prompts)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    return ctx


_PATCH_BROADCAST = patch('bar.skip.broadcast_area', new_callable=AsyncMock)


# ---------------------------------------------------------------------------
# Approach broadcast
# ---------------------------------------------------------------------------

class TestSkipApproach(unittest.IsolatedAsyncioTestCase):

    @_PATCH_BROADCAST
    async def test_approach_broadcast_sent(self, mock_ba):
        from bar.skip import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertTrue(any('sits down' in str(c) for c in calls),
                        f'Expected approach broadcast, got: {calls}')

    @_PATCH_BROADCAST
    async def test_approach_broadcast_includes_player_name(self, mock_ba):
        from bar.skip import main
        player = make_player(name='Railbender')
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        approach = next(c for c in mock_ba.await_args_list
                        if 'sits down' in str(c.args))
        self.assertIn('Railbender', approach.args[2])

    @_PATCH_BROADCAST
    async def test_approach_broadcast_targets_bar_area(self, mock_ba):
        from bar.skip import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        approach = next(c for c in mock_ba.await_args_list
                        if 'sits down' in str(c.args))
        self.assertEqual(approach.args[1], 'bar')

    @_PATCH_BROADCAST
    async def test_approach_broadcast_mentions_npc(self, mock_ba):
        from bar.skip import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        approach = next(c for c in mock_ba.await_args_list
                        if 'sits down' in str(c.args))
        self.assertIn(_NPC, approach.args[2])

    @_PATCH_BROADCAST
    async def test_no_approach_broadcast_when_turned_away(self, mock_ba):
        """Player already visited today — turned away before sitting down."""
        from bar.skip import main
        player = make_player(once_per_day=[_NPC])
        ctx    = make_ctx(player, [])
        await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertFalse(any('sits down' in str(c) for c in calls),
                         f'Should not broadcast approach for turned-away player, got: {calls}')


# ---------------------------------------------------------------------------
# Leave broadcast
# ---------------------------------------------------------------------------

class TestSkipLeave(unittest.IsolatedAsyncioTestCase):

    @_PATCH_BROADCAST
    async def test_l_triggers_leave_broadcast(self, mock_ba):
        from bar.skip import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertTrue(any('gets up' in str(c) for c in calls),
                        f'Expected leave broadcast, got: {calls}')

    @_PATCH_BROADCAST
    async def test_q_triggers_leave_broadcast(self, mock_ba):
        from bar.skip import main
        player = make_player()
        ctx    = make_ctx(player, ['q'])
        await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertTrue(any('gets up' in str(c) for c in calls))

    @_PATCH_BROADCAST
    async def test_leave_broadcast_includes_player_name(self, mock_ba):
        from bar.skip import main
        player = make_player(name='Rulan')
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        leave = next(c for c in mock_ba.await_args_list
                     if 'gets up' in str(c.args))
        self.assertIn('Rulan', leave.args[2])

    @_PATCH_BROADCAST
    async def test_leave_broadcast_targets_bar_area(self, mock_ba):
        from bar.skip import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        leave = next(c for c in mock_ba.await_args_list
                     if 'gets up' in str(c.args))
        self.assertEqual(leave.args[1], 'bar')

    @_PATCH_BROADCAST
    async def test_eof_no_leave_broadcast(self, mock_ba):
        """EOF/disconnect should not produce a leave broadcast."""
        from bar.skip import main
        player = make_player()
        ctx    = make_ctx(player, [None])
        await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertFalse(any('gets up' in str(c) for c in calls))

    @_PATCH_BROADCAST
    async def test_approach_and_leave_both_sent(self, mock_ba):
        from bar.skip import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        has_approach = any('sits down' in str(c.args) for c in mock_ba.await_args_list)
        has_leave    = any('gets up'   in str(c.args) for c in mock_ba.await_args_list)
        self.assertTrue(has_approach and has_leave)


if __name__ == '__main__':
    unittest.main()
