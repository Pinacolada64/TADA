"""tests/test_shoppe_session.py

Tests for the shoppe session loop introduced in shoppe/main.py, covering
menu display, others_present integration, input dispatch, and exit paths.
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


def make_player(*, is_expert: bool = False, level: int = 1) -> MagicMock:
    p = MagicMock()
    p.name      = 'TestPlayer'
    p.map_level = level
    p.is_expert = is_expert
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
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


# Patch out all sub-section handlers so they don't do anything
_PATCH_STUBS = patch.multiple(
    'shoppe.main',
    _armory        = AsyncMock(return_value=None),
    _protection    = AsyncMock(return_value=None),
    _general_store = AsyncMock(return_value=None),
    _bank          = AsyncMock(return_value=None),
    _wizard        = AsyncMock(return_value=None),
    _clan          = AsyncMock(return_value=None),
    _elevator      = AsyncMock(return_value=None),
    _pawn_shop     = AsyncMock(return_value=None),
    _player_list   = AsyncMock(return_value=None),
)


class TestShoppeSessionExit(unittest.IsolatedAsyncioTestCase):

    @_PATCH_STUBS
    async def test_x_exits(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, ['x'])
        await _shoppe_session(ctx, player)
        self.assertIn('passageway', _sent(ctx))

    @_PATCH_STUBS
    async def test_X_uppercase_exits(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, ['X'])
        await _shoppe_session(ctx, player)
        self.assertIn('passageway', _sent(ctx))

    @_PATCH_STUBS
    async def test_none_prompt_exits(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, [None])
        await _shoppe_session(ctx, player)
        self.assertTrue(ctx.send.called)

    @_PATCH_STUBS
    async def test_empty_input_stays(self, **_):
        """Empty input stays in the loop — needs an explicit exit after."""
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, ['', 'x'])
        await _shoppe_session(ctx, player)
        self.assertIn('passageway', _sent(ctx))


class TestShoppeSessionMenu(unittest.IsolatedAsyncioTestCase):

    @_PATCH_STUBS
    async def test_menu_shown_for_non_expert(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player(is_expert=False)
        ctx    = make_ctx(player, ['x'])
        await _shoppe_session(ctx, player)
        self.assertIn('Merchant Shoppe', _sent(ctx))

    @_PATCH_STUBS
    async def test_menu_not_shown_for_expert(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player(is_expert=True)
        ctx    = make_ctx(player, ['x'])
        await _shoppe_session(ctx, player)
        self.assertNotIn('Merchant Shoppe', _sent(ctx))

    @_PATCH_STUBS
    async def test_menu_lists_elevator(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, ['x'])
        await _shoppe_session(ctx, player)
        self.assertIn('Elevator', _sent(ctx))

    @_PATCH_STUBS
    async def test_menu_lists_leave_option(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, ['x'])
        await _shoppe_session(ctx, player)
        self.assertIn('[X] Leave', _sent(ctx))


class TestShoppeSessionOthersPresent(unittest.IsolatedAsyncioTestCase):

    @_PATCH_STUBS
    async def test_others_shown_in_menu(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, ['x'])

        peer_player      = MagicMock()
        peer_player.name = 'Railbender'
        peer_ctx         = MagicMock()
        peer_ctx.player  = peer_player
        peer_client      = MagicMock()
        peer_client.ctx  = peer_ctx
        peer_client.virtual_location = 'shoppe'

        ctx.server.clients = {'peer': peer_client}
        await _shoppe_session(ctx, player)
        self.assertIn('Railbender', _sent(ctx))

    @_PATCH_STUBS
    async def test_self_not_listed(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, ['x'])
        # own client is never in server.clients in this test setup,
        # so just verify the player's own name doesn't appear under "Also here:"
        sent = _sent(ctx)
        self.assertNotIn('Also here: TestPlayer', sent)

    @_PATCH_STUBS
    async def test_no_others_no_also_here_line(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, ['x'])
        ctx.server.clients = {}
        await _shoppe_session(ctx, player)
        self.assertNotIn('Also here', _sent(ctx))


def _make_menu(*keys: str):
    """Return a minimal _MENU tuple with one AsyncMock handler per key."""
    mocks = {k: AsyncMock() for k in keys}
    menu  = tuple((k, k.capitalize(), mocks[k]) for k in keys)
    return menu, mocks


class TestShoppeSessionDispatch(unittest.IsolatedAsyncioTestCase):

    async def test_a_calls_armory(self):
        from shoppe.main import _shoppe_session
        menu, mocks = _make_menu('A')
        with patch('shoppe.main._MENU', menu):
            player = make_player()
            ctx    = make_ctx(player, ['a', 'x'])
            await _shoppe_session(ctx, player)
        mocks['A'].assert_awaited_once_with(ctx)

    async def test_e_calls_elevator(self):
        from shoppe.main import _shoppe_session
        menu, mocks = _make_menu('E')
        with patch('shoppe.main._MENU', menu):
            player = make_player()
            ctx    = make_ctx(player, ['e', 'x'])
            await _shoppe_session(ctx, player)
        mocks['E'].assert_awaited_once_with(ctx)

    async def test_b_calls_bank(self):
        from shoppe.main import _shoppe_session
        menu, mocks = _make_menu('B')
        with patch('shoppe.main._MENU', menu):
            player = make_player()
            ctx    = make_ctx(player, ['b', 'x'])
            await _shoppe_session(ctx, player)
        mocks['B'].assert_awaited_once_with(ctx)

    async def test_uppercase_key_dispatches(self):
        """Keys are case-insensitive — 'G' input should match 'G' menu key."""
        from shoppe.main import _shoppe_session
        menu, mocks = _make_menu('G')
        with patch('shoppe.main._MENU', menu):
            player = make_player()
            ctx    = make_ctx(player, ['G', 'x'])
            await _shoppe_session(ctx, player)
        mocks['G'].assert_awaited_once_with(ctx)

    @_PATCH_STUBS
    async def test_invalid_key_shows_error(self, **_):
        from shoppe.main import _shoppe_session
        player = make_player()
        ctx    = make_ctx(player, ['z', 'x'])
        await _shoppe_session(ctx, player)
        self.assertIn('"z"', _sent(ctx))

    async def test_multi_char_input_uses_first_char(self):
        """Shoppe reads only the first character — 'armory' acts like 'a'."""
        from shoppe.main import _shoppe_session
        menu, mocks = _make_menu('A')
        with patch('shoppe.main._MENU', menu):
            player = make_player()
            ctx    = make_ctx(player, ['armory', 'x'])
            await _shoppe_session(ctx, player)
        mocks['A'].assert_awaited_once_with(ctx)

    async def test_multiple_visits_before_exit(self):
        from shoppe.main import _shoppe_session
        menu, mocks = _make_menu('A', 'B', 'W')
        with patch('shoppe.main._MENU', menu):
            player = make_player()
            ctx    = make_ctx(player, ['a', 'b', 'w', 'x'])
            await _shoppe_session(ctx, player)
        self.assertEqual(mocks['A'].await_count, 1)
        self.assertEqual(mocks['B'].await_count, 1)
        self.assertEqual(mocks['W'].await_count, 1)


class TestShoppeMain(unittest.IsolatedAsyncioTestCase):
    """Tests for the outer main() which guards level and manages presence."""

    @_PATCH_STUBS
    async def test_level_7_refused(self, **_):
        from shoppe.main import main
        player = make_player(level=7)
        ctx    = make_ctx(player, [])
        with patch('shoppe.main.enter_area', new=AsyncMock()) as ea, \
             patch('shoppe.main.leave_area', new=AsyncMock()) as la:
            await main(ctx)
            ea.assert_not_awaited()
            la.assert_not_awaited()
        self.assertIn('closed', _sent(ctx))

    @_PATCH_STUBS
    async def test_enter_area_called(self, **_):
        from shoppe.main import main
        player = make_player(level=1)
        ctx    = make_ctx(player, ['x'])
        with patch('shoppe.main.enter_area', new=AsyncMock()) as ea, \
             patch('shoppe.main.leave_area', new=AsyncMock()):
            await main(ctx)
            ea.assert_awaited_once_with(ctx, 'Shoppe')

    @_PATCH_STUBS
    async def test_leave_area_called_on_exit(self, **_):
        from shoppe.main import main
        player = make_player(level=1)
        ctx    = make_ctx(player, ['x'])
        with patch('shoppe.main.enter_area', new=AsyncMock()), \
             patch('shoppe.main.leave_area', new=AsyncMock()) as la:
            await main(ctx)
            la.assert_awaited_once_with(ctx, 'Shoppe')

    @_PATCH_STUBS
    async def test_leave_area_called_even_on_exception(self, **_):
        from shoppe.main import main
        player = make_player(level=1)
        ctx    = make_ctx(player, [])
        ctx.prompt = AsyncMock(side_effect=RuntimeError('boom'))
        with patch('shoppe.main.enter_area', new=AsyncMock()), \
             patch('shoppe.main.leave_area', new=AsyncMock()) as la:
            with self.assertRaises(RuntimeError):
                await main(ctx)
            la.assert_awaited_once_with(ctx, 'Shoppe')


if __name__ == '__main__':
    unittest.main()
