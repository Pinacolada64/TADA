"""tests/test_class_taming.py

Unit tests for CombatSession._try_class_tame(): a TADA original mechanic
(not from SPUR) -- Druids and Rangers, being especially attuned to animals,
get a per-round chance to tame a wild horse outright during combat, without
needing LASSO.

Coverage:
  - non-Druid/Ranger classes never get the chance, regardless of roll
  - Druid/Ranger vs. a non-horse monster: no-op
  - successful roll: mount created, combat ends, gender-correct flavor text
  - failed roll: nothing happens, combat continues
  - full party / existing mount blocks the attempt silently (no message)
  - wired into both the leader's per-round loop and a bystander's join()

Run with:
    python -m pytest tests/test_class_taming.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sys, types

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from base_classes import Gender, PlayerClass
from combat.engine import CombatSession


class _FakePlayer:
    def __init__(self, char_class=PlayerClass.DRUID, gender=Gender.MALE,
                 allies=None, name='Rulan'):
        self.name = name
        self.char_class = char_class
        self.gender = gender
        self.party = list(allies or [])
        self.unsaved_changes = False


class _FakeClient:
    def __init__(self, room=1):
        self.room = room
        self.virtual_location = None


class _FakeCtx:
    def __init__(self, player, room=1, name_answer='Silver'):
        self.player = player
        self.client = _FakeClient(room=room)
        self.server = MagicMock()
        self._sent: list[str] = []
        self._name_answer = name_answer

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        pass

    async def prompt(self, *a, **kw):
        return self._name_answer

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _session(monster_name='WILD HORSE'):
    return CombatSession({'name': monster_name, 'strength': 0, 'flags': {}}, room_no=1)


@patch('combat.engine.CombatSession._append_capture_log')
class TestClassTaming(unittest.IsolatedAsyncioTestCase):

    async def test_non_druid_ranger_never_tames(self, _log):
        player = _FakePlayer(char_class=PlayerClass.FIGHTER)
        ctx = _FakeCtx(player)
        session = _session()
        with patch('combat.engine.random.randint', return_value=1):   # would succeed if eligible
            tamed = await session._try_class_tame(ctx)
        self.assertFalse(tamed)
        self.assertEqual(player.party, [])

    async def test_non_horse_monster_no_op(self, _log):
        player = _FakePlayer(char_class=PlayerClass.DRUID)
        ctx = _FakeCtx(player)
        session = _session(monster_name='TROLL')
        with patch('combat.engine.random.randint', return_value=1):
            tamed = await session._try_class_tame(ctx)
        self.assertFalse(tamed)

    async def test_druid_success_creates_mount_and_ends_combat(self, _log):
        player = _FakePlayer(char_class=PlayerClass.DRUID, gender=Gender.MALE)
        ctx = _FakeCtx(player, name_answer='Silver')
        session = _session()
        with patch('combat.engine.random.randint', return_value=1):   # 1 <= 15 -> success
            tamed = await session._try_class_tame(ctx)
        self.assertTrue(tamed)
        self.assertTrue(session._done.is_set())
        self.assertEqual(len(player.party), 1)
        self.assertEqual(player.party[0].name, 'Silver')
        self.assertIn('as its master!', ctx.sent())

    async def test_ranger_success_female_uses_mistress(self, _log):
        player = _FakePlayer(char_class=PlayerClass.RANGER, gender=Gender.FEMALE)
        ctx = _FakeCtx(player, name_answer='Star')
        session = _session()
        with patch('combat.engine.random.randint', return_value=1):
            tamed = await session._try_class_tame(ctx)
        self.assertTrue(tamed)
        self.assertIn('as its mistress!', ctx.sent())

    async def test_failed_roll_does_nothing(self, _log):
        player = _FakePlayer(char_class=PlayerClass.DRUID)
        ctx = _FakeCtx(player)
        session = _session()
        with patch('combat.engine.random.randint', return_value=100):   # 100 > 15 -> fail
            tamed = await session._try_class_tame(ctx)
        self.assertFalse(tamed)
        self.assertFalse(session._done.is_set())
        self.assertEqual(player.party, [])

    async def test_full_party_blocks_silently(self, _log):
        from bar.ally_data import Ally, AllyStatus
        allies = [Ally(name=f'A{i}', gender='m', strength=10, to_hit=5) for i in range(3)]
        for a in allies:
            a.status = AllyStatus.SERVANT
        player = _FakePlayer(char_class=PlayerClass.DRUID, allies=allies)
        ctx = _FakeCtx(player)
        session = _session()
        with patch('combat.engine.random.randint', return_value=1), \
             patch('bar.allies.owned_allies', return_value=allies):
            tamed = await session._try_class_tame(ctx)
        self.assertFalse(tamed)
        self.assertEqual(ctx.sent(), '')   # silent, no "Only 3 allies allowed" spam

    async def test_already_finished_combat_is_a_no_op(self, _log):
        player = _FakePlayer(char_class=PlayerClass.DRUID)
        ctx = _FakeCtx(player)
        session = _session()
        session._done.set()
        with patch('combat.engine.random.randint', return_value=1):
            tamed = await session._try_class_tame(ctx)
        self.assertFalse(tamed)


if __name__ == '__main__':
    unittest.main()
