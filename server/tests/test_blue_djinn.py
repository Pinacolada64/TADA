"""tests/test_blue_djinn.py

Tests for bar/blue_djinn.py focusing on the broadcast_area additions:
  - approach broadcast when interaction starts
  - leave broadcast on l/q exit
  - ejection broadcast when insulting The Blue Djinn
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


_NPC = "The Blue Djinn"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(*, name='TestPlayer', hp=20, is_expert=True):
    p = MagicMock()
    p.name             = name
    p.hit_points       = hp
    p.previous_command = None
    p.query_flag       = MagicMock(return_value=is_expert)
    p.toggle_flag      = MagicMock()
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


_PATCH_BROADCAST = patch('bar.blue_djinn.broadcast_area', new_callable=AsyncMock)
_PATCH_BOUNCER   = patch('bar.main._bouncer', new=AsyncMock())


# ---------------------------------------------------------------------------
# Approach broadcast
# ---------------------------------------------------------------------------

class TestBlueDjinnApproach(unittest.IsolatedAsyncioTestCase):

    @_PATCH_BROADCAST
    async def test_approach_broadcast_sent(self, mock_ba):
        from bar.blue_djinn import main
        player = make_player(name='Rulan')
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertTrue(any('sits down' in str(c) for c in calls),
                        f'Expected approach broadcast, got: {calls}')

    @_PATCH_BROADCAST
    async def test_approach_broadcast_includes_player_name(self, mock_ba):
        from bar.blue_djinn import main
        player = make_player(name='Railbender')
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        approach = next(c for c in mock_ba.await_args_list if 'sits down' in str(c.args))
        self.assertIn('Railbender', approach.args[2])

    @_PATCH_BROADCAST
    async def test_approach_broadcast_targets_bar_area(self, mock_ba):
        from bar.blue_djinn import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        approach = next(c for c in mock_ba.await_args_list if 'sits down' in str(c.args))
        self.assertEqual(approach.args[1], 'bar')

    @_PATCH_BROADCAST
    async def test_approach_broadcast_mentions_npc(self, mock_ba):
        from bar.blue_djinn import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        approach = next(c for c in mock_ba.await_args_list if 'sits down' in str(c.args))
        self.assertIn(_NPC, approach.args[2])


# ---------------------------------------------------------------------------
# Normal leave (l / q)
# ---------------------------------------------------------------------------

class TestBlueDjinnLeave(unittest.IsolatedAsyncioTestCase):

    @_PATCH_BROADCAST
    async def test_l_triggers_leave_broadcast(self, mock_ba):
        from bar.blue_djinn import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertTrue(any('gets up' in str(c) for c in calls),
                        f'Expected leave broadcast, got: {calls}')

    @_PATCH_BROADCAST
    async def test_q_triggers_leave_broadcast(self, mock_ba):
        from bar.blue_djinn import main
        player = make_player()
        ctx    = make_ctx(player, ['q'])
        await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertTrue(any('gets up' in str(c) for c in calls))

    @_PATCH_BROADCAST
    async def test_leave_broadcast_includes_player_name(self, mock_ba):
        from bar.blue_djinn import main
        player = make_player(name='Rulan')
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        leave = next(c for c in mock_ba.await_args_list if 'gets up' in str(c.args))
        self.assertIn('Rulan', leave.args[2])

    @_PATCH_BROADCAST
    async def test_leave_broadcast_targets_bar_area(self, mock_ba):
        from bar.blue_djinn import main
        player = make_player()
        ctx    = make_ctx(player, ['l'])
        await main(ctx)
        leave = next(c for c in mock_ba.await_args_list if 'gets up' in str(c.args))
        self.assertEqual(leave.args[1], 'bar')

    @_PATCH_BROADCAST
    async def test_eof_no_leave_broadcast(self, mock_ba):
        """EOF/disconnect should not produce a leave broadcast."""
        from bar.blue_djinn import main
        player = make_player()
        ctx    = make_ctx(player, [None])
        await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertFalse(any('gets up' in str(c) for c in calls))


# ---------------------------------------------------------------------------
# Ejection by Mundo (insult)
# ---------------------------------------------------------------------------

class TestBlueDjinnEjection(unittest.IsolatedAsyncioTestCase):

    @_PATCH_BROADCAST
    @_PATCH_BOUNCER
    async def test_insult_triggers_ejection_broadcast(self, *_):
        from bar.blue_djinn import main
        with patch('bar.blue_djinn.broadcast_area', new_callable=AsyncMock) as mock_ba:
            player = make_player(hp=20)
            ctx    = make_ctx(player, ['i'])
            await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertTrue(any('Mundo' in str(c) and 'throws' in str(c) for c in calls),
                        f'Expected ejection broadcast, got: {calls}')

    @_PATCH_BROADCAST
    @_PATCH_BOUNCER
    async def test_ejection_broadcast_includes_player_name(self, *_):
        from bar.blue_djinn import main
        with patch('bar.blue_djinn.broadcast_area', new_callable=AsyncMock) as mock_ba:
            player = make_player(name='Rulan', hp=20)
            ctx    = make_ctx(player, ['i'])
            await main(ctx)
        ejection = next(c for c in mock_ba.await_args_list
                        if 'throws' in str(c.args))
        self.assertIn('Rulan', ejection.args[2])

    @_PATCH_BROADCAST
    @_PATCH_BOUNCER
    async def test_ejection_broadcast_targets_bar_area(self, *_):
        from bar.blue_djinn import main
        with patch('bar.blue_djinn.broadcast_area', new_callable=AsyncMock) as mock_ba:
            player = make_player(hp=20)
            ctx    = make_ctx(player, ['i'])
            await main(ctx)
        ejection = next(c for c in mock_ba.await_args_list
                        if 'throws' in str(c.args))
        self.assertEqual(ejection.args[1], 'bar')

    @_PATCH_BROADCAST
    @_PATCH_BOUNCER
    async def test_no_ejection_broadcast_on_normal_leave(self, *_):
        from bar.blue_djinn import main
        with patch('bar.blue_djinn.broadcast_area', new_callable=AsyncMock) as mock_ba:
            player = make_player()
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        calls = [c.args for c in mock_ba.await_args_list]
        self.assertFalse(any('throws' in str(c) for c in calls))


if __name__ == '__main__':
    unittest.main()
