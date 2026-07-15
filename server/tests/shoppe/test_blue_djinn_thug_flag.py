"""tests/test_blue_djinn_thug_flag.py

Tests for bar/blue_djinn.py's THUG_ATTACK flag wiring:
  - set_thug_flag_on_target() -- online (live Player) and offline (save
    file) targets
  - resolve_all_pending_contracts()
  - _hire() actually calls set_thug_flag_on_target() on a successful hire

Run with:
    python -m pytest tests/test_blue_djinn_thug_flag.py -v
"""
from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from unittest.mock import AsyncMock, MagicMock

import net_common
from flags import PlayerFlags
from tests.conftest import seed_test_account


class _RunDirMixin:
    """Isolate net_common.run_server_dir (and therefore Player save/load
    and bar/blue_djinn.py's hit_contracts.json) to a fresh tmpdir per test."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_run_dir = getattr(net_common, 'run_server_dir', None)
        net_common.run_server_dir = self._tmpdir.name

    def tearDown(self):
        net_common.run_server_dir = self._orig_run_dir
        self._tmpdir.cleanup()


class TestSetThugFlagOnTarget(_RunDirMixin, unittest.TestCase):

    def test_online_target_gets_flag_set_directly(self):
        from bar.blue_djinn import set_thug_flag_on_target
        from player import Player

        target = Player(name='Victim', id='victim')
        target.unsaved_changes = False

        client = MagicMock()
        client.ctx = MagicMock()
        client.ctx.player = target
        ctx = MagicMock()
        ctx.server.clients = {'addr1': client}

        set_thug_flag_on_target(ctx, 'Victim')

        self.assertTrue(target.query_flag(PlayerFlags.THUG_ATTACK))
        self.assertTrue(target.unsaved_changes)

    def test_online_target_matched_case_insensitively(self):
        from bar.blue_djinn import set_thug_flag_on_target
        from player import Player

        target = Player(name='Victim', id='victim')
        client = MagicMock()
        client.ctx = MagicMock()
        client.ctx.player = target
        ctx = MagicMock()
        ctx.server.clients = {'addr1': client}

        set_thug_flag_on_target(ctx, 'VICTIM')
        self.assertTrue(target.query_flag(PlayerFlags.THUG_ATTACK))

    def test_offline_target_flag_persists_to_save_file(self):
        from bar.blue_djinn import set_thug_flag_on_target
        from player import Player

        seed_test_account('offlineguy', 'pw')

        ctx = MagicMock()
        ctx.server.clients = {}   # nobody online

        set_thug_flag_on_target(ctx, 'offlineguy')

        reloaded = Player(name='offlineguy', id='offlineguy')
        self.assertTrue(reloaded.query_flag(PlayerFlags.THUG_ATTACK))


class TestResolveAllPendingContracts(_RunDirMixin, unittest.TestCase):

    def test_marks_all_unresolved_entries(self):
        from bar.blue_djinn import (
            add_contract, pending_contracts, resolve_all_pending_contracts,
        )

        add_contract('Victim', 'SOMEBODY', 'Hirer1', 500)
        add_contract('Victim', 'Hirer2', 'Hirer2', 1000)
        self.assertEqual(len(pending_contracts('Victim')), 2)

        resolve_all_pending_contracts('Victim')

        self.assertEqual(pending_contracts('Victim'), [])

    def test_does_not_affect_other_targets(self):
        from bar.blue_djinn import add_contract, pending_contracts, resolve_all_pending_contracts

        add_contract('Victim', 'SOMEBODY', 'Hirer1', 500)
        add_contract('OtherGuy', 'SOMEBODY', 'Hirer1', 500)

        resolve_all_pending_contracts('Victim')

        self.assertEqual(pending_contracts('Victim'), [])
        self.assertEqual(len(pending_contracts('OtherGuy')), 1)


class TestHireSetsThugFlag(_RunDirMixin, unittest.IsolatedAsyncioTestCase):

    def _make_hirer_ctx(self, prompts):
        player = MagicMock()
        player.name = 'Hirer'
        player.get_silver = MagicMock(return_value=10_000)
        player.subtract_silver = MagicMock(return_value=True)
        player.unsaved_changes = False

        ctx = MagicMock()
        ctx.player = player
        ctx.send = AsyncMock()
        it = iter(prompts)
        ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
        return ctx, player

    async def test_hire_sets_flag_on_online_target(self):
        from bar.blue_djinn import _hire
        from player import Player

        target = Player(name='Victim', id='victim')
        target_client = MagicMock()
        target_client.ctx = MagicMock()
        target_client.ctx.player = target

        ctx, hirer = self._make_hirer_ctx(['Victim', 'y', 'y', 'n'])
        ctx.server.clients = {'t': target_client}

        with unittest.mock.patch('bar.blue_djinn.broadcast_area', new_callable=AsyncMock):
            await _hire(ctx)

        self.assertTrue(target.query_flag(PlayerFlags.THUG_ATTACK))


if __name__ == '__main__':
    unittest.main()
