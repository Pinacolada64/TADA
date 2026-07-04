"""tests/test_ally_events.py

Unit tests for ally_events.try_ally_find_gold.

Coverage:
  Guards (silent no-ops):
    - no SERVANT allies → no output
    - water room (flag-based) → no output
    - water room (keyword-based) → no output
    - already fired today ('AYF' in once_per_day) → no output
    - once_per_day is None → no output
    - random roll misses → no output

  Happy path (random forced to hit):
    - gold credited to player IN_HAND
    - amount is in valid range (52-250 gp)
    - 'AYF' appended to once_per_day after firing
    - player.unsaved_changes set True after firing
    - output mentions ally name
    - output mentions gp amount
    - first ally in purchased_allies list is used (SPUR a1 priority)
    - fires exactly once even if called twice in same session (tag blocks second call)

Run with:
    python -m pytest tests/test_ally_events.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch, MagicMock

import sys, types

# Minimal stubs so imports resolve without the full networking stack
nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from bar.ally_data import Ally, AllyStatus
from ally_events import try_ally_find_gold, _OPD_ALLY_GOLD
from base_classes import PlayerMoneyTypes


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_ally(name='BARDA', status=AllyStatus.SERVANT) -> Ally:
    a = Ally(name=name, gender='f', strength=10, to_hit=5)
    a.status = status
    return a


class _Room:
    def __init__(self, name='EAST HALL', desc='', flags=None):
        self.name  = name
        self.desc  = desc
        self.flags = flags or []


class _FakeMap:
    def __init__(self, room=None):
        self._room = room

    def get(self, room_no):
        return self._room

    def get_room(self, level, room_no):
        return self._room

    @property
    def rooms(self):
        return self


class _FakeServer:
    def __init__(self, room=None):
        self.game_map = _FakeMap(room)


class _FakeClient:
    def __init__(self, room_no=1):
        self.room = room_no


class _FakeCtx:
    def __init__(self, player, room=None, room_no=1):
        self.player = player
        self.server = _FakeServer(room=room)
        self.client = _FakeClient(room_no=room_no)
        self._sent: list[str] = []

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _make_player(allies=None, gold=0, once_per_day=None):
    p = MagicMock()
    p.name = 'Rulan'
    p.once_per_day = once_per_day if once_per_day is not None else []
    p.unsaved_changes = False

    wallet = {PlayerMoneyTypes.IN_HAND: gold}

    def get_silver(kind):
        return wallet.get(kind, 0)

    def set_silver_absolute(kind, value):
        wallet[kind] = value

    p.get_silver.side_effect  = get_silver
    p.set_silver_absolute.side_effect = set_silver_absolute
    p._wallet = wallet

    party_mock = MagicMock()
    party_mock.__iter__ = MagicMock(return_value=iter(allies or []))
    p.party = party_mock

    return p


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Guards — no ally gold should fire
# ---------------------------------------------------------------------------

class TestAllyFindGoldGuards(unittest.IsolatedAsyncioTestCase):

    async def _call_always_hits(self, ctx):
        """Call with random forced to always trigger."""
        with patch('ally_events.random.random', return_value=0.0), \
             patch('ally_events.random.randint', return_value=50):
            await try_ally_find_gold(ctx)

    async def test_no_allies_silent(self):
        """No allies in party → no gold, no output."""
        player = _make_player(allies=[])
        ctx    = _FakeCtx(player)
        await self._call_always_hits(ctx)
        self.assertEqual(ctx.sent(), '')
        self.assertNotIn(_OPD_ALLY_GOLD, player.once_per_day)

    async def test_free_ally_can_find_gold(self):
        """FREE-status allies are still in the party and can find gold."""
        ally   = _make_ally(name='LYSSA', status=AllyStatus.FREE)
        player = _make_player(allies=[ally], gold=0)
        ctx    = _FakeCtx(player)
        await self._call_always_hits(ctx)
        self.assertIn(_OPD_ALLY_GOLD, player.once_per_day)
        self.assertIn('LYSSA', ctx.sent())

    async def test_water_room_flag_blocks(self):
        """Water room (flag) silences the event."""
        ally   = _make_ally()
        player = _make_player(allies=[ally])
        room   = _Room(name='POOL ROOM', flags=['water'])
        ctx    = _FakeCtx(player, room=room)
        await self._call_always_hits(ctx)
        self.assertEqual(ctx.sent(), '')

    async def test_water_room_keyword_blocks(self):
        """Water room (name keyword) silences the event."""
        ally   = _make_ally()
        player = _make_player(allies=[ally])
        room   = _Room(name='UNDERGROUND RAPIDS')
        ctx    = _FakeCtx(player, room=room)
        await self._call_always_hits(ctx)
        self.assertEqual(ctx.sent(), '')

    async def test_already_fired_today_blocks(self):
        """'AYF' already in once_per_day → skip."""
        ally   = _make_ally()
        player = _make_player(allies=[ally], once_per_day=[_OPD_ALLY_GOLD])
        ctx    = _FakeCtx(player)
        await self._call_always_hits(ctx)
        self.assertEqual(ctx.sent(), '')

    async def test_once_per_day_none_blocks(self):
        """once_per_day=None (misconfigured player) → skip gracefully."""
        ally         = _make_ally()
        player       = _make_player(allies=[ally])
        player.once_per_day = None
        ctx          = _FakeCtx(player)
        await self._call_always_hits(ctx)
        self.assertEqual(ctx.sent(), '')

    async def test_random_miss_silent(self):
        """Probability gate not hit → no output."""
        ally   = _make_ally()
        player = _make_player(allies=[ally])
        ctx    = _FakeCtx(player)
        with patch('ally_events.random.random', return_value=1.0):
            await try_ally_find_gold(ctx)
        self.assertEqual(ctx.sent(), '')
        self.assertNotIn(_OPD_ALLY_GOLD, player.once_per_day)


# ---------------------------------------------------------------------------
# Happy path — gold fires
# ---------------------------------------------------------------------------

class TestAllyFindGoldFires(unittest.IsolatedAsyncioTestCase):

    def _setup(self, ally_name='BARDA', starting_gold=100):
        ally   = _make_ally(name=ally_name)
        player = _make_player(allies=[ally], gold=starting_gold)
        ctx    = _FakeCtx(player)
        return ally, player, ctx

    async def _fire(self, ctx, roll=50):
        with patch('ally_events.random.random', return_value=0.0), \
             patch('ally_events.random.randint', return_value=roll):
            await try_ally_find_gold(ctx)

    async def test_gold_credited(self):
        """Player receives gold."""
        _, player, ctx = self._setup(starting_gold=100)
        await self._fire(ctx, roll=50)
        self.assertGreater(player._wallet[PlayerMoneyTypes.IN_HAND], 100)

    async def test_gold_amount_formula(self):
        """Amount = (roll*2)+50; roll=50 → 150 gp."""
        _, player, ctx = self._setup(starting_gold=0)
        await self._fire(ctx, roll=50)
        self.assertEqual(player._wallet[PlayerMoneyTypes.IN_HAND], 150)

    async def test_gold_min_roll(self):
        """roll=1 → 52 gp (minimum)."""
        _, player, ctx = self._setup(starting_gold=0)
        await self._fire(ctx, roll=1)
        self.assertEqual(player._wallet[PlayerMoneyTypes.IN_HAND], 52)

    async def test_gold_max_roll(self):
        """roll=100 → 250 gp (maximum)."""
        _, player, ctx = self._setup(starting_gold=0)
        await self._fire(ctx, roll=100)
        self.assertEqual(player._wallet[PlayerMoneyTypes.IN_HAND], 250)

    async def test_ayf_tag_appended(self):
        """'AYF' is added to once_per_day after firing."""
        _, player, ctx = self._setup()
        await self._fire(ctx)
        self.assertIn(_OPD_ALLY_GOLD, player.once_per_day)

    async def test_unsaved_changes_set(self):
        """player.unsaved_changes is True after gold is credited."""
        _, player, ctx = self._setup()
        await self._fire(ctx)
        self.assertTrue(player.unsaved_changes)

    async def test_output_mentions_ally_name(self):
        """Ally name appears in output."""
        ally, _, ctx = self._setup(ally_name='LYSSA')
        await self._fire(ctx)
        self.assertIn('LYSSA', ctx.sent())

    async def test_output_mentions_gp(self):
        """GP amount appears in output."""
        _, _, ctx = self._setup()
        await self._fire(ctx, roll=50)
        self.assertIn('150', ctx.sent())

    async def test_first_ally_used(self):
        """First SERVANT ally in party order is chosen (SPUR a1 priority)."""
        ally_a = _make_ally(name='ALAN')
        ally_b = _make_ally(name='BARDA')
        player = _make_player(allies=[ally_a, ally_b], gold=0)
        ctx    = _FakeCtx(player)
        with patch('ally_events.random.random', return_value=0.0), \
             patch('ally_events.random.randint', return_value=50):
            await try_ally_find_gold(ctx)
        self.assertIn('ALAN', ctx.sent())
        self.assertNotIn('BARDA', ctx.sent())

    async def test_does_not_fire_twice(self):
        """Second call on same player is a no-op (tag blocks it)."""
        _, player, ctx = self._setup(starting_gold=0)
        await self._fire(ctx, roll=50)
        gold_after_first = player._wallet[PlayerMoneyTypes.IN_HAND]
        ctx._sent.clear()
        await self._fire(ctx, roll=50)
        self.assertEqual(player._wallet[PlayerMoneyTypes.IN_HAND], gold_after_first)
        self.assertEqual(ctx.sent(), '')

    async def test_dry_room_does_not_block(self):
        """Normal dry room does not suppress the event."""
        ally   = _make_ally()
        player = _make_player(allies=[ally], gold=0)
        room   = _Room(name='EAST HALL')
        ctx    = _FakeCtx(player, room=room)
        with patch('ally_events.random.random', return_value=0.0), \
             patch('ally_events.random.randint', return_value=50):
            await try_ally_find_gold(ctx)
        self.assertIn(_OPD_ALLY_GOLD, player.once_per_day)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main(verbosity=2)
