"""tests/server/test_player_survival_counter_persistence.py

Regression test: player._survival_counter (survival.py's survival_tick()
command counter) used to be session-only, resetting to 0 on every login --
Ryan pointed out that let a player dodge hunger/thirst indefinitely by
just logging out and back in right before the next depletion step. Same
gap food/drink had before an earlier fix (see
test_player_food_drink_persistence.py) -- now a plain Player.__init__/
simple_keys field like everything else in that list.
"""
from __future__ import annotations

import tempfile
import unittest

from player import Player


class TestSurvivalCounterPersistence(unittest.TestCase):
    def test_survival_counter_survives_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='survivalcountertest', name='Survivalcountertest')
            player._survival_counter = 7
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='survivalcountertest', name='Survivalcountertest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded._survival_counter, 7)


if __name__ == '__main__':
    unittest.main()
