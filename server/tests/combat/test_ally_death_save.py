"""tests/test_ally_death_save.py

Unit tests for ally_events.try_ally_death_save (SPUR.COMBAT.S "dragon" ->
sac.ally, ported from the skip branch's SPUR.MISC9.S).

Coverage:
  - no allies / non-lethal damage -> no-op, returns False
  - GOD/GODDESS ally always saves: returns True, ally freed, message shown
  - non-elite ally fails courage roll -> flees (freed), cascades to next ally
  - non-elite ally passes courage roll -> "sacrifices" (marked DEAD), damage
    still lands (returns False) -- matches the source's actual behavior
  - ELITE ally gets -100 courage bonus (less likely to flee)
  - cascade stops as soon as an ally is freed or sacrifices

Run with:
    python -m pytest tests/test_ally_death_save.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

import sys, types

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from bar.ally_data import Ally, AllyFlags, AllyStatus
from ally_events import try_ally_death_save


def _make_ally(name='BARDA', flags=None) -> Ally:
    a = Ally(name=name, gender='f', strength=10, to_hit=5, flags=flags or [])
    a.status = AllyStatus.SERVANT
    return a


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self._sent: list[str] = []

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _make_player(allies=None, honor=1000, hit_points=5, name='Rulan'):
    class _P:
        pass
    p = _P()
    p.name = name
    p.honor = honor
    p.hit_points = hit_points
    p.unsaved_changes = False
    p.party = list(allies or [])
    return p


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@patch('ally_events._free_ally_in_roster')
class TestAllyDeathSave(unittest.IsolatedAsyncioTestCase):

    async def test_no_allies_returns_false(self, _mock_roster):
        player = _make_player(allies=[], hit_points=5)
        ctx = _FakeCtx(player)
        saved = await try_ally_death_save(ctx, incoming_damage=10)
        self.assertFalse(saved)
        self.assertEqual(ctx.sent(), '')

    async def test_non_lethal_damage_returns_false(self, _mock_roster):
        ally = _make_ally()
        player = _make_player(allies=[ally], hit_points=50)
        ctx = _FakeCtx(player)
        saved = await try_ally_death_save(ctx, incoming_damage=10)
        self.assertFalse(saved)
        self.assertEqual(ctx.sent(), '')
        self.assertIn(ally, player.party)

    async def test_god_ally_always_saves(self, _mock_roster):
        ally = _make_ally(name='ANUBIS', flags=[AllyFlags.GOD])
        player = _make_player(allies=[ally], hit_points=5)
        ctx = _FakeCtx(player)
        saved = await try_ally_death_save(ctx, incoming_damage=10)
        self.assertTrue(saved)
        self.assertIn('whisks you away', ctx.sent())
        self.assertNotIn(ally, player.party)
        self.assertEqual(ally.status, AllyStatus.FREE)
        self.assertIsNone(ally.owner)

    async def test_goddess_ally_always_saves(self, _mock_roster):
        ally = _make_ally(name='ATHENA', flags=[AllyFlags.GODDESS])
        player = _make_player(allies=[ally], hit_points=5)
        ctx = _FakeCtx(player)
        saved = await try_ally_death_save(ctx, incoming_damage=10)
        self.assertTrue(saved)

    async def test_courage_fail_flees_and_returns_false(self, _mock_roster):
        """High courage roll vs low honor -> ally flees; hit still lands."""
        ally = _make_ally(name='COWARD')
        player = _make_player(allies=[ally], honor=0, hit_points=5)
        ctx = _FakeCtx(player)
        with patch('ally_events.random.randint', return_value=999):
            saved = await try_ally_death_save(ctx, incoming_damage=10)
        self.assertFalse(saved)
        self.assertIn('runs away', ctx.sent())
        self.assertNotIn(ally, player.party)
        self.assertEqual(ally.status, AllyStatus.FREE)

    async def test_courage_pass_sacrifices_but_damage_still_lands(self, _mock_roster):
        """Low courage roll vs high honor -> ally 'sacrifices', but this is
        flavor only in the source: the cascade stops and returns False, so
        the caller still applies the incoming damage."""
        ally = _make_ally(name='BRAVE')
        player = _make_player(allies=[ally], honor=2000, hit_points=5)
        ctx = _FakeCtx(player)
        with patch('ally_events.random.randint', return_value=200):
            saved = await try_ally_death_save(ctx, incoming_damage=10)
        self.assertFalse(saved)
        self.assertIn('leaps in front', ctx.sent())
        self.assertNotIn(ally, player.party)
        self.assertEqual(ally.status, AllyStatus.DEAD)

    async def test_elite_gets_courage_bonus(self, _mock_roster):
        """ELITE flag subtracts 100 from the courage roll, making flight less likely."""
        ally = _make_ally(name='ELITE1', flags=[AllyFlags.ELITE])
        player = _make_player(allies=[ally], honor=850, hit_points=5)
        ctx = _FakeCtx(player)
        # roll=900 -> elite effective courage=800, which is <= honor(850): stands and fights
        with patch('ally_events.random.randint', return_value=900):
            saved = await try_ally_death_save(ctx, incoming_damage=10)
        self.assertIn('leaps in front', ctx.sent())
        self.assertEqual(ally.status, AllyStatus.DEAD)

    async def test_cascade_tries_next_ally_after_flee(self, _mock_roster):
        """First ally flees; second ally (a GOD) then saves the player."""
        coward = _make_ally(name='COWARD')
        god    = _make_ally(name='ANUBIS', flags=[AllyFlags.GOD])
        player = _make_player(allies=[coward, god], honor=0, hit_points=5)
        ctx = _FakeCtx(player)
        with patch('ally_events.random.randint', return_value=999):
            saved = await try_ally_death_save(ctx, incoming_damage=10)
        self.assertTrue(saved)
        self.assertIn('runs away', ctx.sent())
        self.assertIn('whisks you away', ctx.sent())
        self.assertNotIn(coward, player.party)
        self.assertNotIn(god, player.party)

    async def test_cascade_stops_after_sacrifice(self, _mock_roster):
        """A second ally is never touched once the first one sacrifices."""
        brave = _make_ally(name='BRAVE')
        other = _make_ally(name='OTHER')
        player = _make_player(allies=[brave, other], honor=2000, hit_points=5)
        ctx = _FakeCtx(player)
        with patch('ally_events.random.randint', return_value=200):
            saved = await try_ally_death_save(ctx, incoming_damage=10)
        self.assertFalse(saved)
        self.assertIn(other, player.party)
        self.assertEqual(other.status, AllyStatus.SERVANT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
