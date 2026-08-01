"""tests/social/test_login_equipment_lines.py

Unit tests for commands/connect.py's _login_equipment_lines() -- the
"<name> is readied" notice shown at login for a currently-equipped
shield, matching origin/skip's fuller SPUR.LOGON.S revision (this repo's
own SPUR-code copy resets xt$ at login with no reseed at all). See
Player.__init__'s item_history seeding for the ring-buffer half of this.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from commands.connect import _login_equipment_lines
from player import Player


class _FakeCtx:
    def __init__(self, items):
        self.server = MagicMock()
        self.server.items = items


class TestLoginEquipmentLines(unittest.TestCase):
    def test_no_active_shield_returns_no_lines(self):
        player = Player(name='Rulan')
        ctx = _FakeCtx(items=[])
        self.assertEqual(_login_equipment_lines(ctx, player), [])

    def test_active_shield_produces_sentence_cased_readied_line(self):
        player = Player(name='Rulan')
        player.active_shield_id = 4
        ctx = _FakeCtx(items=[{'number': 4, 'name': 'small shield', 'type': 'shield', 'price': 2}])
        lines = _login_equipment_lines(ctx, player)
        self.assertEqual(lines, ['Small shield is readied.'])

    def test_shield_id_not_found_in_items_returns_no_lines(self):
        player = Player(name='Rulan')
        player.active_shield_id = 999
        ctx = _FakeCtx(items=[{'number': 4, 'name': 'small shield', 'type': 'shield', 'price': 2}])
        self.assertEqual(_login_equipment_lines(ctx, player), [])


class TestItemHistorySeededFromActiveShield(unittest.TestCase):
    def test_item_history_seeded_from_active_shield_id_on_relogin(self):
        import net_common
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        net_common.run_server_dir = str(tmp.name)

        original = Player(id='shieldtest', name='shieldtest')
        original.active_shield_id = 4
        assert original.save(force=True)

        relogged = Player(name='shieldtest', id='shieldtest')
        self.assertEqual(relogged.item_history, [4])

    def test_item_history_empty_when_no_active_shield(self):
        import net_common
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        net_common.run_server_dir = str(tmp.name)

        original = Player(id='noshieldtest', name='noshieldtest')
        assert original.save(force=True)

        relogged = Player(name='noshieldtest', id='noshieldtest')
        self.assertEqual(relogged.item_history, [])


if __name__ == '__main__':
    unittest.main()
