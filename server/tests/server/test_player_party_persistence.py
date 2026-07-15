"""tests/server/test_player_party_persistence.py

Regression test: player.party (owned allies) was written by Player.save()
(full __dict__ dump) but never read back by _load() -- the same gap
shield/armor/active_shield_id and loan_amount/loan_days had before
earlier fixes. Found live while playtesting encounters/ally_starvation.py:
a player's allies silently vanished on every reconnect, so no
party-dependent mechanic (ally_events.try_ally_find_gold,
try_hungry_ally, try_ally_death_save, encounters/ally_starvation.py)
could ever actually fire against a real, persisted ally.
"""
from __future__ import annotations

import tempfile
import unittest

from bar.ally_data import Ally
from player import Player


class TestPartyPersistence(unittest.TestCase):
    def test_owned_ally_survives_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='partytest', name='Partytest')
            ally = Ally(name='Grog', gender='m', strength=15, to_hit=4)
            player.party.add_member(player, ally)
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='partytest', name='Partytest')
            self.assertTrue(reloaded._load())
            self.assertEqual(len(reloaded.party), 1)
            restored = reloaded.party[0]
            self.assertIsInstance(restored, Ally)
            self.assertEqual(restored.name, 'Grog')
            self.assertEqual(restored.strength, 15)


if __name__ == '__main__':
    unittest.main()
