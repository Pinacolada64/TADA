"""tests/combat/test_weapon_survives_reconnect.py

End-to-end regression for the "attack drops you to the main prompt" bug:
a readied weapon that survived a save/load round trip used to come back
as a bare items.Item (Inventory.from_json()'s old "lightweight Item"
behavior), missing sound_effect/weapon_class entirely. Combat's
weapon_sfx() then did `weapon.sound_effect` with no guard, raising
AttributeError -- caught by command_processor's blanket except-handler,
which logs server-side only and silently returns the player to the main
prompt with zero feedback.

This test exercises the real fix end-to-end: Player(..., weapons_data=...)
-- exactly what simple_server.py's _authenticate() and commands/connect.py
now pass at login -- must come back out of Inventory.from_json() with a
real Weapon, not a bare Item, so weapon_sfx()/weapon_bonus() return the
weapon's actual stats rather than the class-based fallback table.

Run with:
    python -m pytest tests/combat/test_weapon_survives_reconnect.py -v
"""
from __future__ import annotations

import tempfile
import unittest

from item_system import weapon_sfx
from items import Item, Weapon
from player import Player

_LONG_SWORD = {
    'number': 1, 'location': 2, 'name': 'LONG SWORD', 'kind': 'standard',
    'sound_effect': ['SWISH!', 'SLASH!'], 'stability': 50, 'to_hit': 60,
    'price': 250, 'weapon_class': 'bash/slash',
}


class TestWeaponSurvivesReconnect(unittest.TestCase):

    def test_readied_weapon_keeps_real_stats_after_reload(self):
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp

            player = Player(id='reconnecttest', name='Reconnecttest')
            weapon = Weapon(id_number=1, name='LONG SWORD', location=0,
                             kind='standard', sound_effect=('SWISH!', 'SLASH!'),
                             stability=50, to_hit=60, price=250,
                             weapon_class='bash/slash')
            player.inventory.add(weapon)
            player.readied_weapon = weapon
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            # Reconnect: exactly what simple_server.py's _authenticate() and
            # commands/connect.py now do -- pass the server's raw
            # weapons.json list through so the reload can resolve real
            # Weapon objects, not bare Items.
            reloaded = Player(id='reconnecttest', name='Reconnecttest',
                               weapons_data=[_LONG_SWORD])

            entries = reloaded.inventory.find(name='LONG SWORD')
            self.assertEqual(len(entries), 1)
            restored_weapon = entries[0].item

            self.assertIsInstance(restored_weapon, Weapon)
            self.assertNotIsInstance(restored_weapon, Item)

            # Simulate re-readying after reconnect (commands/ready.py:405
            # pulls straight from entry.item) and swinging -- this is the
            # exact call that crashed before the fix.
            reloaded.readied_weapon = restored_weapon
            self.assertEqual(weapon_sfx(reloaded.readied_weapon), ('SWISH!', 'SLASH!'))
            self.assertEqual(reloaded.readied_weapon.weapon_class, 'bash/slash')
            self.assertEqual(reloaded.readied_weapon.stability, 50)
            self.assertEqual(reloaded.readied_weapon.to_hit, 60)

    def test_readied_weapon_without_weapons_data_no_longer_crashes(self):
        """Even without weapons_data (e.g. a code path that can't supply
        it), the pre-existing defensive-getattr fix in weapon_sfx() means
        a bare Item no longer crashes combat -- it just degrades to the
        class-based fallback sfx instead of the real per-weapon sound."""
        import net_common

        with tempfile.TemporaryDirectory() as tmp:
            net_common.run_server_dir = tmp

            player = Player(id='reconnecttest2', name='Reconnecttest2')
            weapon = Weapon(id_number=1, name='LONG SWORD', location=0,
                             kind='standard', sound_effect=('SWISH!', 'SLASH!'),
                             stability=50, to_hit=60, price=250,
                             weapon_class='bash/slash')
            player.inventory.add(weapon)
            player.unsaved_changes = True
            self.assertTrue(player.save(force=True))

            reloaded = Player(id='reconnecttest2', name='Reconnecttest2')  # no weapons_data
            entry = reloaded.inventory.find(name='LONG SWORD')[0]
            reloaded.readied_weapon = entry.item

            # Must not raise.
            miss, hit = weapon_sfx(reloaded.readied_weapon)
            self.assertIsInstance(miss, str)
            self.assertIsInstance(hit, str)


if __name__ == '__main__':
    unittest.main(verbosity=2)
