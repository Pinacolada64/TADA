"""tests/test_hidden_exit_reveal.py

Unit tests for CombatSession._reveal_hidden_exit(): SPUR.MISC.S:419-420,
right after "gosub rec.ammo" in the dead-monster routine (p.a3/p.a4/
no.robot), unconditionally prints "A search reveals a secret hole,
east/west!" for any non-Dwarf kill in a room flagged
hidden_exit_east/hidden_exit_west, and is not otherwise gated (no monster
type check, no "only once" state).

Run with:
    python -m pytest tests/test_hidden_exit_reveal.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from combat.engine import CombatSession
from base_classes import Map, Room


class _FakePlayer:
    def __init__(self):
        self.name = 'Rulan'
        self.hit_points = 30
        self.unsaved_changes = False
        self.stats = {}
        self.shield = 0
        self.armor = 0
        self.map_level = 1


class _FakeClient:
    room = 89


class _FakeServer:
    def __init__(self, game_map=None):
        self.clients = {}
        self.active_combats = {}
        self.game_map = game_map


class _FakeCtx:
    def __init__(self, player, game_map=None):
        self.player = player
        self.client = _FakeClient()
        self.server = _FakeServer(game_map)
        self._sent: list[str] = []

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        pass

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _map_with_flags(flags):
    m = Map()
    room = Room(number=89, name='TELEPORT ROOM', desc='', flags=flags)
    m.levels[1] = {89: room}
    m.rooms = m.levels[1]
    return m


def _map_with_confirmed_east():
    m = Map()
    room = Room(number=89, name='TELEPORT ROOM', desc='', flags=[],
                hidden_exit_east={'room': 41, 'level': 5})
    m.levels[1] = {89: room}
    m.rooms = m.levels[1]
    return m


class TestRevealHiddenExit(unittest.IsolatedAsyncioTestCase):
    async def test_reveals_east(self):
        player = _FakePlayer()
        ctx = _FakeCtx(player, game_map=_map_with_flags(['hidden_exit_east']))
        session = CombatSession({'name': 'GOBLIN', 'strength': 0, 'flags': {}}, room_no=89)
        with patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch('combat.engine._record_kill'), \
             patch('combat.engine._give_silver'), \
             patch('combat.rewards.gold_from_monster', return_value=0):
            await session._monster_dies(ctx)
        self.assertIn('A search reveals a secret hole, east!', ctx.sent())

    async def test_reveals_east_via_confirmed_field(self):
        # A room with the confirmed hidden_exit_east field and no legacy
        # flag string (e.g. level_1.json room 89 post-migration) still
        # triggers the reveal.
        player = _FakePlayer()
        ctx = _FakeCtx(player, game_map=_map_with_confirmed_east())
        session = CombatSession({'name': 'GOBLIN', 'strength': 0, 'flags': {}}, room_no=89)
        with patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch('combat.engine._record_kill'), \
             patch('combat.engine._give_silver'), \
             patch('combat.rewards.gold_from_monster', return_value=0):
            await session._monster_dies(ctx)
        self.assertIn('A search reveals a secret hole, east!', ctx.sent())

    async def test_reveals_west(self):
        player = _FakePlayer()
        ctx = _FakeCtx(player, game_map=_map_with_flags(['hidden_exit_west']))
        session = CombatSession({'name': 'GOBLIN', 'strength': 0, 'flags': {}}, room_no=89)
        with patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch('combat.engine._record_kill'), \
             patch('combat.engine._give_silver'), \
             patch('combat.rewards.gold_from_monster', return_value=0):
            await session._monster_dies(ctx)
        self.assertIn('A search reveals a secret hole, west!', ctx.sent())

    async def test_no_reveal_without_flag(self):
        player = _FakePlayer()
        ctx = _FakeCtx(player, game_map=_map_with_flags([]))
        session = CombatSession({'name': 'GOBLIN', 'strength': 0, 'flags': {}}, room_no=89)
        with patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch('combat.engine._record_kill'), \
             patch('combat.engine._give_silver'), \
             patch('combat.rewards.gold_from_monster', return_value=0):
            await session._monster_dies(ctx)
        self.assertNotIn('secret hole', ctx.sent())

    async def test_no_game_map_is_safe(self):
        player = _FakePlayer()
        ctx = _FakeCtx(player, game_map=None)
        session = CombatSession({'name': 'GOBLIN', 'strength': 0, 'flags': {}}, room_no=89)
        with patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch('combat.engine._record_kill'), \
             patch('combat.engine._give_silver'), \
             patch('combat.rewards.gold_from_monster', return_value=0):
            await session._monster_dies(ctx)  # should not raise
        self.assertNotIn('secret hole', ctx.sent())


if __name__ == '__main__':
    unittest.main()
