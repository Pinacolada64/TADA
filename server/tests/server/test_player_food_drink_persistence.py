"""tests/server/test_player_food_drink_persistence.py

Regression test: player.food/player.drink were written by Player.save()
(full __dict__ dump) but never read back by _load() -- the same gap
shield/armor/loan_amount/party had before earlier fixes. Found live while
testing spells/charm.py's CHARM POTION: a player's thirst silently reset
to "not thirsty" (drink=20, the __init__ default) on every reconnect, so
DrinkCommand's "You're not thirsty" gate made it impossible to ever drink
anything again after logging back in.
"""
from __future__ import annotations

import tempfile
import unittest

from player import Player


class TestFoodDrinkPersistence(unittest.TestCase):
    def test_food_and_drink_survive_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='fooddrinktest', name='Fooddrinktest')
            player.food = 3
            player.drink = 5
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='fooddrinktest', name='Fooddrinktest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded.food, 3)
            self.assertEqual(reloaded.drink, 5)


if __name__ == '__main__':
    unittest.main()
