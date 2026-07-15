"""tests/server/test_player_loan_persistence.py

Regression test: player.loan_amount/loan_days (silver owed to Vinny at
the Bar, and days left to repay) were written by Player.save() (full
__dict__ dump) but never read back by _load() -- the exact same gap
shield/armor/active_shield_id had before an earlier fix this session,
found live while playtesting encounters/djinn_sighting.py (a player's
debt silently reset to 0 on every reconnect, so the debt-collection
ambush -- both the existing Bar overdue-loan check and the new random
Blue Djinn sighting -- could never actually fire in practice).
"""
from __future__ import annotations

import tempfile
import unittest

from player import Player


class TestLoanPersistence(unittest.TestCase):
    def test_loan_amount_and_days_survive_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='loantest', name='Loantest')
            player.loan_amount = 500
            player.loan_days = 3
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='loantest', name='Loantest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded.loan_amount, 500)
            self.assertEqual(reloaded.loan_days, 3)


if __name__ == '__main__':
    unittest.main()
