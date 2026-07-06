"""tests/test_zero_damage_message.py

A hit that inflicts 0 damage should read "You strike the TROLL, but
inflict no damage!" (and the bystander/room broadcast equivalent), not
"You strike the TROLL for 0 damage!" -- both for the player's own swing
(CombatSession._narrate_player_swing()) and for an ally's swing
(CombatSession._ally_attacks_round(), the "{name} strikes for N damage!"
message loop).
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from combat.engine import CombatSession
from combat.resolution import AttackResult


class _FakePlayer:
    def __init__(self):
        self.name = 'Rulan'
        self.hit_points = 30
        self.unsaved_changes = False


class _FakeCtx:
    def __init__(self):
        self.player = _FakePlayer()
        self.client = MagicMock(room=1)
        self.server = MagicMock()
        self.send = AsyncMock()
        self.send_room = AsyncMock()

    def sent(self) -> str:
        return '\n'.join(str(c.args[0]) for c in self.send.await_args_list)

    def room_sent(self) -> str:
        return '\n'.join(str(c.args[0]) for c in self.send_room.await_args_list)


class TestPlayerZeroDamageMessage(unittest.IsolatedAsyncioTestCase):
    async def test_zero_damage_hit_message(self):
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        ctx = _FakeCtx()
        result = AttackResult(hit=True, damage=0)
        await session._narrate_player_swing(ctx, result)
        self.assertIn('You strike the TROLL, but inflict no damage!', ctx.sent())
        self.assertNotIn('for 0 damage', ctx.sent())

    async def test_nonzero_damage_message_unchanged(self):
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        ctx = _FakeCtx()
        result = AttackResult(hit=True, damage=5)
        await session._narrate_player_swing(ctx, result)
        self.assertIn('You strike the TROLL for 5 damage!', ctx.sent())

    async def test_zero_damage_bystander_room_broadcast(self):
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        ctx = _FakeCtx()
        result = AttackResult(hit=True, damage=0)
        await session._narrate_player_swing(ctx, result, bystander=True)
        self.assertIn('Rulan strikes the TROLL, but inflicts no damage!', ctx.room_sent())

    async def test_zero_damage_keeps_critical_and_surprise_suffixes(self):
        session = CombatSession({'name': 'TROLL', 'strength': 0, 'flags': {}}, room_no=1)
        ctx = _FakeCtx()
        result = AttackResult(hit=True, damage=0, is_critical=True, is_surprise=True)
        await session._narrate_player_swing(ctx, result)
        sent = ctx.sent()
        self.assertIn('but inflict no damage!', sent)
        self.assertIn('CRITICAL HIT!', sent)
        self.assertIn('(Surprise!)', sent)


if __name__ == '__main__':
    unittest.main()
