"""tests/test_bar_session.py

Tests for bar/main.py focusing on the presence and broadcast additions:
  - enter_area / leave_area lifecycle
  - send_room on entry and exit
  - broadcast_area on movement and obstacle death
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(*, name='TestPlayer', hp=20, is_expert=True, is_debug=False):
    p = MagicMock()
    p.name          = name
    p.hit_points    = hp       # real int so -= 1 arithmetic works
    p.is_expert     = is_expert
    p.is_debug      = is_debug
    p.previous_command = None
    p.client_settings.return_key  = 'Return'
    p.client_settings.translation = None
    p.query_flag  = MagicMock(return_value=False)
    p.toggle_flag = MagicMock()
    p.loan_amount = 0   # real int so enter_bar()'s Mundo/Vinny check works
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


def _sent(ctx) -> str:
    parts = []
    for c in ctx.send.await_args_list:
        for arg in c.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


# Patch helpers that produce output we don't care about in most tests
_PATCH_HELP   = patch('bar.main._bar_help',   new=AsyncMock())
_PATCH_MENU   = patch('bar.main._show_menu',  new=AsyncMock())
_PATCH_RENDER = patch('bar.main._render_map', return_value=['[map]'])


# ---------------------------------------------------------------------------
# Presence lifecycle
# ---------------------------------------------------------------------------

class TestBarPresenceLifecycle(unittest.IsolatedAsyncioTestCase):

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_enter_area_called(self, *_):
        from bar.main import enter_bar
        player = make_player()
        ctx    = make_ctx(player, ['q'])
        with patch('bar.main.enter_area', new=AsyncMock()) as ea, \
             patch('bar.main.leave_area', new=AsyncMock()):
            await enter_bar(ctx)
            ea.assert_awaited_once_with(ctx, 'Bar')

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_leave_area_called_on_quit(self, *_):
        from bar.main import enter_bar
        player = make_player()
        ctx    = make_ctx(player, ['q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()) as la:
            await enter_bar(ctx)
            la.assert_awaited_once_with(ctx, 'Bar')

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_leave_area_called_on_eof(self, *_):
        from bar.main import enter_bar
        player = make_player()
        ctx    = make_ctx(player, [None])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()) as la:
            await enter_bar(ctx)
            la.assert_awaited_once_with(ctx, 'Bar')

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_leave_area_called_even_on_exception(self, *_):
        from bar.main import enter_bar
        player = make_player()
        ctx    = make_ctx(player, [])
        ctx.prompt = AsyncMock(side_effect=RuntimeError('boom'))
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()) as la:
            with self.assertRaises(RuntimeError):
                await enter_bar(ctx)
            la.assert_awaited_once_with(ctx, 'Bar')


# ---------------------------------------------------------------------------
# Outstanding loan: Mundo escorts the player straight to Vinny
# (SPUR.BAR.S:16-18 -- "Mundo checks your books.." / "if (g7>0) or (g8>0)
# ... 'He escorts you over to Vinney!' ... goto mundo.ck")
# ---------------------------------------------------------------------------

class TestMundoEscortsToVinny(unittest.IsolatedAsyncioTestCase):

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_no_loan_skips_escort(self, *_):
        from bar.main import enter_bar
        player = make_player()
        player.loan_amount = 0
        ctx = make_ctx(player, ['q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main._vinny', new=AsyncMock()) as vinny:
            await enter_bar(ctx)
            vinny.assert_not_awaited()
        self.assertNotIn('Mundo checks your books..', _sent(ctx))

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_outstanding_loan_triggers_escort(self, *_):
        from bar.main import enter_bar
        player = make_player()
        player.loan_amount = 2500
        ctx = make_ctx(player, [])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main._vinny', new=AsyncMock()) as vinny:
            await enter_bar(ctx)
            vinny.assert_awaited_once()

        sent = _sent(ctx)
        self.assertIn('Mundo checks your books..', sent)
        self.assertIn("He 'escorts' you over to Vinney!", sent)

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_escort_places_player_on_vinnys_tile(self, *_):
        from bar.main import enter_bar, Bar
        player = make_player()
        player.loan_amount = 2500
        ctx = make_ctx(player, [])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main._vinny', new=AsyncMock()) as vinny:
            await enter_bar(ctx)

        vinny_loc = next(loc for loc in Bar.locations if loc[2] == 'Vinny the Loan Shark')
        (_, bar_arg), _kwargs = vinny.await_args
        self.assertEqual((bar_arg.pos_y, bar_arg.pos_x), (vinny_loc[0], vinny_loc[1]))

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_escort_skips_help_and_normal_loop(self, *_):
        from bar.main import enter_bar
        player = make_player()
        player.loan_amount = 2500
        ctx = make_ctx(player, [])   # no prompt answers queued -- loop must never run
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main._bar_help', new=AsyncMock()) as help_mock, \
             patch('bar.main._vinny', new=AsyncMock()):
            await enter_bar(ctx)
            help_mock.assert_not_awaited()
        ctx.prompt.assert_not_awaited()

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_leave_area_still_called_after_escort(self, *_):
        from bar.main import enter_bar
        player = make_player()
        player.loan_amount = 2500
        ctx = make_ctx(player, [])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()) as la, \
             patch('bar.main._vinny', new=AsyncMock()):
            await enter_bar(ctx)
            la.assert_awaited_once_with(ctx, 'Bar')

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_escort_repeats_every_entry_while_loan_outstanding(self, *_):
        from bar.main import enter_bar
        player = make_player()
        player.loan_amount = 2500
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main._vinny', new=AsyncMock()) as vinny:
            await enter_bar(make_ctx(player, []))
            await enter_bar(make_ctx(player, []))
            self.assertEqual(vinny.await_count, 2)


# ---------------------------------------------------------------------------
# Entry / exit send_room broadcasts
# ---------------------------------------------------------------------------

class TestBarRoomBroadcasts(unittest.IsolatedAsyncioTestCase):

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_send_room_on_entry(self, *_):
        from bar.main import enter_bar
        player = make_player(name='Railbender')
        ctx    = make_ctx(player, ['q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()):
            await enter_bar(ctx)
        # First send_room call should be the entry message
        first_call_arg = ctx.send_room.await_args_list[0].args[0]
        self.assertIn('Railbender', first_call_arg)
        self.assertIn('Wall Bar', first_call_arg)

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_send_room_entry_excludes_self(self, *_):
        from bar.main import enter_bar
        player = make_player()
        ctx    = make_ctx(player, ['q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()):
            await enter_bar(ctx)
        first_kwargs = ctx.send_room.await_args_list[0].kwargs
        self.assertTrue(first_kwargs.get('exclude_self'))

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_send_room_on_quit(self, *_):
        from bar.main import enter_bar
        player = make_player(name='Railbender')
        ctx    = make_ctx(player, ['q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()):
            await enter_bar(ctx)
        # Second send_room call is the exit message
        exit_call_arg = ctx.send_room.await_args_list[1].args[0]
        self.assertIn('Railbender', exit_call_arg)
        self.assertIn('street', exit_call_arg)

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_send_to_player_on_quit(self, *_):
        from bar.main import enter_bar
        player = make_player()
        ctx    = make_ctx(player, ['q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()):
            await enter_bar(ctx)
        self.assertIn('street', _sent(ctx))

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_no_exit_send_room_on_eof(self, *_):
        """EOF/disconnect should not produce an exit send_room — only the entry one."""
        from bar.main import enter_bar
        player = make_player()
        ctx    = make_ctx(player, [None])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()):
            await enter_bar(ctx)
        self.assertEqual(ctx.send_room.await_count, 1)


# ---------------------------------------------------------------------------
# Movement broadcast_area
# ---------------------------------------------------------------------------

class TestBarMovementBroadcast(unittest.IsolatedAsyncioTestCase):

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_south_move_broadcasts(self, *_):
        """Moving south from start (6,0) → (6,1) is a valid move."""
        from bar.main import enter_bar
        player = make_player()
        ctx    = make_ctx(player, ['s', 'q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main.broadcast_area', new=AsyncMock()) as ba:
            await enter_bar(ctx)
        calls = [c.args for c in ba.await_args_list]
        self.assertTrue(any('south' in str(c) for c in calls),
                        f'Expected south broadcast, got: {calls}')

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_move_broadcast_includes_player_name(self, *_):
        from bar.main import enter_bar
        player = make_player(name='Rulan')
        ctx    = make_ctx(player, ['s', 'q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main.broadcast_area', new=AsyncMock()) as ba:
            await enter_bar(ctx)
        move_calls = [c for c in ba.await_args_list
                      if c.args[1] == 'bar' and 'moves' in str(c.args[2])]
        self.assertTrue(move_calls)
        self.assertIn('Rulan', move_calls[0].args[2])

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_obstacle_move_does_not_broadcast_movement(self, *_):
        """Walking into a wall should not broadcast a movement message."""
        from bar.main import enter_bar
        player = make_player(hp=20)
        # 'n' from (6,0) hits boundary — obstacle, not a valid move
        ctx    = make_ctx(player, ['n', 'q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main.broadcast_area', new=AsyncMock()) as ba:
            await enter_bar(ctx)
        move_broadcasts = [c for c in ba.await_args_list
                           if 'moves' in str(c.args)]
        self.assertEqual(move_broadcasts, [])

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_multiple_moves_each_broadcast(self, *_):
        """Each successful move step gets its own broadcast."""
        from bar.main import enter_bar
        player = make_player()
        # s, s from (6,0)→(6,1)→(6,2); both valid spaces
        ctx    = make_ctx(player, ['s', 's', 'q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main.broadcast_area', new=AsyncMock()) as ba:
            await enter_bar(ctx)
        move_broadcasts = [c for c in ba.await_args_list
                           if 'moves' in str(c.args)]
        self.assertEqual(len(move_broadcasts), 2)


# ---------------------------------------------------------------------------
# Death by obstacle
# ---------------------------------------------------------------------------

class TestBarObstacleDeath(unittest.IsolatedAsyncioTestCase):

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_death_broadcasts_to_bar(self, *_):
        from bar.main import enter_bar
        player = make_player(hp=1)
        # 'w' from (6,0) hits the wall at bar_map[0][5] ('|').
        # (0,6) itself is the "Exit" tile, so 'n' from there now leaves instead of
        # bumping into an obstacle -- see Bar.locations / the fix in bar/main.py
        ctx    = make_ctx(player, ['w'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main.broadcast_area', new=AsyncMock()) as ba:
            await enter_bar(ctx)
        death_calls = [c for c in ba.await_args_list
                       if 'died' in str(c.args)]
        self.assertTrue(death_calls, 'Expected a death broadcast')

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_death_broadcast_includes_player_name(self, *_):
        from bar.main import enter_bar
        player = make_player(name='Rulan', hp=1)
        ctx    = make_ctx(player, ['w'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main.broadcast_area', new=AsyncMock()) as ba:
            await enter_bar(ctx)
        death_calls = [c for c in ba.await_args_list
                       if 'died' in str(c.args)]
        self.assertIn('Rulan', death_calls[0].args[2])

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_death_sends_died_message_to_player(self, *_):
        from bar.main import enter_bar
        player = make_player(hp=1)
        ctx    = make_ctx(player, ['w'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main.broadcast_area', new=AsyncMock()):
            await enter_bar(ctx)
        self.assertIn('died', _sent(ctx).lower())

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_leave_area_called_after_death(self, *_):
        from bar.main import enter_bar
        player = make_player(hp=1)
        ctx    = make_ctx(player, ['n'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()) as la, \
             patch('bar.main.broadcast_area', new=AsyncMock()):
            await enter_bar(ctx)
        la.assert_awaited_once_with(ctx, 'Bar')

    @_PATCH_HELP
    @_PATCH_MENU
    @_PATCH_RENDER
    async def test_obstacle_without_death_no_death_broadcast(self, *_):
        """Bumping a wall with HP > 1 should NOT produce a death broadcast."""
        from bar.main import enter_bar
        player = make_player(hp=20)
        ctx    = make_ctx(player, ['n', 'q'])
        with patch('bar.main.enter_area', new=AsyncMock()), \
             patch('bar.main.leave_area', new=AsyncMock()), \
             patch('bar.main.broadcast_area', new=AsyncMock()) as ba:
            await enter_bar(ctx)
        death_calls = [c for c in ba.await_args_list if 'died' in str(c.args)]
        self.assertEqual(death_calls, [])


if __name__ == '__main__':
    unittest.main()
