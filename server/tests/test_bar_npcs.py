"""tests/test_bar_npcs.py

Tests for broadcast_area additions in bar_none.py, fat_olaf.py, and zelda.py.
Each NPC gets approach and leave broadcast coverage.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from flags import PlayerFlags


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def make_player(*, name='TestPlayer', expert=False):
    p = MagicMock()
    p.name             = name
    p.hit_points       = 20
    p.previous_command = None
    p.client_settings  = MagicMock(return_key='Return')
    p.query_flag       = MagicMock(return_value=expert)
    p.toggle_flag      = MagicMock()
    p.subtract_silver  = MagicMock(return_value=True)
    p.once_per_day     = []
    p.party            = []
    return p


def make_ctx(player, prompts: list) -> MagicMock:
    ctx                = MagicMock()
    ctx.player         = player
    ctx.send           = AsyncMock()
    ctx.send_room      = AsyncMock()
    ctx.server.clients = {}
    it = iter(prompts)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    return ctx


def _approach_calls(mock_ba):
    return [c for c in mock_ba.await_args_list if 'sits down' in str(c.args)
            or 'pulls up' in str(c.args)
            or 'bellies up' in str(c.args)]


def _leave_calls(mock_ba):
    return [c for c in mock_ba.await_args_list if 'gets up' in str(c.args)
            or 'tips a hat' in str(c.args)]


# ---------------------------------------------------------------------------
# Bar None (Mae the Bartender)
# ---------------------------------------------------------------------------

class TestBarNoneBroadcasts(unittest.IsolatedAsyncioTestCase):

    def _patch(self):
        return patch('bar.bar_none.broadcast_area', new_callable=AsyncMock)

    async def test_approach_broadcast_sent(self):
        with self._patch() as mock_ba, \
             patch('bar.bar_none.Rations.read_rations', return_value=[]), \
             patch('bar.bar_none.food_menu', return_value=[]):
            from bar.bar_none import main
            player = make_player(name='Rulan', expert=True)
            ctx    = make_ctx(player, [''])
            await main(ctx)
        self.assertTrue(_approach_calls(mock_ba),
                        f'No approach broadcast; calls: {mock_ba.await_args_list}')

    async def test_approach_broadcast_includes_player_name(self):
        with self._patch() as mock_ba, \
             patch('bar.bar_none.Rations.read_rations', return_value=[]), \
             patch('bar.bar_none.food_menu', return_value=[]):
            from bar.bar_none import main
            player = make_player(name='Railbender', expert=True)
            ctx    = make_ctx(player, [''])
            await main(ctx)
        self.assertIn('Railbender', _approach_calls(mock_ba)[0].args[2])

    async def test_approach_broadcast_targets_bar_area(self):
        with self._patch() as mock_ba, \
             patch('bar.bar_none.Rations.read_rations', return_value=[]), \
             patch('bar.bar_none.food_menu', return_value=[]):
            from bar.bar_none import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, [''])
            await main(ctx)
        self.assertEqual(_approach_calls(mock_ba)[0].args[1], 'bar')

    async def test_leave_broadcast_on_empty_input(self):
        with self._patch() as mock_ba, \
             patch('bar.bar_none.Rations.read_rations', return_value=[]), \
             patch('bar.bar_none.food_menu', return_value=[]):
            from bar.bar_none import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, [''])
            await main(ctx)
        self.assertTrue(_leave_calls(mock_ba),
                        f'No leave broadcast; calls: {mock_ba.await_args_list}')

    async def test_leave_broadcast_includes_player_name(self):
        with self._patch() as mock_ba, \
             patch('bar.bar_none.Rations.read_rations', return_value=[]), \
             patch('bar.bar_none.food_menu', return_value=[]):
            from bar.bar_none import main
            player = make_player(name='Rulan', expert=True)
            ctx    = make_ctx(player, [''])
            await main(ctx)
        self.assertIn('Rulan', _leave_calls(mock_ba)[0].args[2])

    async def test_no_leave_broadcast_on_eof(self):
        with self._patch() as mock_ba, \
             patch('bar.bar_none.Rations.read_rations', return_value=[]), \
             patch('bar.bar_none.food_menu', return_value=[]):
            from bar.bar_none import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, [None])
            await main(ctx)
        self.assertFalse(_leave_calls(mock_ba))


# ---------------------------------------------------------------------------
# Fat Olaf
# ---------------------------------------------------------------------------

class TestFatOlafBroadcasts(unittest.IsolatedAsyncioTestCase):

    def _patch(self):
        return patch('bar.fat_olaf.broadcast_area', new_callable=AsyncMock)

    async def test_approach_broadcast_sent(self):
        with self._patch() as mock_ba, \
             patch('bar.fat_olaf.load_allies', return_value=[]):
            from bar.fat_olaf import main
            player = make_player(name='Rulan', expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertTrue(_approach_calls(mock_ba),
                        f'No approach broadcast; calls: {mock_ba.await_args_list}')

    async def test_approach_broadcast_includes_player_name(self):
        with self._patch() as mock_ba, \
             patch('bar.fat_olaf.load_allies', return_value=[]):
            from bar.fat_olaf import main
            player = make_player(name='Railbender', expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertIn('Railbender', _approach_calls(mock_ba)[0].args[2])

    async def test_approach_broadcast_targets_bar_area(self):
        with self._patch() as mock_ba, \
             patch('bar.fat_olaf.load_allies', return_value=[]):
            from bar.fat_olaf import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertEqual(_approach_calls(mock_ba)[0].args[1], 'bar')

    async def test_leave_broadcast_on_l(self):
        with self._patch() as mock_ba, \
             patch('bar.fat_olaf.load_allies', return_value=[]):
            from bar.fat_olaf import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertTrue(_leave_calls(mock_ba))

    async def test_leave_broadcast_on_q(self):
        with self._patch() as mock_ba, \
             patch('bar.fat_olaf.load_allies', return_value=[]):
            from bar.fat_olaf import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, ['q'])
            await main(ctx)
        self.assertTrue(_leave_calls(mock_ba))

    async def test_leave_broadcast_includes_player_name(self):
        with self._patch() as mock_ba, \
             patch('bar.fat_olaf.load_allies', return_value=[]):
            from bar.fat_olaf import main
            player = make_player(name='Rulan', expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertIn('Rulan', _leave_calls(mock_ba)[0].args[2])

    async def test_no_leave_broadcast_on_eof(self):
        with self._patch() as mock_ba, \
             patch('bar.fat_olaf.load_allies', return_value=[]):
            from bar.fat_olaf import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, [None])
            await main(ctx)
        self.assertFalse(_leave_calls(mock_ba))


# ---------------------------------------------------------------------------
# Madame Zelda
# ---------------------------------------------------------------------------

class TestZeldaBroadcasts(unittest.IsolatedAsyncioTestCase):

    def _patch(self):
        return patch('bar.zelda.broadcast_area', new_callable=AsyncMock)

    async def test_approach_broadcast_sent(self):
        with self._patch() as mock_ba:
            from bar.zelda import main
            player = make_player(name='Rulan', expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertTrue(_approach_calls(mock_ba),
                        f'No approach broadcast; calls: {mock_ba.await_args_list}')

    async def test_approach_broadcast_includes_player_name(self):
        with self._patch() as mock_ba:
            from bar.zelda import main
            player = make_player(name='Railbender', expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertIn('Railbender', _approach_calls(mock_ba)[0].args[2])

    async def test_approach_broadcast_targets_bar_area(self):
        with self._patch() as mock_ba:
            from bar.zelda import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertEqual(_approach_calls(mock_ba)[0].args[1], 'bar')

    async def test_leave_broadcast_on_l(self):
        with self._patch() as mock_ba:
            from bar.zelda import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertTrue(_leave_calls(mock_ba))

    async def test_leave_broadcast_on_q(self):
        with self._patch() as mock_ba:
            from bar.zelda import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, ['q'])
            await main(ctx)
        self.assertTrue(_leave_calls(mock_ba))

    async def test_leave_broadcast_includes_player_name(self):
        with self._patch() as mock_ba:
            from bar.zelda import main
            player = make_player(name='Rulan', expert=True)
            ctx    = make_ctx(player, ['l'])
            await main(ctx)
        self.assertIn('Rulan', _leave_calls(mock_ba)[0].args[2])

    async def test_no_leave_broadcast_on_eof(self):
        with self._patch() as mock_ba:
            from bar.zelda import main
            player = make_player(expert=True)
            ctx    = make_ctx(player, [None])
            await main(ctx)
        self.assertFalse(_leave_calls(mock_ba))


if __name__ == '__main__':
    unittest.main()
