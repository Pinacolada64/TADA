"""tests/server/test_dead_monsters_persistence.py

Regression coverage for player.dead_monsters (the per-kill log) and
player.monsters_killed (the derived @property, len(dead_monsters)):

  - dead_monsters survives a real save/load round-trip (same pattern as
    test_player_party_persistence.py).
  - monsters_killed is read-only and always reflects dead_monsters'
    current length, including duplicate entries (killing the same monster
    twice counts twice -- Ryan's request; no dedup).
  - An older save file written before dead_monsters existed (key
    'monsters_killed' holding what used to be a deduplicated list) is
    migrated into dead_monsters on load, so upgrading doesn't silently
    erase kill history.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from player import Player


class TestDeadMonstersPersistence(unittest.TestCase):

    def test_dead_monsters_survives_save_and_load(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            player = Player(id='killtest', name='Killtest')
            player.dead_monsters.append(7)
            player.dead_monsters.append(7)   # same monster, killed twice
            player.dead_monsters.append(12)
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='killtest', name='Killtest')
            self.assertTrue(reloaded._load())
            self.assertEqual(reloaded.dead_monsters, [7, 7, 12])
            self.assertEqual(reloaded.monsters_killed, 3)

    def test_monsters_killed_is_read_only_derived_count(self):
        player = Player(id='killtest2', name='Killtest2')
        self.assertEqual(player.monsters_killed, 0)
        player.dead_monsters.extend([1, 2, 3, 3])
        self.assertEqual(player.monsters_killed, 4)
        with self.assertRaises(AttributeError):
            player.monsters_killed = 99

    def test_old_save_with_monsters_killed_key_migrates(self):
        """A save written before dead_monsters existed had a deduplicated
        'monsters_killed' list under that key -- must still load, not
        silently lose the player's kill history."""
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            path = Path(tmp) / 'player-oldsave.json'
            path.write_text(json.dumps({'id': 'oldsave', 'name': 'Oldsave',
                                         'monsters_killed': [3, 8, 15]}))

            player = Player(id='oldsave', name='Oldsave')
            self.assertTrue(player._load())
            self.assertEqual(player.dead_monsters, [3, 8, 15])
            self.assertEqual(player.monsters_killed, 3)

    def test_dead_monsters_key_takes_priority_over_old_key(self):
        """If a save somehow has both keys, the current dead_monsters key wins."""
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp
            path = Path(tmp) / 'player-bothkeys.json'
            path.write_text(json.dumps({'id': 'bothkeys', 'name': 'Bothkeys',
                                         'dead_monsters': [1, 1, 1],
                                         'monsters_killed': [99]}))

            player = Player(id='bothkeys', name='Bothkeys')
            self.assertTrue(player._load())
            self.assertEqual(player.dead_monsters, [1, 1, 1])


if __name__ == '__main__':
    unittest.main()
