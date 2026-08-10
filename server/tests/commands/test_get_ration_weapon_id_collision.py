"""tests/commands/test_get_ration_weapon_id_collision.py

Regression: id_number is only unique *within* its own category
(weapons/items/rations each number independently -- see items.py:364).
Every special-id check in commands/get.py's _pick_up() (Gollum's ring,
Tut's Treasure, anti-hoarding, fireplace, obelisk, booby trap, Pandora's
Box, gold rose, fireball, staff) originally compared item_id alone with
no category guard, so real objects.json/weapons.json ids collided with
unrelated rations.json/weapons.json entries sharing the same number:

  - ration #39 TOMATOES        vs weapon #39 SMALL FIREBALL
  - ration #72 STANDARD RATIONS vs object #72 funny doll (booby trap)
  - ration #81 SALT LICK        vs object #81 fireplace (USE-only block)
  - ration #41 BROOK WATER      vs object #41 gold rose (poison)
  - weapon #41 STORM DAGGER     vs object #41 gold rose (poison)
  - ration #67 DEAD BUG         vs object #67 ring (Gollum guard)
  - object #3 steel armor       vs weapon #3 WOOD STAFF (anti-hoarding
    block + false "enhances spellcasting" reminder)

Run with:
    python -m pytest tests/commands/test_get_ration_weapon_id_collision.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from base_classes import PlayerClass
from commands.get import GetCommand, _room_available_items


def _make_ctx(*, items=(), weapons=(), rations=(),
              room_item=0, room_weapon=0, room_food=0, room_monster=0,
              monsters=()):
    server = MagicMock()
    server.items = list(items)
    server.weapons = list(weapons)
    server.rations = list(rations)
    server.monsters = list(monsters)
    server.room_items = {}

    room = MagicMock()
    room.item = room_item
    room.weapon = room_weapon
    room.food = room_food
    room.monster = room_monster
    server.game_map.get_room.return_value = room

    player = MagicMock()
    player.ration_history = []
    player.item_history = []
    player.map_level = 1
    player.char_class = PlayerClass.FIGHTER
    player.hit_points = 20
    player.dead_monsters = []
    player.charmed_monsters = []

    ctx = MagicMock()
    ctx.server = server
    ctx.player = player
    ctx.client.room = 1
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


def _sent_lines(ctx):
    lines = []
    for call in ctx.send.await_args_list:
        arg = call.args[0]
        if isinstance(arg, (list, tuple)):
            lines.extend(str(x) for x in arg)
        else:
            lines.append(str(arg))
    return lines


def _padded(entries: list[dict], target_number: int, name: str, **fields) -> list[dict]:
    """Build a 1-indexed list where element `target_number` is the real
    catalog entry, matching _room_available_items()'s id_number=idx+1
    fallback (rations.json/weapons.json dicts carry "number" but never
    "id_number")."""
    out = [{'number': i + 1, 'name': f'FILLER{i}', 'price': 1, **entries}
           for i in range(target_number - 1)]
    out.append({'number': target_number, 'name': name, **fields})
    return out


class TestRationWeaponIdCollision(unittest.TestCase):

    def _pick_up_first(self, ctx):
        name, entry, remove_fn = _room_available_items(ctx)[0]
        inventory = MagicMock()
        inventory.is_full.return_value = False
        inventory.find.return_value = []
        cmd = GetCommand()
        asyncio.run(cmd._pick_up(ctx, inventory, name, entry, remove_fn))
        return _sent_lines(ctx)

    def test_getting_tomatoes_does_not_trigger_fireball_burn(self):
        rations = _padded({'kind': 'food'}, 39, 'TOMATOES', kind='food', price=5)
        ctx = _make_ctx(rations=rations, room_food=39)
        sent = self._pick_up_first(ctx)
        self.assertFalse(any('burn your fingers' in line for line in sent),
                          f'unexpected fireball burn message in: {sent}')
        self.assertEqual(ctx.player.hit_points, 20)

    def test_getting_standard_rations_does_not_explode_as_booby_trap(self):
        rations = _padded({'kind': 'food'}, 72, 'STANDARD RATIONS', kind='food', price=5)
        ctx = _make_ctx(rations=rations, room_food=72)
        sent = self._pick_up_first(ctx)
        self.assertFalse(any('booby trapped' in line for line in sent),
                          f'unexpected booby-trap explosion in: {sent}')
        self.assertEqual(ctx.player.hit_points, 20)

    def test_getting_salt_lick_does_not_block_as_use_only_fireplace(self):
        rations = _padded({'kind': 'food'}, 81, 'SALT LICK', kind='food', price=5)
        ctx = _make_ctx(rations=rations, room_food=81)
        sent = self._pick_up_first(ctx)
        self.assertFalse(any('You can only USE this' in line for line in sent),
                          f'unexpected fireplace USE-only block in: {sent}')
        self.assertIn('You pick up SALT LICK.', sent)
        # get.py had no send_room() at all -- bystanders never saw an
        # item picked up off the ground. Ryan's request.
        ctx.send_room.assert_awaited_once()
        self.assertIn('SALT LICK', ctx.send_room.await_args.args[0])

    def test_getting_brook_water_does_not_trigger_gold_rose_poison(self):
        rations = _padded({'kind': 'drink'}, 41, 'BROOK WATER', kind='drink', price=5)
        ctx = _make_ctx(rations=rations, room_food=41)
        sent = self._pick_up_first(ctx)
        self.assertFalse(any('prick your finger' in line for line in sent),
                          f'unexpected gold-rose poison prompt in: {sent}')

    def test_getting_storm_dagger_does_not_trigger_gold_rose_poison(self):
        weapons = _padded({'weapon_class': 'stab'}, 41, 'STORM DAGGER',
                           weapon_class='stab', price=5)
        ctx = _make_ctx(weapons=weapons, room_weapon=41)
        sent = self._pick_up_first(ctx)
        self.assertFalse(any('prick your finger' in line for line in sent),
                          f'unexpected gold-rose poison prompt in: {sent}')

    def test_getting_dead_bug_ration_does_not_trigger_gollum_ring_guard(self):
        from encounters.gollum import MONSTER_NUMBER
        rations = _padded({'kind': 'food'}, 67, 'DEAD BUG', kind='food', price=1)
        monsters = [{'number': MONSTER_NUMBER, 'name': 'Gollum', 'strength': 10}]
        ctx = _make_ctx(rations=rations, room_food=67, room_monster=MONSTER_NUMBER,
                        monsters=monsters)
        sent = self._pick_up_first(ctx)
        self.assertFalse(any('Gollum hisses' in line for line in sent),
                          f'unexpected Gollum ring guard triggered by: {sent}')
        self.assertIn('You pick up DEAD BUG.', sent)

    def test_steel_armor_pickup_not_blocked_by_unrelated_wood_staff_in_inventory(self):
        # Anti-hoarding must key off category too: a WOOD STAFF (weapon #3)
        # already in inventory must not block picking up "steel armor"
        # (object #3, a completely different item) as "you already have it".
        # Uses the real Inventory class -- a MagicMock stand-in would only
        # reflect whatever filtering *this test* imagines find() does,
        # not what the pre-fix call site (no category kwarg) actually got.
        from inventory import Inventory
        from items import Item, ItemCategory

        items = _padded({'type': 'armor'}, 3, 'steel armor', type='armor', price=6)
        ctx = _make_ctx(items=items, room_item=3)

        name, entry, remove_fn = _room_available_items(ctx)[0]
        inventory = Inventory()
        inventory.add(Item(id_number=3, name='WOOD STAFF', category=ItemCategory.WEAPON))

        cmd = GetCommand()
        asyncio.run(cmd._pick_up(ctx, inventory, name, entry, remove_fn))
        sent = _sent_lines(ctx)
        self.assertFalse(any('already have' in line for line in sent),
                          f'unexpected anti-hoarding block in: {sent}')
        self.assertIn('You pick up steel armor.', sent)


if __name__ == '__main__':
    unittest.main(verbosity=2)
