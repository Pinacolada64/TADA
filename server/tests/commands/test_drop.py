"""tests/test_drop.py

Unit tests for commands/drop.py:
  - _is_water_room   (flag-based and keyword-based detection)
  - _is_well_room    (well shaft detection)
  - _item_sinks      (buoyancy heuristic by category/name)
  - _water_drop_messages (message text and lost flag)
  - DropCommand.execute  (full async flow: dry room, water room, well)

Run with:
    python -m pytest tests/test_drop.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

import sys, types
nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from commands.drop import (
    DropCommand,
    _is_water_room,
    _is_well_room,
    _item_sinks,
    _water_drop_messages,
)
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _Room:
    def __init__(self, name='EAST HALL', desc='', flags=None):
        self.name  = name
        self.desc  = desc
        self.flags = flags or []


class _FakeMap:
    def __init__(self, room):
        self._room = room

    def get(self, room_no):          # called as game_map.rooms.get(n)
        return self._room

    def get_room(self, level, room_no):
        return self._room

    @property
    def rooms(self):
        return self


class _FakeServer:
    def __init__(self, room=None):
        self.game_map  = _FakeMap(room) if room is not None else None
        self.room_items: dict = {}


class _FakeClient:
    def __init__(self, room_no=1):
        self.room = room_no


class _FakeCtx:
    def __init__(self, player, server=None, room_no=1):
        self.player = player
        self.server = server or _FakeServer()
        self.client = _FakeClient(room_no)
        self._sent: list[str] = []
        self._prompt_answer = ''

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        pass

    async def prompt(self, *args, **kwargs):
        return self._prompt_answer

    def sent(self):
        return '\n'.join(self._sent)


def _make_player(inv_capacity=None):
    import unittest.mock as mock
    p = mock.MagicMock()
    p.name = 'Rulan'
    p.inventory = Inventory(capacity=inv_capacity)
    return p


def _item(name, item_id=1, category=None, kind=''):
    return Item(id_number=item_id, name=name,
                category=category or ItemCategory.ITEM, kind=kind)


def _weapon(name, item_id=1):
    return Item(id_number=item_id, name=name, category=ItemCategory.WEAPON)


# ---------------------------------------------------------------------------
# _is_water_room
# ---------------------------------------------------------------------------

class TestIsWaterRoom(unittest.TestCase):

    def test_flag_based_detection(self):
        self.assertTrue(_is_water_room(_Room(flags=['water'])))

    def test_flag_case_sensitive_match(self):
        # flags list stores lowercase strings per RoomFlag enum values
        self.assertFalse(_is_water_room(_Room(flags=['WATER'])))

    def test_name_keyword_rapids(self):
        self.assertTrue(_is_water_room(_Room(name='UNDERGROUND RAPIDS')))

    def test_name_keyword_pool(self):
        self.assertTrue(_is_water_room(_Room(name='UNDERGROUND POOL')))

    def test_name_keyword_stream(self):
        self.assertTrue(_is_water_room(_Room(name='UNDERGROUND STREAM')))

    def test_name_keyword_lake(self):
        self.assertTrue(_is_water_room(_Room(name='HIDDEN LAKE')))

    def test_name_keyword_river(self):
        self.assertTrue(_is_water_room(_Room(name='DARK RIVER')))

    def test_name_keyword_ocean(self):
        self.assertTrue(_is_water_room(_Room(name='OCEAN FLOOR')))

    def test_desc_keyword_fallback(self):
        # name is dry but desc mentions a swamp
        self.assertTrue(_is_water_room(
            _Room(name='MURKY AREA', desc='A thick swamp surrounds you.')))

    def test_dry_room_not_water(self):
        self.assertFalse(_is_water_room(_Room(name='EAST HALL')))

    def test_well_room_not_caught_by_water_keywords(self):
        # WELL rooms are handled separately; _is_water_room should NOT match them
        # (they don't contain any of the _WATER_NAME_KEYWORDS)
        self.assertFalse(_is_water_room(_Room(name='CAVERN WELL')))
        self.assertFalse(_is_water_room(_Room(name='WELL ROOM')))

    def test_underground_alone_not_water(self):
        # 'UNDERGROUND' was intentionally removed from the keyword list
        self.assertFalse(_is_water_room(_Room(name='UNDERGROUND PASSAGE')))


# ---------------------------------------------------------------------------
# _is_well_room
# ---------------------------------------------------------------------------

class TestIsWellRoom(unittest.TestCase):

    def test_cavern_well(self):
        self.assertTrue(_is_well_room(_Room(name='CAVERN WELL')))

    def test_well_room(self):
        self.assertTrue(_is_well_room(_Room(name='WELL ROOM')))

    def test_ordinary_room_not_well(self):
        self.assertFalse(_is_well_room(_Room(name='EAST HALL')))

    def test_underground_pool_not_well(self):
        self.assertFalse(_is_well_room(_Room(name='UNDERGROUND POOL')))


# ---------------------------------------------------------------------------
# _item_sinks
# ---------------------------------------------------------------------------

class TestItemSinks(unittest.TestCase):

    # Metal weapons sink
    def test_sword_sinks(self):
        self.assertTrue(_item_sinks(_weapon('LONG SWORD')))

    def test_axe_sinks(self):
        self.assertTrue(_item_sinks(_weapon('BATTLE AXE')))

    def test_dagger_sinks(self):
        self.assertTrue(_item_sinks(_weapon('DAGGER')))

    # Wooden weapons float
    def test_bow_floats(self):
        self.assertFalse(_item_sinks(_weapon('SHORT BOW')))

    def test_crossbow_floats(self):
        self.assertFalse(_item_sinks(_weapon('CROSSBOW')))

    def test_wood_staff_floats(self):
        self.assertFalse(_item_sinks(_weapon('WOOD STAFF')))

    # Named heavy items sink
    def test_shield_sinks(self):
        self.assertTrue(_item_sinks(_item('IRON SHIELD')))

    def test_gold_coin_sinks(self):
        self.assertTrue(_item_sinks(_item('GOLD COIN')))

    def test_grenade_sinks(self):
        self.assertTrue(_item_sinks(_item('GRENADE')))

    def test_stone_sinks(self):
        self.assertTrue(_item_sinks(_item('STONE')))

    def test_bullet_sinks(self):
        self.assertTrue(_item_sinks(_item('BULLET')))

    def test_gauntlets_sink(self):
        self.assertTrue(_item_sinks(_item('GAUNTLETS')))

    # Light / natural items float
    def test_ration_floats(self):
        self.assertFalse(_item_sinks(_item('RATION', kind='food')))

    def test_book_floats(self):
        self.assertFalse(_item_sinks(_item('BOOK OF LORE')))

    def test_arrow_floats(self):
        self.assertFalse(_item_sinks(_item('ARROW')))

    def test_dart_floats(self):
        self.assertFalse(_item_sinks(_item('DART')))

    def test_compass_floats(self):
        self.assertFalse(_item_sinks(_item('COMPASS')))

    def test_torch_floats(self):
        self.assertFalse(_item_sinks(_item('TORCH')))


# ---------------------------------------------------------------------------
# _water_drop_messages
# ---------------------------------------------------------------------------

class TestWaterDropMessages(unittest.TestCase):

    def _open_water(self):
        return _Room(name='UNDERGROUND POOL')

    def _well(self):
        return _Room(name='CAVERN WELL')

    def test_sinking_item_is_lost(self):
        _, lost = _water_drop_messages(_weapon('LONG SWORD'), self._open_water())
        self.assertTrue(lost)

    def test_sinking_message_mentions_sinks(self):
        msgs, _ = _water_drop_messages(_weapon('LONG SWORD'), self._open_water())
        self.assertTrue(any('sink' in m.lower() for m in msgs))

    def test_floating_item_not_lost(self):
        _, lost = _water_drop_messages(_weapon('SHORT BOW'), self._open_water())
        self.assertFalse(lost)

    def test_floating_message_mentions_floats(self):
        msgs, _ = _water_drop_messages(_weapon('SHORT BOW'), self._open_water())
        self.assertTrue(any('float' in m.lower() for m in msgs))

    def test_well_always_loses_item(self):
        for item in [_weapon('SHORT BOW'), _weapon('LONG SWORD'), _item('RATION')]:
            with self.subTest(item=item.name):
                _, lost = _water_drop_messages(item, self._well())
                self.assertTrue(lost, f'{item.name} should be lost in a well')

    def test_well_message_mentions_well(self):
        msgs, _ = _water_drop_messages(_item('RATION'), self._well())
        combined = ' '.join(msgs).lower()
        self.assertTrue('well' in combined or 'splash' in combined)


# ---------------------------------------------------------------------------
# DropCommand.execute — full async integration
# ---------------------------------------------------------------------------

class TestDropCommand(unittest.IsolatedAsyncioTestCase):

    def _setup(self, room=None, room_no=1):
        player = _make_player()
        server = _FakeServer(room=room)
        ctx    = _FakeCtx(player, server=server, room_no=room_no)
        cmd    = DropCommand()
        return player, server, ctx, cmd

    # --- dry room ---

    async def test_dry_room_drop_by_name(self):
        player, server, ctx, cmd = self._setup()
        sword = _weapon('LONG SWORD', item_id=1)
        player.inventory.add(sword)
        await cmd.execute(ctx, 'sword')
        self.assertIn('You drop', ctx.sent())
        self.assertEqual(len(player.inventory.entries()), 0)

    async def test_dry_room_item_placed_in_room_items(self):
        player, server, ctx, cmd = self._setup(room_no=5)
        sword = _weapon('LONG SWORD', item_id=1)
        player.inventory.add(sword)
        await cmd.execute(ctx, 'sword')
        self.assertIn(5, server.room_items)
        self.assertEqual(len(server.room_items[5]), 1)

    async def test_dry_room_no_inventory(self):
        player, server, ctx, cmd = self._setup()
        player.inventory = None
        await cmd.execute(ctx)
        self.assertIn('nothing', ctx.sent().lower())

    async def test_dry_room_empty_inventory(self):
        player, server, ctx, cmd = self._setup()
        await cmd.execute(ctx)
        self.assertIn('nothing', ctx.sent().lower())

    async def test_dry_room_no_match(self):
        player, server, ctx, cmd = self._setup()
        player.inventory.add(_item('RATION'))
        await cmd.execute(ctx, 'sword')
        self.assertIn('not carrying anything matching', ctx.sent().lower())

    async def test_dry_room_interactive_selection(self):
        player, server, ctx, cmd = self._setup(room_no=3)
        player.inventory.add(_item('RATION', item_id=1))
        ctx._prompt_answer = '1'
        await cmd.execute(ctx)
        self.assertEqual(len(player.inventory.entries()), 0)
        self.assertIn(3, server.room_items)

    async def test_dry_room_cancel_interactive(self):
        player, server, ctx, cmd = self._setup()
        player.inventory.add(_item('RATION', item_id=1))
        ctx._prompt_answer = ''
        await cmd.execute(ctx)
        self.assertEqual(len(player.inventory.entries()), 1)

    # --- water room: sinking ---

    async def test_water_room_metal_weapon_sinks(self):
        room = _Room(name='UNDERGROUND POOL')
        player, server, ctx, cmd = self._setup(room=room, room_no=2)
        sword = _weapon('LONG SWORD', item_id=1)
        player.inventory.add(sword)
        await cmd.execute(ctx, 'sword')
        # removed from inventory
        self.assertEqual(len(player.inventory.entries()), 0)
        # NOT placed in room_items (it sank)
        self.assertEqual(len(server.room_items.get(2, [])), 0)
        self.assertIn('sink', ctx.sent().lower())

    async def test_water_room_flag_detection(self):
        room = _Room(name='POOL ROOM', flags=['water'])
        player, server, ctx, cmd = self._setup(room=room, room_no=7)
        sword = _weapon('LONG SWORD', item_id=2)
        player.inventory.add(sword)
        await cmd.execute(ctx, 'sword')
        self.assertEqual(len(server.room_items.get(7, [])), 0)

    # --- water room: floating ---

    async def test_water_room_bow_floats(self):
        room = _Room(name='UNDERGROUND RAPIDS')
        player, server, ctx, cmd = self._setup(room=room, room_no=3)
        bow = _weapon('SHORT BOW', item_id=2)
        player.inventory.add(bow)
        await cmd.execute(ctx, 'bow')
        # removed from inventory
        self.assertEqual(len(player.inventory.entries()), 0)
        # placed in room_items (it floats)
        self.assertEqual(len(server.room_items.get(3, [])), 1)
        self.assertIn('float', ctx.sent().lower())

    async def test_water_room_food_floats(self):
        room = _Room(name='UNDERGROUND STREAM')
        player, server, ctx, cmd = self._setup(room=room, room_no=4)
        food = _item('RATION', item_id=3, kind='food')
        player.inventory.add(food)
        await cmd.execute(ctx, 'ration')
        self.assertEqual(len(server.room_items.get(4, [])), 1)
        self.assertIn('float', ctx.sent().lower())

    # --- well room ---

    async def test_well_room_bow_still_lost(self):
        room = _Room(name='CAVERN WELL')
        player, server, ctx, cmd = self._setup(room=room, room_no=27)
        bow = _weapon('SHORT BOW', item_id=2)
        player.inventory.add(bow)
        await cmd.execute(ctx, 'bow')
        self.assertEqual(len(player.inventory.entries()), 0)
        self.assertEqual(len(server.room_items.get(27, [])), 0,
                         'bow should be lost in the well even though it floats')

    async def test_well_room_message(self):
        room = _Room(name='WELL ROOM')
        player, server, ctx, cmd = self._setup(room=room, room_no=97)
        ration = _item('RATION', item_id=3)
        player.inventory.add(ration)
        await cmd.execute(ctx, 'ration')
        combined = ctx.sent().lower()
        self.assertTrue('well' in combined or 'splash' in combined)

    # --- Sugar Cube / wild horse (SPUR.MISC.S "d.sugar") ---

    def _sugar_cube(self, item_id=4):
        from items import Rations
        return Rations(number=16, name='CUBE OF SUGAR', kind='food', price=1)

    async def test_sugar_cube_not_grassy_does_no_good(self):
        room = _Room(name='EAST HALL', flags=[])
        player, server, ctx, cmd = self._setup(room=room)
        player.inventory.add(self._sugar_cube())
        await cmd.execute(ctx, 'sugar')
        self.assertIn('does no good', ctx.sent().lower())
        self.assertEqual(len(player.inventory.entries()), 0, 'cube is consumed either way')
        self.assertEqual(server.room_items, {}, 'never placed on the ground')

    async def test_sugar_cube_grassy_failure_roll(self):
        room = _Room(name='TINY MEADOW', flags=['grassy'])
        player, server, ctx, cmd = self._setup(room=room)
        player.inventory.add(self._sugar_cube())
        with patch('wild_horse_events.random.randint', return_value=1):   # <=50 -> fails
            await cmd.execute(ctx, 'sugar')
        self.assertIn('nothing', ctx.sent().lower())
        self.assertEqual(room.monster if hasattr(room, 'monster') else 0, 0)

    async def test_sugar_cube_grassy_success_places_horse(self):
        room = _Room(name='TINY MEADOW', flags=['grassy'])
        room.monster = 0
        player, server, ctx, cmd = self._setup(room=room)
        player.inventory.add(self._sugar_cube())
        with patch('wild_horse_events.random.randint', return_value=100):   # >50 -> succeeds
            await cmd.execute(ctx, 'sugar')
        self.assertIn('gallops up', ctx.sent().lower())
        self.assertEqual(room.monster, 136)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main(verbosity=2)
