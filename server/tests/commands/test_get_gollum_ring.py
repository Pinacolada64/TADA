"""tests/commands/test_get_gollum_ring.py

Covers encounters/gollum.py + commands/get.py's guard on item #67 "ring"
(monsters.json #71 GOLLUM, level 4 room 17 "Gollum's Cave"): GETting the
ring while Gollum is alive and present refuses the pickup, quotes him, and
starts real combat via combat.enter_combat -- instead of just letting the
ring walk out from under a live guard.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.get import GetCommand
from inventory import Inventory
from player import Player

_GOLLUM = {'number': 71, 'name': 'GOLLUM', 'strength': 12, 'flags': {}}
_RING_ITEM_ID = 67


def _player() -> Player:
    p = Player(name='Frodo')
    p.inventory = Inventory(capacity=10)
    p.item_history = []
    p.ration_history = []
    p.charmed_monsters = []
    return p


class _FakeCtx:
    def __init__(self, player, server):
        self.player = player
        self.server = server
        self.client = MagicMock()
        self.client.room = 17
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def send_room(self, *args, **kwargs):
        pass

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _server_with_gollum(monster=_GOLLUM):
    server = MagicMock()
    # commands/get.py._room_available_items() indexes server.items by
    # room.item - 1 (1-based), so the ring (objects.json #67) has to sit
    # at index 66 -- everything before it is never touched.
    server.items      = [{'number': n, 'name': f'filler {n}'} for n in range(1, _RING_ITEM_ID)] + [
        {'number': _RING_ITEM_ID, 'name': 'ring', 'type': 'misc', 'price': 9}
    ]
    server.weapons    = []
    server.rations    = []
    server.room_items = {}
    server.monsters   = [monster] if monster else []
    room = MagicMock()
    room.item    = _RING_ITEM_ID
    room.weapon  = 0
    room.food    = 0
    room.monster = monster['number'] if monster else 0
    server.game_map.get_room.return_value = room
    return server


class TestGetRingGuardedByGollum(unittest.IsolatedAsyncioTestCase):

    async def test_get_ring_refused_while_gollum_alive(self):
        p = _player()
        ctx = _FakeCtx(p, _server_with_gollum())

        with patch('combat.enter_combat', new=AsyncMock()):
            await GetCommand().execute(ctx, 'ring')

        self.assertIn('You cannot have my precioussssss!', ctx._flat())
        self.assertIn("He won't let you! He attacks!", ctx._flat())

    async def test_get_ring_never_added_to_inventory_while_gollum_alive(self):
        p = _player()
        ctx = _FakeCtx(p, _server_with_gollum())

        with patch('combat.enter_combat', new=AsyncMock()):
            await GetCommand().execute(ctx, 'ring')

        self.assertEqual(p.inventory.entries(), [])

    async def test_get_ring_starts_combat_with_gollum(self):
        p = _player()
        ctx = _FakeCtx(p, _server_with_gollum())

        with patch('combat.enter_combat', new=AsyncMock()) as mock_combat:
            await GetCommand().execute(ctx, 'ring')

        mock_combat.assert_awaited_once()
        self.assertEqual(mock_combat.await_args.args[1]['number'], 71)

    async def test_get_ring_succeeds_once_gollum_is_dead(self):
        dead_gollum = {**_GOLLUM, 'strength': 0}
        p = _player()
        ctx = _FakeCtx(p, _server_with_gollum(dead_gollum))

        await GetCommand().execute(ctx, 'ring')

        self.assertTrue(p.inventory.find(item_id=_RING_ITEM_ID))

    async def test_get_ring_succeeds_once_player_has_killed_gollum(self):
        # combat/engine.py's CombatSession fights on its own dict(monster)
        # copy (enter_combat()), so a kill never actually zeroes the shared
        # monsters.json entry's strength -- it stays at its template value
        # (12) forever. player.dead_monsters is the real per-player "already
        # killed this one" record (_record_kill()), so it -- not the global
        # monster dict's strength -- has to be what gates a re-guard.
        p = _player()
        p.dead_monsters = [71]
        ctx = _FakeCtx(p, _server_with_gollum())

        await GetCommand().execute(ctx, 'ring')

        self.assertTrue(p.inventory.find(item_id=_RING_ITEM_ID))

    async def test_get_ring_succeeds_when_no_monster_in_room(self):
        p = _player()
        ctx = _FakeCtx(p, _server_with_gollum(monster=None))

        await GetCommand().execute(ctx, 'ring')

        self.assertTrue(p.inventory.find(item_id=_RING_ITEM_ID))


if __name__ == '__main__':
    unittest.main(verbosity=2)
