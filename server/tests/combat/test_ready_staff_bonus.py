"""tests/combat/test_ready_staff_bonus.py

Covers commands/ready.py's staff-enhances-spellcasting flavor line: shown
when a Wizard readies a WOOD STAFF/STORM STAFF (commands/get.py's
_STAFF_IDS) -- the moment the mechanical bonus (commands/cast.py's
_caster_bonus()) actually takes effect, distinct from commands/get.py's
own pickup-time reminder, which fires before the item is even readied.

Deliberately a separate file from tests/combat/test_ready.py, which
registers a `network_context` stub in sys.modules (a known cross-test
pollution risk -- see this project's memory on it) -- this file uses real
Player/network-style fakes instead, matching the pattern already
established in tests/shoppe/test_wizard.py and tests/commands/test_cast.py.
"""
from __future__ import annotations

import unittest

from base_classes import PlayerClass
from commands.ready import ReadyCommand
from inventory import Inventory
from items import Item, ItemCategory
from player import Player


def _weapon(name, item_id):
    return Item(id_number=item_id, name=name, category=ItemCategory.WEAPON,
                stability=10, to_hit=50, weapon_class=None)


def _new_player(char_class=None) -> Player:
    player = Player(name='Rulan', char_class=char_class)
    player.inventory = Inventory(capacity=14)
    player.stats['Strength'] = 15  # comfortably above ReadyCommand's _MIN_STR
    return player


class _FakeCtx:
    def __init__(self, player, responses=()):
        self.player = player
        self._q = list(responses)
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestStaffFlavorOnReady(unittest.IsolatedAsyncioTestCase):
    async def test_wizard_readying_wood_staff_gets_the_flavor_line(self):
        player = _new_player(PlayerClass.WIZARD)
        player.inventory.add(_weapon('WOOD STAFF', 3))
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'wood staff')
        self.assertIn('your spells will draw on its power', ctx._flat())

    async def test_wizard_readying_storm_staff_also_gets_it(self):
        player = _new_player(PlayerClass.WIZARD)
        player.inventory.add(_weapon('STORM STAFF', 47))
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'storm staff')
        self.assertIn('your spells will draw on its power', ctx._flat())

    async def test_non_wizard_readying_a_staff_gets_no_flavor_line(self):
        player = _new_player(PlayerClass.FIGHTER)
        player.inventory.add(_weapon('WOOD STAFF', 3))
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'wood staff')
        self.assertNotIn('draw on its power', ctx._flat())

    async def test_wizard_readying_a_non_staff_weapon_gets_no_flavor_line(self):
        player = _new_player(PlayerClass.WIZARD)
        player.inventory.add(_weapon('DAGGER', 7))
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'dagger')
        self.assertNotIn('draw on its power', ctx._flat())
        self.assertIn('DAGGER READIED.', ctx._flat())


if __name__ == '__main__':
    unittest.main()
