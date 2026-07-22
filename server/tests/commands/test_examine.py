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

from base_classes import PlayerRace
from commands.examine import (
    ExamineCommand,
    _examine_item,
    _examine_monster,
    _monster_disease_check,
    _monster_food,
    _monster_treasure,
    _player_has_food,
    _player_has_item,
    _raw_item_data,
    room_monster,
)
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory, Rations, Weapon
from player import Player


class _FakeServer:
    def __init__(self, items=None, weapons=None, rations=None, monsters=None, game_map=None):
        self.items      = items or []
        self.weapons    = weapons or []
        self.rations    = rations or []
        self.monsters   = monsters or []
        self.game_map   = game_map
        self.room_items = {}


class _FakeRoom:
    def __init__(self, monster=0, flags=None):
        self.monster = monster
        self.flags   = flags or []


class _FakeGameMap:
    def __init__(self, room):
        self._room = room

    def get_room(self, level, room_no):
        return self._room


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


_TROLL = {'number': 42, 'name': 'TROLL'}


def _ctx_with_monster(player, monster=None, room_flags=None, monsters=None):
    """A ctx wired up with a room (level 1, room 1) holding *monster*
    (defaults to _TROLL), for room_monster()/_examine_monster() tests."""
    monster = _TROLL if monster is None else monster
    room = _FakeRoom(monster=monster['number'], flags=room_flags)
    server = _FakeServer(monsters=monsters if monsters is not None else [monster],
                         game_map=_FakeGameMap(room))
    ctx = _FakeCtx(player, server)
    ctx.client.room = 1
    player.map_level = 1
    return ctx


class TestRoomMonster(unittest.TestCase):
    def test_finds_room_monster(self):
        ctx = _ctx_with_monster(_player())
        self.assertEqual(room_monster(ctx), _TROLL)

    def test_no_monster_when_room_has_none(self):
        ctx = _ctx_with_monster(_player(), monster={'number': 0, 'name': ''})
        room = _FakeRoom(monster=0)
        ctx.server.game_map = _FakeGameMap(room)
        self.assertIsNone(room_monster(ctx))

    def test_no_monster_when_number_not_in_pool(self):
        room = _FakeRoom(monster=99)
        server = _FakeServer(monsters=[_TROLL], game_map=_FakeGameMap(room))
        ctx = _FakeCtx(_player(), server)
        ctx.client.room = 1
        self.assertIsNone(room_monster(ctx))


class TestPlayerHasItemOrFood(unittest.TestCase):
    def test_no_inventory_means_no_item_or_food(self):
        player = _player()
        player.inventory = None
        self.assertFalse(_player_has_item(player))
        self.assertFalse(_player_has_food(player))

    def test_empty_inventory_means_no_item_or_food(self):
        player = _player()
        self.assertFalse(_player_has_item(player))
        self.assertFalse(_player_has_food(player))

    def test_generic_item_counts_as_item_not_food(self):
        player = _player()
        player.inventory.add(Item(id_number=1, name='rock', category=ItemCategory.ITEM))
        self.assertTrue(_player_has_item(player))
        self.assertFalse(_player_has_food(player))

    def test_food_ration_counts_as_food_not_item(self):
        player = _player()
        player.inventory.add(Rations(number=1, name='bread', kind='food', price=1))
        self.assertFalse(_player_has_item(player))
        self.assertTrue(_player_has_food(player))

    def test_drink_ration_is_neither_item_nor_food(self):
        player = _player()
        player.inventory.add(Rations(number=1, name='ale', kind='drink', price=1))
        self.assertFalse(_player_has_item(player))
        self.assertFalse(_player_has_food(player))

    def test_weapon_is_neither_item_nor_food(self):
        player = _player()
        player.inventory.add(Weapon(id_number=1, name='SWORD', kind='standard'))
        self.assertFalse(_player_has_item(player))
        self.assertFalse(_player_has_food(player))


class TestMonsterTreasure(unittest.TestCase):
    """SPUR.MISC3.S mon.dv's four tiers, mapped onto the nearest existing
    objects.json treasure items."""

    def _ctx(self):
        return _FakeCtx(_player(), _FakeServer())

    def test_lowest_tier_is_gold_coins(self):
        ctx = self._ctx()
        with patch('random.randint', return_value=1):  # roll<=40
            lines = _monster_treasure(ctx)
        self.assertEqual(lines, ['Your search reveals a gold coins!'])
        self.assertEqual(ctx.player.inventory.entries()[0].item.name, 'gold coins')

    def test_second_tier_is_diamond_pile(self):
        ctx = self._ctx()
        with patch('random.randint', return_value=50):  # 40<roll<=70
            _monster_treasure(ctx)
        self.assertEqual(ctx.player.inventory.entries()[0].item.name, 'diamond pile')

    def test_third_tier_is_diamonds(self):
        ctx = self._ctx()
        with patch('random.randint', return_value=80):  # 70<roll<=90
            _monster_treasure(ctx)
        self.assertEqual(ctx.player.inventory.entries()[0].item.name, 'diamonds')

    def test_top_tier_is_mound_of_jewels(self):
        ctx = self._ctx()
        with patch('random.randint', return_value=95):  # roll>90
            _monster_treasure(ctx)
        self.assertEqual(ctx.player.inventory.entries()[0].item.name, 'mound of jewels')

    def test_article_matches_item_name(self):
        ctx = self._ctx()
        with patch('random.randint', return_value=95):  # "mound of jewels" -- starts with 'm'
            lines = _monster_treasure(ctx)
        self.assertEqual(lines, ['Your search reveals a mound of jewels!'])


class TestMonsterFood(unittest.TestCase):
    def test_ogre_race_bonus_helps_reach_edible(self):
        player = _player()
        player.char_race = PlayerRace.OGRE
        ctx = _FakeCtx(player, _FakeServer())
        with patch('random.randint', return_value=30):  # 30+25=55, >=50
            lines = _monster_food(ctx, _TROLL, has_food=False)
        self.assertIn('looks edible', lines[0])
        self.assertEqual(player.inventory.entries()[0].item.name, 'TROLL meat')

    def test_elf_race_penalty_prevents_edible(self):
        player = _player()
        player.char_race = PlayerRace.ELF
        ctx = _FakeCtx(player, _FakeServer())
        with patch('random.randint', return_value=60):  # 60-25=35, <50
            lines = _monster_food(ctx, _TROLL, has_food=False)
        self.assertIn('reveals nothing', lines[0])
        self.assertEqual(len(player.inventory.entries()), 0)

    def test_elf_roll_below_one_shows_disgust_line(self):
        player = _player()
        player.char_race = PlayerRace.ELF
        ctx = _FakeCtx(player, _FakeServer())
        with patch('random.randint', return_value=1):  # 1-25 = -24, <1
            lines = _monster_food(ctx, _TROLL, has_food=False)
        self.assertEqual(lines[0], 'Your elvish eyes wrinkle in disgust.')

    def test_already_carrying_food_skips_new_discovery(self):
        player = _player()
        ctx = _FakeCtx(player, _FakeServer())
        with patch('random.randint', return_value=100):  # would clear the >=50 bar easily
            lines = _monster_food(ctx, _TROLL, has_food=True)
        self.assertIn('reveals nothing', lines[0])
        self.assertEqual(len(player.inventory.entries()), 0)

    def test_human_no_race_modifier_reaches_edible_above_50(self):
        player = _player()  # default char_race is None -- no modifier applies
        ctx = _FakeCtx(player, _FakeServer())
        with patch('random.randint', return_value=51):
            lines = _monster_food(ctx, _TROLL, has_food=False)
        self.assertIn('looks edible', lines[0])


class TestMonsterDiseaseCheck(unittest.TestCase):
    def test_low_roll_causes_disease(self):
        player = _player()
        with patch('random.randint', return_value=1):  # <=2% chance
            lines = _monster_disease_check(player)
        self.assertEqual(lines, ['Yuk! You picked up a disease from the thing!'])
        self.assertTrue(player.diseased)

    def test_high_roll_no_disease(self):
        player = _player()
        with patch('random.randint', return_value=50):
            lines = _monster_disease_check(player)
        self.assertEqual(lines, [])
        self.assertFalse(getattr(player, 'diseased', False))


class TestExamineMonster(unittest.TestCase):
    """SPUR.MISC3.S exam.mon's dispatch chain, end to end."""

    def test_live_monster_refuses_examination(self):
        player = _player()
        player.dead_monsters = []  # TROLL not killed yet
        ctx = _ctx_with_monster(player)
        lines = _examine_monster(ctx, _TROLL)
        self.assertEqual(lines, ["TROLL doesn't like being examined!"])

    def test_dead_monster_dwarf_finds_treasure(self):
        player = _player()
        player.dead_monsters = [_TROLL['number']]
        player.char_race = PlayerRace.DWARF
        ctx = _ctx_with_monster(player)
        with patch('random.randint', side_effect=[50, 1, 1]):
            # roll1 (base flavor, unused), dwarf-chance roll (<26 -> hits),
            # treasure tier roll (<=40 -> gold coins)
            lines = _examine_monster(ctx, _TROLL)
        self.assertEqual(lines[0], 'Your dwarvish eyes spot something!')
        self.assertIn('gold coins', lines[1])

    def test_dead_monster_high_roll_finds_food(self):
        player = _player()
        player.dead_monsters = [_TROLL['number']]
        ctx = _ctx_with_monster(player)
        with patch('random.randint', side_effect=[50, 80, 60]):
            # roll1 (base flavor, unused), roll2>70 -> food branch,
            # food's own roll (60, no race modifier) -> edible
            lines = _examine_monster(ctx, _TROLL)
        self.assertIn('looks edible', lines[0])

    def test_dead_monster_frozen_room_flavor(self):
        player = _player()
        player.dead_monsters = [_TROLL['number']]
        ctx = _ctx_with_monster(player, room_flags=['snow'])
        with patch('random.randint', side_effect=[10, 50, 20, 50]):
            # roll1<=40 (frozen flavor kept), roll2<=70 (not food),
            # roll3>15 -> base_msg + disease check (roll4=50 -> no disease)
            lines = _examine_monster(ctx, _TROLL)
        self.assertEqual(lines, ['The TROLL is quite frozen!'])

    def test_dead_monster_dead_awright_flavor_above_40(self):
        player = _player()
        player.dead_monsters = [_TROLL['number']]
        ctx = _ctx_with_monster(player)
        with patch('random.randint', side_effect=[50, 50, 20, 50]):
            lines = _examine_monster(ctx, _TROLL)
        self.assertEqual(lines, ["Yep. It's dead awright.."])

    def test_dead_monster_ugly_flavor_above_70(self):
        player = _player()
        player.dead_monsters = [_TROLL['number']]
        ctx = _ctx_with_monster(player)
        with patch('random.randint', side_effect=[80, 50, 20, 50]):
            lines = _examine_monster(ctx, _TROLL)
        self.assertEqual(lines, ['The TROLL is quite ugly, actually..'])

    def test_dead_monster_disease_from_search(self):
        player = _player()
        player.dead_monsters = [_TROLL['number']]
        ctx = _ctx_with_monster(player)
        with patch('random.randint', side_effect=[50, 50, 20, 1]):
            # roll1/roll2/roll3 land on the base_msg+disease-check path,
            # disease roll of 1 triggers it
            lines = _examine_monster(ctx, _TROLL)
        self.assertEqual(lines[0], "Yep. It's dead awright..")
        self.assertEqual(lines[1], 'Yuk! You picked up a disease from the thing!')
        self.assertTrue(player.diseased)

    def test_dead_monster_falls_through_to_treasure_when_no_branch_taken(self):
        """SPUR has no explicit branch between the final roll check and
        mon.dv -- a low roll with nothing carried falls straight through
        to a treasure find, matched here for authenticity."""
        player = _player()
        player.dead_monsters = [_TROLL['number']]
        ctx = _ctx_with_monster(player)
        with patch('random.randint', side_effect=[50, 50, 10, 1]):
            # roll1 (unused), roll2<=70 (not food), roll3<=15 and no item
            # held -> falls through, then the treasure tier roll (1)
            lines = _examine_monster(ctx, _TROLL)
        self.assertIn('gold coins', lines[0])


class TestExamineCommandMonsterIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_examine_monster_by_name(self):
        player = _player()
        player.dead_monsters = [_TROLL['number']]
        ctx = _ctx_with_monster(player)
        with patch('random.randint', side_effect=[50, 50, 20, 50]):
            await ExamineCommand().execute(ctx, 'troll')
        self.assertEqual(ctx.sent, ["Yep. It's dead awright.."])

    async def test_live_monster_refuses_via_command(self):
        player = _player()
        player.dead_monsters = []
        ctx = _ctx_with_monster(player)
        await ExamineCommand().execute(ctx, 'troll')
        self.assertEqual(ctx.sent, ["TROLL doesn't like being examined!"])

    async def test_examine_all_includes_room_monster(self):
        player = _player()
        player.dead_monsters = [_TROLL['number']]
        ctx = _ctx_with_monster(player)
        with patch('random.randint', side_effect=[50, 50, 20, 50]):
            await ExamineCommand().execute(ctx)
        self.assertIn("Yep. It's dead awright..", ctx.sent)


if __name__ == '__main__':
    unittest.main(verbosity=2)
