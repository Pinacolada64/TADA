"""tests/test_thug_attack.py

Unit tests for bar/thug_attack.py -- resolves a pending Blue Djinn hit
contract (PlayerFlags.THUG_ATTACK, set by bar/blue_djinn.py's HIRE flow)
at login.

Run with:
    python -m pytest tests/test_thug_attack.py -v
"""
from __future__ import annotations

import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import net_common
from flags import PlayerFlags


class _RunDirMixin:
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_run_dir = getattr(net_common, 'run_server_dir', None)
        net_common.run_server_dir = self._tmpdir.name

    def tearDown(self):
        net_common.run_server_dir = self._orig_run_dir
        self._tmpdir.cleanup()


def _make_player(*, thug_attack=False, debug_mode=False, name='Victim'):
    flags_set = set()
    if thug_attack:
        flags_set.add(PlayerFlags.THUG_ATTACK)
    if debug_mode:
        flags_set.add(PlayerFlags.DEBUG_MODE)

    player = MagicMock()
    player.name = name
    player.unsaved_changes = False
    player.query_flag = MagicMock(side_effect=lambda f: f in flags_set)

    def _clear(f):
        flags_set.discard(f)
    player.clear_flag = MagicMock(side_effect=_clear)
    return player


def _make_ctx(player, prompts=None):
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    it = iter(prompts or [])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    ctx.server.monsters = [{'number': 60, 'name': 'THUG'}]
    return ctx


class TestNoFlagSet(_RunDirMixin, unittest.IsolatedAsyncioTestCase):

    async def test_noop_when_flag_not_set(self):
        from bar.thug_attack import maybe_trigger_thug_attack

        player = _make_player(thug_attack=False)
        ctx = _make_ctx(player)

        with patch('combat.enter_combat', new_callable=AsyncMock) as mock_combat:
            await maybe_trigger_thug_attack(ctx)

        mock_combat.assert_not_awaited()
        ctx.send.assert_not_called()


class TestNormalAmbush(_RunDirMixin, unittest.IsolatedAsyncioTestCase):

    async def test_ambush_triggers_combat_and_clears_flag(self):
        from bar.blue_djinn import add_contract
        from bar.thug_attack import maybe_trigger_thug_attack

        add_contract('Victim', 'SOMEBODY', 'Hirer1', 500)
        player = _make_player(thug_attack=True, debug_mode=False)
        ctx = _make_ctx(player)

        with patch('combat.enter_combat', new_callable=AsyncMock) as mock_combat:
            await maybe_trigger_thug_attack(ctx)

        mock_combat.assert_awaited_once()
        args = mock_combat.await_args.args
        self.assertIs(args[0], ctx)
        self.assertEqual(args[1]['number'], 60)

        player.clear_flag.assert_called_once_with(PlayerFlags.THUG_ATTACK)
        self.assertTrue(player.unsaved_changes)

    async def test_ambush_mentions_hirer_display_name(self):
        from bar.blue_djinn import add_contract
        from bar.thug_attack import maybe_trigger_thug_attack

        add_contract('Victim', 'Some Enemy', 'RealHirer', 500)
        player = _make_player(thug_attack=True)
        ctx = _make_ctx(player)

        with patch('combat.enter_combat', new_callable=AsyncMock):
            await maybe_trigger_thug_attack(ctx)

        sent = str(ctx.send.call_args_list)
        self.assertIn('Some Enemy', sent)

    async def test_ambush_resolves_pending_contracts(self):
        from bar.blue_djinn import add_contract, pending_contracts
        from bar.thug_attack import maybe_trigger_thug_attack

        add_contract('Victim', 'SOMEBODY', 'Hirer1', 500)
        player = _make_player(thug_attack=True)
        ctx = _make_ctx(player)

        with patch('combat.enter_combat', new_callable=AsyncMock):
            await maybe_trigger_thug_attack(ctx)

        self.assertEqual(pending_contracts('Victim'), [])

    async def test_missing_thug_monster_still_clears_flag(self):
        from bar.thug_attack import maybe_trigger_thug_attack

        player = _make_player(thug_attack=True)
        ctx = _make_ctx(player)
        ctx.server.monsters = []   # THUG not found

        with patch('combat.enter_combat', new_callable=AsyncMock) as mock_combat:
            await maybe_trigger_thug_attack(ctx)

        mock_combat.assert_not_awaited()
        player.clear_flag.assert_called_once_with(PlayerFlags.THUG_ATTACK)


class TestDebugModeSkip(_RunDirMixin, unittest.IsolatedAsyncioTestCase):

    async def test_debug_mode_yes_skips_ambush_leaves_flag(self):
        from bar.thug_attack import maybe_trigger_thug_attack

        player = _make_player(thug_attack=True, debug_mode=True)
        ctx = _make_ctx(player, prompts=['y'])

        with patch('combat.enter_combat', new_callable=AsyncMock) as mock_combat:
            await maybe_trigger_thug_attack(ctx)

        mock_combat.assert_not_awaited()
        player.clear_flag.assert_not_called()

    async def test_debug_mode_no_still_triggers_ambush(self):
        from bar.thug_attack import maybe_trigger_thug_attack

        player = _make_player(thug_attack=True, debug_mode=True)
        ctx = _make_ctx(player, prompts=['n'])

        with patch('combat.enter_combat', new_callable=AsyncMock) as mock_combat:
            await maybe_trigger_thug_attack(ctx)

        mock_combat.assert_awaited_once()
        player.clear_flag.assert_called_once_with(PlayerFlags.THUG_ATTACK)


if __name__ == '__main__':
    unittest.main()
