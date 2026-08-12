"""tests/commands/test_drink_skill_potion.py — POTION OF SKILL (item #65),
SPUR.SUB.S potion subroutine "OF SKILL" branch: +4 to-hit with the readied
weapon, lasting only "until READY is executed again."
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.drink import DrinkCommand
from commands.unready import UnreadyCommand
from inventory import Inventory
from items import Rations


def run(coro):
    return asyncio.run(coro)


class _FakeWeapon:
    def __init__(self, name='DAGGER', number=1):
        self.name = name
        self.id_number = number
        self.category = None


class _FakePlayer:
    def __init__(self, drink=10, readied_weapon=None):
        self.drink = drink
        self.food = 20
        self.inventory = Inventory(capacity=14)
        self.party = []
        self.readied_weapon = readied_weapon
        self.storm_servant_bonus = None
        self.skill_potion_bonus = None


def make_ctx(player):
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(return_value='')
    return ctx


class TestPotionOfSkill(unittest.IsolatedAsyncioTestCase):

    async def test_grants_bonus_when_weapon_readied(self):
        weapon = _FakeWeapon('LONG SWORD')
        player = _FakePlayer(readied_weapon=weapon)
        player.inventory.add(Rations(number=65, name='POTION OF SKILL', kind='drink', price=50))
        ctx = make_ctx(player)

        await DrinkCommand().execute(ctx, 'potion')

        self.assertEqual(player.skill_potion_bonus, 4)
        sent = str(ctx.send.call_args_list)
        self.assertIn('more skillful', sent.lower())
        self.assertIn('LONG SWORD', sent)

    async def test_no_bonus_without_readied_weapon(self):
        player = _FakePlayer(readied_weapon=None)
        player.inventory.add(Rations(number=65, name='POTION OF SKILL', kind='drink', price=50))
        ctx = make_ctx(player)

        await DrinkCommand().execute(ctx, 'potion')

        self.assertIsNone(player.skill_potion_bonus)

    async def test_unready_clears_bonus(self):
        weapon = _FakeWeapon('LONG SWORD')
        player = _FakePlayer(readied_weapon=weapon)
        player.skill_potion_bonus = 4
        ctx = make_ctx(player)

        await UnreadyCommand().execute(ctx)

        self.assertIsNone(player.skill_potion_bonus)


if __name__ == '__main__':
    unittest.main()
