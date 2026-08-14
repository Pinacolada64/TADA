"""tests/horses/test_horse_bolt.py

Unit tests for ally_events/horse_bolt.py -- the TADA-only enhancement that
replaces a mount's old chance of permanently deserting (see
tests/combat/test_tactical_ambush.py, tests/combat/test_thug_attack.py's
MOUNT exclusions) with a "bolts a few rooms away, re-catchable" mechanic.

Coverage:
  - maybe_bolt_mount(): no-op when not mounted / no mount / roll misses;
    on a hit, dismounts the player, sets AllyStatus.BOLTED with a
    same-level destination room, and sends flavor text
  - _walk_random_rooms(): follows exits N hops, stops early at a dead end
  - try_catch_bolted_mount(): reattaches a BOLTED mount only when the
    player is standing in its bolt_room_no/bolt_map_level; None otherwise
  - has_bolted_mount(): reflects BOLTED status regardless of location
  - commands/mount.py integration: MOUNT catches a bolted mount standing
    in the same room and climbs on; refuses with a distinct message when
    the bolted mount is elsewhere
  - party.py round-trips bolt_room_no/bolt_map_level through to_json/from_json

Run with:
    python -m pytest tests/horses/test_horse_bolt.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ally_events.horse_bolt import (
    _bolt_denominator,
    _walk_random_rooms,
    bolt_thrown_mount,
    has_bolted_mount,
    maybe_bolt_mount,
    try_catch_bolted_mount,
)
from bar.ally_data import Ally, AllyFlags, AllyStatus
from base_classes import Map, Room
from commands.mount import MountCommand
from flags import PlayerFlags
from party import Party
from player import Player


def _make_mount(name='SHADOW') -> Ally:
    a = Ally(name=name, gender='m', strength=20, to_hit=0, flags=[AllyFlags.MOUNT])
    a.status = AllyStatus.SERVANT
    return a


def make_player(*, with_mount: bool = True) -> Player:
    p = Player(name='Tester')
    if with_mount:
        p.party.members.append(_make_mount())
    return p


def make_map(*, water_room: int | None = None) -> Map:
    """A -> B -> C -> D, one-way chain, each room's only exit is 'e'.

    water_room, if given, flags that room number 'water' so
    _walk_random_rooms() must stop at the room just before it.
    """
    m = Map()
    room_a = Room(number=1, name='A', desc='.', exits={'east': 2})
    room_b = Room(number=2, name='B', desc='.', exits={'east': 3})
    room_c = Room(number=3, name='C', desc='.', exits={'east': 4})
    room_d = Room(number=4, name='D', desc='.', exits={})  # dead end
    rooms = {1: room_a, 2: room_b, 3: room_c, 4: room_d}
    if water_room is not None:
        rooms[water_room].flags = ['water']
    m.levels[1] = rooms
    m.rooms = rooms
    return m


def make_ctx(player, *, room_no: int = 1, game_map: Map | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.player = player
    ctx.client.room = room_no
    ctx.server.game_map = game_map if game_map is not None else make_map()
    ctx.send = AsyncMock()
    return ctx


def _sent(ctx) -> str:
    parts = []
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


class TestWalkRandomRooms(unittest.TestCase):
    def test_walks_the_requested_number_of_hops(self):
        m = make_map()
        with patch('random.choice', side_effect=lambda choices: choices[0]):
            dest, hit_water = _walk_random_rooms(m, 1, 1, 2)
        self.assertEqual(dest, 3)  # 1 -> 2 -> 3
        self.assertFalse(hit_water)

    def test_stops_early_at_a_dead_end(self):
        m = make_map()
        with patch('random.choice', side_effect=lambda choices: choices[0]):
            dest, hit_water = _walk_random_rooms(m, 1, 1, 10)
        self.assertEqual(dest, 4)  # 1->2->3->4, then no exits left
        self.assertFalse(hit_water)

    def test_stops_at_the_edge_of_a_water_room_instead_of_entering_it(self):
        m = make_map(water_room=3)  # C is water
        with patch('random.choice', side_effect=lambda choices: choices[0]):
            dest, hit_water = _walk_random_rooms(m, 1, 1, 10)
        self.assertEqual(dest, 2)  # stops at B, never steps into C
        self.assertTrue(hit_water)


class TestMaybeBoltMount(unittest.IsolatedAsyncioTestCase):
    async def test_noop_when_not_mounted(self):
        player = make_player()
        ctx = make_ctx(player)
        bolted = await maybe_bolt_mount(ctx)
        self.assertFalse(bolted)
        self.assertEqual(player.party[0].status, AllyStatus.SERVANT)

    async def test_noop_when_no_mount_ally(self):
        player = make_player(with_mount=False)
        player.set_flag(PlayerFlags.MOUNTED)
        ctx = make_ctx(player)
        bolted = await maybe_bolt_mount(ctx)
        self.assertFalse(bolted)

    async def test_noop_when_roll_misses(self):
        player = make_player()
        player.set_flag(PlayerFlags.MOUNTED)
        ctx = make_ctx(player)
        with patch('random.randint', return_value=1):  # != 5, misses
            bolted = await maybe_bolt_mount(ctx)
        self.assertFalse(bolted)
        self.assertTrue(player.query_flag(PlayerFlags.MOUNTED))
        self.assertEqual(player.party[0].status, AllyStatus.SERVANT)

    async def test_bolts_on_a_hit(self):
        player = make_player()
        player.set_flag(PlayerFlags.MOUNTED)
        ctx = make_ctx(player, room_no=1)
        mount = player.party[0]
        with patch('random.randint', return_value=5), \
             patch('random.choice', side_effect=lambda choices: choices[0]):
            bolted = await maybe_bolt_mount(ctx)
        self.assertTrue(bolted)
        self.assertFalse(player.query_flag(PlayerFlags.MOUNTED))
        self.assertEqual(mount.status, AllyStatus.BOLTED)
        self.assertEqual(mount.bolt_map_level, 1)
        self.assertIsNotNone(mount.bolt_room_no)
        self.assertNotEqual(mount.bolt_room_no, 1)  # actually moved
        self.assertIn('gallops off', _sent(ctx).lower())


class TestBoltDenominator(unittest.TestCase):
    def test_untrained_mount_uses_base_denominator(self):
        mount = _make_mount()
        self.assertEqual(_bolt_denominator(mount, 10), 10)

    def test_combat_trained_mount_halves_the_odds(self):
        mount = _make_mount()
        mount.flags.append(AllyFlags.COMBAT_TRAINED)
        self.assertEqual(_bolt_denominator(mount, 10), 20)

    def test_elite_mount_is_immune(self):
        mount = _make_mount()
        mount.flags.append(AllyFlags.ELITE)
        self.assertIsNone(_bolt_denominator(mount, 10))

    def test_elite_and_combat_trained_stays_immune(self):
        mount = _make_mount()
        mount.flags.extend([AllyFlags.COMBAT_TRAINED, AllyFlags.ELITE])
        self.assertIsNone(_bolt_denominator(mount, 10))


class TestMaybeBoltMountTraining(unittest.IsolatedAsyncioTestCase):
    async def test_combat_trained_mount_rolls_against_the_doubled_denominator(self):
        player = make_player()
        player.set_flag(PlayerFlags.MOUNTED)
        player.party[0].flags.append(AllyFlags.COMBAT_TRAINED)
        ctx = make_ctx(player)
        with patch('random.randint') as mock_randint:
            mock_randint.return_value = 5
            await maybe_bolt_mount(ctx)
        mock_randint.assert_called_once_with(1, 20)  # base 10, doubled

    async def test_elite_mount_never_bolts(self):
        player = make_player()
        player.set_flag(PlayerFlags.MOUNTED)
        player.party[0].flags.append(AllyFlags.ELITE)
        ctx = make_ctx(player)
        with patch('random.randint', return_value=5):
            bolted = await maybe_bolt_mount(ctx)
        self.assertFalse(bolted)
        self.assertTrue(player.query_flag(PlayerFlags.MOUNTED))


class TestBoltThrownMountTraining(unittest.IsolatedAsyncioTestCase):
    async def test_elite_mount_does_not_bolt_after_being_thrown(self):
        player = make_player()
        mount = player.party[0]
        mount.flags.append(AllyFlags.ELITE)
        ctx = make_ctx(player)
        with patch('random.randint', return_value=1):
            bolted = await bolt_thrown_mount(ctx, mount)
        self.assertFalse(bolted)
        self.assertEqual(mount.status, AllyStatus.SERVANT)

    async def test_combat_trained_mount_rolls_against_the_doubled_denominator(self):
        player = make_player()
        mount = player.party[0]
        mount.flags.append(AllyFlags.COMBAT_TRAINED)
        ctx = make_ctx(player)
        with patch('random.randint') as mock_randint:
            mock_randint.return_value = 1
            await bolt_thrown_mount(ctx, mount)
        mock_randint.assert_called_once_with(1, 4)  # base 2, doubled


class TestTryCatchBoltedMount(unittest.IsolatedAsyncioTestCase):
    async def test_none_when_no_bolted_mount(self):
        player = make_player()
        ctx = make_ctx(player)
        caught = await try_catch_bolted_mount(ctx)
        self.assertIsNone(caught)

    async def test_none_when_bolted_elsewhere(self):
        player = make_player()
        mount = player.party[0]
        mount.status = AllyStatus.BOLTED
        mount.bolt_map_level = 1
        mount.bolt_room_no = 3
        ctx = make_ctx(player, room_no=1)  # not where the horse is
        caught = await try_catch_bolted_mount(ctx)
        self.assertIsNone(caught)
        self.assertEqual(mount.status, AllyStatus.BOLTED)

    async def test_catches_when_in_the_right_room(self):
        player = make_player()
        mount = player.party[0]
        mount.status = AllyStatus.BOLTED
        mount.bolt_map_level = 1
        mount.bolt_room_no = 3
        ctx = make_ctx(player, room_no=3)
        caught = await try_catch_bolted_mount(ctx)
        self.assertIs(caught, mount)
        self.assertEqual(mount.status, AllyStatus.SERVANT)
        self.assertIsNone(mount.bolt_room_no)
        self.assertIsNone(mount.bolt_map_level)
        self.assertIn('catch up', _sent(ctx).lower())

    async def test_catch_message_mentions_water_edge_when_applicable(self):
        player = make_player()
        mount = player.party[0]
        mount.status = AllyStatus.BOLTED
        mount.bolt_map_level = 1
        mount.bolt_room_no = 3
        mount.bolt_at_water = True
        ctx = make_ctx(player, room_no=3)
        caught = await try_catch_bolted_mount(ctx)
        self.assertIs(caught, mount)
        self.assertFalse(mount.bolt_at_water)
        self.assertIn("water's edge", _sent(ctx))


class TestHasBoltedMount(unittest.TestCase):
    def test_false_normally(self):
        player = make_player()
        self.assertFalse(has_bolted_mount(player))

    def test_true_once_bolted(self):
        player = make_player()
        player.party[0].status = AllyStatus.BOLTED
        self.assertTrue(has_bolted_mount(player))


class TestMountCommandCatchesBoltedMount(unittest.IsolatedAsyncioTestCase):
    async def test_mount_catches_and_rides_a_bolted_mount_in_room(self):
        player = make_player()
        mount = player.party[0]
        mount.status = AllyStatus.BOLTED
        mount.bolt_map_level = 1
        mount.bolt_room_no = 3
        ctx = make_ctx(player, room_no=3)
        res = await MountCommand().execute(ctx)
        self.assertTrue(res.success)
        self.assertTrue(player.query_flag(PlayerFlags.MOUNTED))
        self.assertEqual(mount.status, AllyStatus.SERVANT)

    async def test_mount_refuses_with_distinct_message_when_bolted_elsewhere(self):
        player = make_player()
        mount = player.party[0]
        mount.status = AllyStatus.BOLTED
        mount.bolt_map_level = 1
        mount.bolt_room_no = 3
        ctx = make_ctx(player, room_no=1)
        res = await MountCommand().execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'mount_bolted')
        self.assertIn("isn't anywhere nearby", _sent(ctx))


class TestPartyRoundTrip(unittest.TestCase):
    def test_bolt_fields_round_trip_through_json(self):
        mount = _make_mount()
        mount.status = AllyStatus.BOLTED
        mount.bolt_room_no = 42
        mount.bolt_map_level = 3
        mount.bolt_at_water = True
        party = Party([mount])
        data = party.to_json()
        restored = Party.from_json(data)
        restored_mount = restored[0]
        self.assertEqual(restored_mount.status, AllyStatus.BOLTED)
        self.assertEqual(restored_mount.bolt_room_no, 42)
        self.assertEqual(restored_mount.bolt_map_level, 3)
        self.assertTrue(restored_mount.bolt_at_water)


if __name__ == '__main__':
    unittest.main()
