"""tests/commands/test_examine.py

Covers commands/examine.py's EXAMINE flavor text (SPUR.MISC3.S exam.a/exam2/
exam3), moved here from commands/look.py (LOOK now only gives a plain
description -- Ryan's request):

  - Items with data-authored "examine" text (objects.json/weapons.json/
    rations.json) always show it -- New in TADA, Ryan's request: this text
    used to live in an if-chain keyed off item name/kind.
  - Magic weapons (weapons.json kind=="magic") and cursed treasures
    (objects.json type=="cursed") without their own "examine" override go
    through exam2's skill roll (60% success) and one-shot "already
    examined" memory (player.last_examined).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from commands.examine import ExamineCommand, _examine_item, _raw_item_data
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory, Rations, Weapon
from player import Player


class _FakeServer:
    def __init__(self, items=None, weapons=None, rations=None):
        self.items    = items or []
        self.weapons  = weapons or []
        self.rations  = rations or []
        self.game_map = None


class _FakeClient:
    room = None


class _FakeCtx:
    def __init__(self, player, server):
        self.player = player
        self.server = server
        self.client = _FakeClient()
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def send_room(self, *args, **kwargs):
        pass


def _player() -> Player:
    p = Player(name='Rulan')
    p.inventory = Inventory(capacity=10)
    return p


class TestRawItemData(unittest.TestCase):
    def test_finds_weapon_pool_entry(self):
        server = _FakeServer(weapons=[{'number': 22, 'name': 'STORM AXE', 'kind': 'standard'}])
        weapon = Weapon(id_number=22, name='STORM AXE', kind='standard')
        ctx = _FakeCtx(_player(), server)
        raw = _raw_item_data(ctx, weapon)
        self.assertEqual(raw['name'], 'STORM AXE')

    def test_finds_rations_pool_entry(self):
        server = _FakeServer(rations=[{'number': 65, 'name': 'POTION OF SKILL', 'kind': 'drink'}])
        ration = Rations(number=65, name='POTION OF SKILL', kind='drink', price=50)
        ctx = _FakeCtx(_player(), server)
        raw = _raw_item_data(ctx, ration)
        self.assertEqual(raw['name'], 'POTION OF SKILL')

    def test_finds_items_pool_entry(self):
        server = _FakeServer(items=[{'number': 41, 'name': 'gold rose', 'type': 'treasure'}])
        item = Item(id_number=41, name='gold rose', category=ItemCategory.ITEM)
        ctx = _FakeCtx(_player(), server)
        raw = _raw_item_data(ctx, item)
        self.assertEqual(raw['name'], 'gold rose')

    def test_returns_none_when_not_found(self):
        server = _FakeServer()
        item = Item(id_number=999, name='mystery', category=ItemCategory.ITEM)
        ctx = _FakeCtx(_player(), server)
        self.assertIsNone(_raw_item_data(ctx, item))


class TestExamineDataAuthoredText(unittest.TestCase):
    """Items with their own 'examine' field always show it -- no roll gate,
    matching SPUR's exam3 branch."""

    def test_storm_weapon_examine_text(self):
        server = _FakeServer(weapons=[
            {'number': 22, 'name': 'STORM AXE', 'kind': 'standard',
             'examine': 'There is much power in the STORM AXE!'},
        ])
        weapon = Weapon(id_number=22, name='STORM AXE', kind='standard')
        ctx = _FakeCtx(_player(), server)
        self.assertEqual(_examine_item(ctx, 'STORM AXE', weapon),
                          'There is much power in the STORM AXE!')

    def test_potion_examine_text(self):
        server = _FakeServer(rations=[
            {'number': 65, 'name': 'POTION OF SKILL', 'kind': 'drink',
             'examine': 'It is a magic potion!'},
        ])
        ration = Rations(number=65, name='POTION OF SKILL', kind='drink', price=50)
        ctx = _FakeCtx(_player(), server)
        self.assertEqual(_examine_item(ctx, 'POTION OF SKILL', ration), 'It is a magic potion!')

    def test_named_treasure_examine_text(self):
        server = _FakeServer(items=[
            {'number': 82, 'name': 'Crystal Pendant', 'type': 'treasure',
             'examine': "In small letters you see; 'PROTECTS FROM STONE SPELL!'"},
        ])
        item = Item(id_number=82, name='Crystal Pendant', category=ItemCategory.ITEM)
        ctx = _FakeCtx(_player(), server)
        self.assertEqual(_examine_item(ctx, 'Crystal Pendant', item),
                          "In small letters you see; 'PROTECTS FROM STONE SPELL!'")

    def test_examine_text_bypasses_magic_kind_roll(self):
        """A weapon can be both kind=='magic' and carry its own examine
        text (none currently do, but the precedence must still hold) --
        the data-authored text always wins, no roll involved."""
        server = _FakeServer(weapons=[
            {'number': 1, 'name': 'ODD BLADE', 'kind': 'magic', 'examine': 'It hums oddly.'},
        ])
        weapon = Weapon(id_number=1, name='ODD BLADE', kind='magic')
        ctx = _FakeCtx(_player(), server)
        with patch('random.randint', return_value=100):  # would fail the roll if reached
            self.assertEqual(_examine_item(ctx, 'ODD BLADE', weapon), 'It hums oddly.')


class TestExamineMagicRoll(unittest.TestCase):
    def _weapon_and_ctx(self):
        server = _FakeServer(weapons=[{'number': 1, 'name': 'WOODEN STAKE', 'kind': 'magic'}])
        weapon = Weapon(id_number=1, name='WOODEN STAKE', kind='magic')
        ctx = _FakeCtx(_player(), server)
        return weapon, ctx

    def test_success_reveals_magical(self):
        weapon, ctx = self._weapon_and_ctx()
        with patch('random.randint', return_value=1):  # <=60 -> success
            result = _examine_item(ctx, 'WOODEN STAKE', weapon)
        self.assertEqual(result, 'This WOODEN STAKE is Magical.')

    def test_failure_message(self):
        weapon, ctx = self._weapon_and_ctx()
        with patch('random.randint', return_value=100):  # >60 -> fail
            result = _examine_item(ctx, 'WOODEN STAKE', weapon)
        self.assertEqual(result, 'Your examination fails...')

    def test_success_marks_last_examined(self):
        weapon, ctx = self._weapon_and_ctx()
        with patch('random.randint', return_value=1):
            _examine_item(ctx, 'WOODEN STAKE', weapon)
        self.assertEqual(ctx.player.last_examined, 'WOODEN STAKE')

    def test_repeat_examine_after_success_says_already_examined(self):
        weapon, ctx = self._weapon_and_ctx()
        with patch('random.randint', return_value=1):
            _examine_item(ctx, 'WOODEN STAKE', weapon)          # first: reveals
            result = _examine_item(ctx, 'WOODEN STAKE', weapon)  # second: already examined
        self.assertEqual(result, 'You have already examined this!')

    def test_repeat_examine_still_rolls_and_can_fail(self):
        """SPUR rolls before checking xz$ -- a failed roll on a repeat
        examine still shows the failure message, not 'already examined'."""
        weapon, ctx = self._weapon_and_ctx()
        with patch('random.randint', return_value=1):
            _examine_item(ctx, 'WOODEN STAKE', weapon)  # reveals, sets last_examined
        with patch('random.randint', return_value=100):
            result = _examine_item(ctx, 'WOODEN STAKE', weapon)
        self.assertEqual(result, 'Your examination fails...')

    def test_different_item_does_not_trigger_already_examined(self):
        weapon, ctx = self._weapon_and_ctx()
        ctx.player.last_examined = 'SOME OTHER ITEM'
        with patch('random.randint', return_value=1):
            result = _examine_item(ctx, 'WOODEN STAKE', weapon)
        self.assertEqual(result, 'This WOODEN STAKE is Magical.')


class TestExamineCursedRoll(unittest.TestCase):
    def _item_and_ctx(self):
        server = _FakeServer(items=[{'number': 1, 'name': 'blue gem', 'type': 'cursed'}])
        item = Item(id_number=1, name='blue gem', category=ItemCategory.ITEM)
        ctx = _FakeCtx(_player(), server)
        return item, ctx

    def test_success_reveals_cursed(self):
        item, ctx = self._item_and_ctx()
        with patch('random.randint', return_value=1):
            result = _examine_item(ctx, 'blue gem', item)
        self.assertEqual(result, 'This blue gem is Cursed.')

    def test_failure_message(self):
        item, ctx = self._item_and_ctx()
        with patch('random.randint', return_value=100):
            result = _examine_item(ctx, 'blue gem', item)
        self.assertEqual(result, 'Your examination fails...')


class TestExamineOrdinaryFallback(unittest.TestCase):
    def test_unremarkable_item_is_ordinary(self):
        server = _FakeServer(items=[{'number': 1, 'name': 'rock', 'type': 'treasure'}])
        item = Item(id_number=1, name='rock', category=ItemCategory.ITEM)
        ctx = _FakeCtx(_player(), server)
        self.assertEqual(_examine_item(ctx, 'rock', item), 'It looks pretty ordinary..')

    def test_unknown_item_not_in_any_pool_is_ordinary(self):
        server = _FakeServer()
        item = Item(id_number=999, name='mystery', category=ItemCategory.ITEM)
        ctx = _FakeCtx(_player(), server)
        self.assertEqual(_examine_item(ctx, 'mystery', item), 'It looks pretty ordinary..')

    def test_standard_weapon_is_ordinary(self):
        server = _FakeServer(weapons=[{'number': 1, 'name': 'SWORD', 'kind': 'standard'}])
        weapon = Weapon(id_number=1, name='SWORD', kind='standard')
        ctx = _FakeCtx(_player(), server)
        self.assertEqual(_examine_item(ctx, 'SWORD', weapon), 'It looks pretty ordinary..')


class TestExamineStatue(unittest.TestCase):
    """A room statue (commands/get.py's is_statue pseudo-item, set by
    statues.py's add_statue()) isn't a real objects.json entry -- no
    id_number for _raw_item_data() to find -- so EXAMINE special-cases
    it (Ryan's request) to name the petrified player and the monster
    responsible, rather than falling through to the generic "It looks
    pretty ordinary.." default."""

    def test_statue_names_victim_and_monster(self):
        item = Item(name='a statue', category=ItemCategory.ITEM, is_statue=True,
                   victim='Alice', monster='MEDUSA')
        ctx = _FakeCtx(_player(), _FakeServer())
        self.assertEqual(
            _examine_item(ctx, 'a statue', item),
            'You inspect the statue of Alice. At the base is a small '
            'brass plaque which reads, "Artist: MEDUSA."',
        )

    def test_statue_does_not_fall_through_to_ordinary(self):
        item = Item(name='a statue', category=ItemCategory.ITEM, is_statue=True,
                   victim='Alice', monster='MEDUSA')
        ctx = _FakeCtx(_player(), _FakeServer())
        self.assertNotEqual(_examine_item(ctx, 'a statue', item), 'It looks pretty ordinary..')

    def test_missing_victim_or_monster_does_not_crash(self):
        item = Item(name='a statue', category=ItemCategory.ITEM, is_statue=True)
        ctx = _FakeCtx(_player(), _FakeServer())
        text = _examine_item(ctx, 'a statue', item)
        self.assertIn('someone', text)
        self.assertIn('Unknown', text)


class TestExamineCommandIntegration(unittest.IsolatedAsyncioTestCase):
    """End-to-end: 'examine <item>' against an inventory item uses the
    data-driven examine text."""

    async def test_examine_inventory_item_shows_examine_text(self):
        server = _FakeServer(items=[
            {'number': 41, 'name': 'gold rose', 'type': 'treasure',
             'examine': 'It looks VERY valuable, but beware the thorns!'},
        ])
        player = _player()
        item = Item(id_number=41, name='gold rose', category=ItemCategory.ITEM)
        player.inventory.add(item)
        ctx = _FakeCtx(player, server)

        await ExamineCommand().execute(ctx, 'gold', 'rose')
        self.assertIn('It looks VERY valuable, but beware the thorns!', ctx.sent)

    async def test_examine_no_target_reports_empty_area(self):
        player = _player()
        ctx = _FakeCtx(player, _FakeServer())
        await ExamineCommand().execute(ctx)
        self.assertIn('This area is empty..', ctx.sent)


if __name__ == '__main__':
    unittest.main(verbosity=2)
