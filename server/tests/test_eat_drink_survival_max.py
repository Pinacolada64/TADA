"""tests/test_eat_drink_survival_max.py — commands/eat.py's and
commands/drink.py's "You're not hungry."/"You're not thirsty." gate now
reads config.survival_max instead of a hardcoded 20, so it stays correct
if a sysop raises/lowers that setting (see config.py's SETTINGS_METADATA).
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from config import config
from commands.eat import EatCommand
from commands.drink import DrinkCommand
from inventory import Inventory
from items import Rations


def run(coro):
    return asyncio.run(coro)


class _FakePlayer:
    def __init__(self, food=20, drink=20):
        self.food = food
        self.drink = drink
        self.inventory = Inventory(capacity=14)
        self.party = []


def make_ctx(player):
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(return_value='')
    return ctx


class _ConfigTestCase(unittest.TestCase):
    """commands/eat.py/commands/drink.py read the module-level `config`
    singleton directly (`from config import config`), not a freshly
    constructed ServerConfig() -- swapping ServerConfig._config_file/
    _instance (the pattern other config tests use) wouldn't affect that
    already-bound object. Reset its actual survival_max value instead,
    so tests stay isolated regardless of run order."""

    def setUp(self):
        self._orig_survival_max = config.survival_max
        config.survival_max = 20

    def tearDown(self):
        config.survival_max = self._orig_survival_max


class TestEatHonorsSurvivalMax(_ConfigTestCase):

    def test_not_hungry_at_default_max(self):
        player = _FakePlayer(food=20)
        player.inventory.add(Rations(number=5, name='LOAF OF BREAD', kind='food', price=30))
        ctx = make_ctx(player)
        run(EatCommand().execute(ctx, 'bread'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('not hungry', sent.lower())

    def test_can_eat_when_below_raised_max(self):
        config.survival_max = 40

        player = _FakePlayer(food=20)   # full under the old default, but not under 40
        player.inventory.add(Rations(number=5, name='LOAF OF BREAD', kind='food', price=30))
        ctx = make_ctx(player)
        run(EatCommand().execute(ctx, 'bread'))
        sent = str(ctx.send.call_args_list)
        self.assertNotIn('not hungry', sent.lower())

    def test_not_hungry_at_raised_max_when_actually_full(self):
        config.survival_max = 40

        player = _FakePlayer(food=40)
        player.inventory.add(Rations(number=5, name='LOAF OF BREAD', kind='food', price=30))
        ctx = make_ctx(player)
        run(EatCommand().execute(ctx, 'bread'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('not hungry', sent.lower())


class TestDrinkHonorsSurvivalMax(_ConfigTestCase):

    def test_not_thirsty_at_default_max(self):
        player = _FakePlayer(drink=20)
        player.inventory.add(Rations(number=12, name='MINERAL WATER', kind='drink', price=10))
        ctx = make_ctx(player)
        run(DrinkCommand().execute(ctx, 'water'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('not thirsty', sent.lower())

    def test_can_drink_when_below_raised_max(self):
        config.survival_max = 40

        player = _FakePlayer(drink=20)
        player.inventory.add(Rations(number=12, name='MINERAL WATER', kind='drink', price=10))
        ctx = make_ctx(player)
        run(DrinkCommand().execute(ctx, 'water'))
        sent = str(ctx.send.call_args_list)
        self.assertNotIn('not thirsty', sent.lower())


if __name__ == '__main__':
    unittest.main()
