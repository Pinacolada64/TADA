"""tests/test_wild_horse_events.py

Unit tests for wild_horse_events.py:
  - try_wandering_horse_encounter (SPUR.MAIN.S "horse" -- per-move ambient
    encounter check, gated on a 'grassy' room, boosted for Rangers/Knights)
  - try_sugar_cube_drop is covered in tests/test_drop.py (it's reached via
    DropCommand, and needs a real inventory/room fixture that file already
    has set up)

Run with:
    python -m pytest tests/test_wild_horse_events.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import sys, types
nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from base_classes import PlayerClass
from wild_horse_events import try_wandering_horse_encounter


class _Room:
    def __init__(self, flags=None, monster=0):
        self.flags = flags or []
        self.monster = monster


class _FakeMap:
    def __init__(self, room):
        self._room = room

    def get_room(self, level, room_no):
        return self._room


class _FakeServer:
    def __init__(self, room):
        self.game_map = _FakeMap(room)


class _FakeClient:
    def __init__(self, room_no=1):
        self.room = room_no


class _FakePlayer:
    def __init__(self, char_class=None):
        self.char_class = char_class
        self.map_level = 1


class _FakeCtx:
    def __init__(self, room, char_class=None):
        self.player = _FakePlayer(char_class=char_class)
        self.client = _FakeClient()
        self.server = _FakeServer(room)
        self._sent: list[str] = []

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    def sent(self) -> str:
        return '\n'.join(self._sent)


class TestWanderingHorseEncounter(unittest.IsolatedAsyncioTestCase):

    async def test_non_grassy_room_is_a_no_op(self):
        room = _Room(flags=[])
        ctx = _FakeCtx(room)
        with patch('wild_horse_events.random.randint', return_value=100):
            await try_wandering_horse_encounter(ctx)
        self.assertEqual(room.monster, 0)
        self.assertEqual(ctx.sent(), '')

    async def test_low_roll_grassy_room_nothing_happens(self):
        room = _Room(flags=['grassy'])
        ctx = _FakeCtx(room)
        with patch('wild_horse_events.random.randint', return_value=50):
            await try_wandering_horse_encounter(ctx)
        self.assertEqual(room.monster, 0)
        self.assertEqual(ctx.sent(), '')

    async def test_roll_above_70_shows_tracks_hint(self):
        room = _Room(flags=['grassy'])
        ctx = _FakeCtx(room)
        with patch('wild_horse_events.random.randint', return_value=80):
            await try_wandering_horse_encounter(ctx)
        self.assertEqual(room.monster, 0, 'not high enough to spawn yet')
        self.assertIn('tracks', ctx.sent().lower())

    async def test_roll_above_93_places_horse_and_shows_tracks(self):
        room = _Room(flags=['grassy'])
        ctx = _FakeCtx(room)
        with patch('wild_horse_events.random.randint', return_value=95):
            await try_wandering_horse_encounter(ctx)
        self.assertEqual(room.monster, 136)
        sent = ctx.sent().lower()
        self.assertIn('tracks', sent, 'both checks are independent, not elif')
        self.assertIn('wild horse', sent)

    async def test_ranger_gets_plus_15_bonus(self):
        room = _Room(flags=['grassy'])
        ctx = _FakeCtx(room, char_class=PlayerClass.RANGER)
        # 80 + 15 = 95 > 93 -> spawns, though a bare 80 would not have
        with patch('wild_horse_events.random.randint', return_value=80):
            await try_wandering_horse_encounter(ctx)
        self.assertEqual(room.monster, 136)

    async def test_knight_gets_plus_10_bonus(self):
        room = _Room(flags=['grassy'])
        ctx = _FakeCtx(room, char_class=PlayerClass.KNIGHT)
        # 84 + 10 = 94 > 93 -> spawns
        with patch('wild_horse_events.random.randint', return_value=84):
            await try_wandering_horse_encounter(ctx)
        self.assertEqual(room.monster, 136)

    async def test_other_classes_get_no_bonus(self):
        room = _Room(flags=['grassy'])
        ctx = _FakeCtx(room, char_class=PlayerClass.FIGHTER)
        with patch('wild_horse_events.random.randint', return_value=94):
            await try_wandering_horse_encounter(ctx)
        # Fighter gets no bonus, so 94 alone still clears the >93 bar
        self.assertEqual(room.monster, 136)

    async def test_fighter_below_threshold_no_bonus_no_spawn(self):
        room = _Room(flags=['grassy'])
        ctx = _FakeCtx(room, char_class=PlayerClass.FIGHTER)
        with patch('wild_horse_events.random.randint', return_value=85):
            await try_wandering_horse_encounter(ctx)
        self.assertEqual(room.monster, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
