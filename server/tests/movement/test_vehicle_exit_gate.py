"""tests/movement/test_vehicle_exit_gate.py

commands/movement.py's vehicle-launch gate (SPUR.MAIN.S's block.s/boat --
see TODO.md's "SPUR boat/vehicle-launch exit flavor text" entry). Only
one real instance exists in the converted game (level 6's Air Lock <->
Outer Space, room 277's VEHICLE_EXIT_WEST flag), but the mechanic itself
is level-agnostic -- these tests exercise it directly against
_check_vehicle_exit_gate()/_room_has_flag() rather than only through
that one room, so the underlying logic is covered regardless of whether
more rooms ever use it.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.movement import _check_vehicle_exit_gate, _room_has_flag
from flags import PlayerFlags
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory


def run(coro):
    return asyncio.run(coro)


def _room(flags):
    room = MagicMock()
    room.flags = flags
    return room


def _player(*, mounted=False, item_ids=()):
    player = MagicMock()
    player.query_flag = MagicMock(side_effect=lambda f: mounted if f == PlayerFlags.MOUNTED else False)
    player.inventory = Inventory()
    for item_id in item_ids:
        player.inventory.add(Item(id_number=item_id, name=f'item{item_id}', category=ItemCategory.ITEM))
    return player


def _ctx(player):
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    return ctx


class TestRoomHasFlag(unittest.TestCase):

    def test_matches_direction_suffix(self):
        room = _room(['vehicle_exit_west'])
        self.assertTrue(_room_has_flag(room, 'vehicle_exit', 'w'))

    def test_no_match_for_other_direction(self):
        room = _room(['vehicle_exit_west'])
        self.assertFalse(_room_has_flag(room, 'vehicle_exit', 'e'))

    def test_up_down_never_match(self):
        room = _room(['vehicle_exit_north', 'vehicle_exit_south',
                       'vehicle_exit_east', 'vehicle_exit_west'])
        self.assertFalse(_room_has_flag(room, 'vehicle_exit', 'u'))
        self.assertFalse(_room_has_flag(room, 'vehicle_exit', 'd'))

    def test_empty_flags(self):
        room = _room([])
        self.assertFalse(_room_has_flag(room, 'vehicle_exit', 'n'))

    def test_none_flags(self):
        room = MagicMock()
        room.flags = None
        self.assertFalse(_room_has_flag(room, 'vehicle_exit', 'n'))


class TestVehicleExitGateNoMarker(unittest.TestCase):

    def test_room_without_marker_always_passes(self):
        room = _room([])
        player = _player()
        ctx = _ctx(player)
        result = run(_check_vehicle_exit_gate(ctx, room, 'w', 1))
        self.assertTrue(result)
        ctx.send.assert_not_awaited()


class TestVehicleExitGateDinghy(unittest.TestCase):
    """Levels 1-5 require the inflatable dinghy (#74)."""

    def test_blocked_without_dinghy(self):
        room = _room(['vehicle_exit_west'])
        player = _player()
        ctx = _ctx(player)
        result = run(_check_vehicle_exit_gate(ctx, room, 'w', 5))
        self.assertFalse(result)
        self.assertIn('Not without a dinghy!', str(ctx.send.call_args))

    def test_allowed_with_dinghy(self):
        room = _room(['vehicle_exit_west'])
        player = _player(item_ids=[74])
        ctx = _ctx(player)
        result = run(_check_vehicle_exit_gate(ctx, room, 'w', 5))
        self.assertTrue(result)
        self.assertIn('You shove the dinghy into the water', str(ctx.send.call_args))

    def test_space_tracker_flavor_not_shown_below_level_6(self):
        room = _room(['vehicle_exit_west'])
        player = _player(item_ids=[74, 138])
        ctx = _ctx(player)
        run(_check_vehicle_exit_gate(ctx, room, 'w', 5))
        self.assertNotIn('space tracker', str(ctx.send.call_args).lower())


class TestVehicleExitGateSpacesuit(unittest.TestCase):
    """Level 6+ requires the spacesuit (#122) instead of the dinghy."""

    def test_blocked_without_spacesuit(self):
        room = _room(['vehicle_exit_west'])
        player = _player(item_ids=[74])  # dinghy alone doesn't count on level 6
        ctx = _ctx(player)
        result = run(_check_vehicle_exit_gate(ctx, room, 'w', 6))
        self.assertFalse(result)
        self.assertIn('Not without a spacesuit!', str(ctx.send.call_args))

    def test_allowed_with_spacesuit(self):
        room = _room(['vehicle_exit_west'])
        player = _player(item_ids=[122])
        ctx = _ctx(player)
        result = run(_check_vehicle_exit_gate(ctx, room, 'w', 6))
        self.assertTrue(result)
        self.assertIn('You put on your spacesuit', str(ctx.send.call_args))

    def test_space_tracker_bonus_flavor_when_carried(self):
        room = _room(['vehicle_exit_west'])
        player = _player(item_ids=[122, 138])
        ctx = _ctx(player)
        run(_check_vehicle_exit_gate(ctx, room, 'w', 6))
        self.assertIn('space tracker powers up', str(ctx.send.call_args).lower())

    def test_no_space_tracker_flavor_when_not_carried(self):
        room = _room(['vehicle_exit_west'])
        player = _player(item_ids=[122])
        ctx = _ctx(player)
        run(_check_vehicle_exit_gate(ctx, room, 'w', 6))
        self.assertIn("don't have a space tracker", str(ctx.send.call_args).lower())


class TestVehicleExitGateMounted(unittest.TestCase):

    def test_mounted_player_must_dismount_first(self):
        room = _room(['vehicle_exit_west'])
        player = _player(mounted=True, item_ids=[122])
        ctx = _ctx(player)
        result = run(_check_vehicle_exit_gate(ctx, room, 'w', 6))
        self.assertFalse(result)
        self.assertIn('dismount', str(ctx.send.call_args).lower())

    def test_dismount_check_happens_before_item_check(self):
        # Mounted AND missing the item -- dismount message wins, not the
        # "Not without a spacesuit!" one, matching SPUR's own check order.
        room = _room(['vehicle_exit_west'])
        player = _player(mounted=True)
        ctx = _ctx(player)
        run(_check_vehicle_exit_gate(ctx, room, 'w', 6))
        sent = str(ctx.send.call_args).lower()
        self.assertIn('dismount', sent)
        self.assertNotIn('spacesuit', sent)


if __name__ == '__main__':
    unittest.main(verbosity=2)
