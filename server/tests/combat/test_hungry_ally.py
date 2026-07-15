"""tests/test_hungry_ally.py

Unit tests for ally_events.try_hungry_ally — the eat/drink interception
mechanic (SPUR SUB.S hun.slv).

Coverage:
  Guards (no interception):
    - no allies in party → player eats normally
    - all allies have strength >= 11 → no interception
    - only elite allies are hungry → no interception (elite stays silent)

  Happy path (player feeds the ally):
    - item removed from player inventory
    - ally strength boosted (via _try_body_build)
    - player honor increases (low-quality food: +2; high-quality: +5)
    - honor capped at 2000
    - player.unsaved_changes set True
    - returns True so caller skips normal consumption

  Player declines to feed:
    - returns False, item stays in inventory, ally strength unchanged
    - no honor change

  Ally selection:
    - weakest non-elite ally is chosen when multiple hungry allies present
    - elite ally ignored even if weaker than a non-elite

  Drink interception:
    - try_hungry_ally with kind='THIRSTY' works the same way

Run with:
    python -m pytest tests/test_hungry_ally.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

import sys, types

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from ally_events import try_hungry_ally
from bar.ally_data import Ally, AllyFlags, AllyStatus
from inventory import Inventory
from items import Item, ItemCategory
from party import Party


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ally(name='BARDA', strength=8, elite=False, status=AllyStatus.SERVANT):
    flags = [AllyFlags.ELITE] if elite else []
    a = Ally(name, 'f', strength, 5, flags)
    a.status = status
    return a


def _make_food(name='RATION', price=10):
    return Item(id_number=1, name=name, kind='food', price=price)


def _make_drink(name='ALE', price=10):
    return Item(id_number=2, name=name, kind='drink', price=price)


def _make_player(allies=None, honor=1000):
    p = MagicMock()
    p.name = 'Rulan'
    p.honor = honor
    p.unsaved_changes = False
    p.inventory = Inventory()
    p.party = Party()
    for ally in (allies or []):
        p.party.add_member(p, ally)
    return p


class _FakeCtx:
    def __init__(self, player, prompt_answer=''):
        self.player = player
        self._sent: list[str] = []
        self._prompt_answer = prompt_answer

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def prompt(self, *args, **kwargs):
        return self._prompt_answer

    def sent(self):
        return '\n'.join(self._sent)


# ---------------------------------------------------------------------------
# Guards — no interception
# ---------------------------------------------------------------------------

class TestHungryAllyGuards(unittest.IsolatedAsyncioTestCase):

    async def test_no_allies_no_interception(self):
        player = _make_player(allies=[])
        food   = _make_food()
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer='Y')
        result = await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertFalse(result)

    async def test_strong_allies_no_interception(self):
        """Allies at or above cap (strength >= 11) don't complain."""
        ally   = _make_ally(strength=11)
        player = _make_player(allies=[ally])
        food   = _make_food()
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer='Y')
        result = await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertFalse(result)
        self.assertEqual(ctx.sent(), '')

    async def test_elite_ally_stays_silent(self):
        """Elite allies never complain, even if hungry."""
        ally   = _make_ally(strength=5, elite=True)
        player = _make_player(allies=[ally])
        food   = _make_food()
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer='Y')
        result = await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertFalse(result)
        self.assertEqual(ctx.sent(), '')


# ---------------------------------------------------------------------------
# Happy path — player feeds the ally
# ---------------------------------------------------------------------------

class TestHungryAllyFed(unittest.IsolatedAsyncioTestCase):

    def _setup(self, ally_strength=8, honor=1000, food_price=10, prompt=''):
        ally   = _make_ally(strength=ally_strength)
        player = _make_player(allies=[ally], honor=honor)
        food   = _make_food(price=food_price)
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer=prompt)
        return ally, player, food, ctx

    async def test_returns_true_when_fed(self):
        _, player, food, ctx = self._setup(prompt='')
        result = await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertTrue(result)

    async def test_item_removed_from_inventory(self):
        _, player, food, ctx = self._setup(prompt='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertEqual(len(player.inventory.entries()), 0)

    async def test_ally_strength_boosted(self):
        ally, player, food, ctx = self._setup(ally_strength=8, prompt='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertEqual(ally.strength, 9)

    async def test_low_quality_food_grants_two_honor(self):
        """price=10 → ration_restore=1 < 5 → +2 honor."""
        _, player, food, ctx = self._setup(honor=1000, food_price=10, prompt='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertEqual(player.honor, 1002)

    async def test_high_quality_food_grants_five_honor(self):
        """price=50 → ration_restore=5 → +5 honor."""
        _, player, food, ctx = self._setup(honor=1000, food_price=50, prompt='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertEqual(player.honor, 1005)

    async def test_honor_capped_at_2000(self):
        _, player, food, ctx = self._setup(honor=1999, food_price=50, prompt='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertEqual(player.honor, 2000)

    async def test_unsaved_changes_set(self):
        _, player, food, ctx = self._setup(prompt='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertTrue(player.unsaved_changes)

    async def test_output_mentions_ally_name(self):
        ally, player, food, ctx = self._setup(prompt='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertIn(ally.name, ctx.sent())

    async def test_output_mentions_thank_you(self):
        _, player, food, ctx = self._setup(prompt='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertIn('Thank you', ctx.sent())

    async def test_honor_gain_message_shown(self):
        _, player, food, ctx = self._setup(prompt='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertIn('honorable', ctx.sent().lower())


# ---------------------------------------------------------------------------
# Player declines to feed
# ---------------------------------------------------------------------------

class TestHungryAllyDeclined(unittest.IsolatedAsyncioTestCase):

    async def test_decline_returns_false(self):
        ally   = _make_ally(strength=8)
        player = _make_player(allies=[ally], honor=1000)
        food   = _make_food()
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer='N')
        result = await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertFalse(result)

    async def test_decline_item_stays_in_inventory(self):
        ally   = _make_ally(strength=8)
        player = _make_player(allies=[ally])
        food   = _make_food()
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer='N')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertEqual(len(player.inventory.entries()), 1)

    async def test_decline_deducts_honor(self):
        ally   = _make_ally(strength=8)
        player = _make_player(allies=[ally], honor=1000)
        food   = _make_food()
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer='N')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertEqual(player.honor, 998)

    async def test_decline_honor_message_shown(self):
        ally   = _make_ally(strength=8)
        player = _make_player(allies=[ally], honor=1000)
        food   = _make_food()
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer='N')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertIn('less honorable', ctx.sent().lower())

    async def test_decline_ally_strength_unchanged(self):
        ally   = _make_ally(strength=8)
        player = _make_player(allies=[ally])
        food   = _make_food()
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer='N')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertEqual(ally.strength, 8)


# ---------------------------------------------------------------------------
# Ally selection
# ---------------------------------------------------------------------------

class TestHungryAllySelection(unittest.IsolatedAsyncioTestCase):

    async def test_weakest_ally_chosen(self):
        """With two hungry non-elite allies, the weaker one gets the food."""
        strong = _make_ally(name='STRONG', strength=9)
        weak   = _make_ally(name='WEAK',   strength=5)
        player = _make_player(allies=[strong, weak])
        food   = _make_food()
        player.inventory.add(food)
        ctx    = _FakeCtx(player, prompt_answer='')
        await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertIn('WEAK', ctx.sent())
        self.assertNotIn('STRONG', ctx.sent())

    async def test_elite_skipped_in_favour_of_non_elite(self):
        """Elite ally with strength 3 is ignored; weaker-named non-elite gets food."""
        elite    = _make_ally(name='GODLIKE', strength=3, elite=True)
        nonelite = _make_ally(name='SCRAPPY',  strength=7)
        player   = _make_player(allies=[elite, nonelite])
        food     = _make_food()
        player.inventory.add(food)
        ctx      = _FakeCtx(player, prompt_answer='')
        result   = await try_hungry_ally(ctx, food, 'HUNGRY')
        self.assertTrue(result)
        self.assertIn('SCRAPPY', ctx.sent())
        self.assertNotIn('GODLIKE', ctx.sent())


# ---------------------------------------------------------------------------
# Drink interception
# ---------------------------------------------------------------------------

class TestHungryAllyDrink(unittest.IsolatedAsyncioTestCase):

    async def test_thirsty_kind_shown_in_output(self):
        ally   = _make_ally(strength=8)
        player = _make_player(allies=[ally])
        drink  = _make_drink()
        player.inventory.add(drink)
        ctx    = _FakeCtx(player, prompt_answer='')
        result = await try_hungry_ally(ctx, drink, 'THIRSTY')
        self.assertTrue(result)
        self.assertIn(ally.name, ctx.sent())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main(verbosity=2)
