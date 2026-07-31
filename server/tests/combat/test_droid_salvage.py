"""tests/combat/test_droid_salvage.py — encounters/droid_salvage.py:
salvage-parts drop + energy-weapon power pak recharge on mechanical-monster
kills (SPUR.MISC.S:406-415).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from encounters.droid_salvage import apply
from items import Weapon
from player import Player


class _FakeServer:
    def __init__(self, items=None):
        self.items = items if items is not None else [
            {'number': 146, 'name': 'salvage parts', 'price': 5},
        ]


class _FakeCtx:
    def __init__(self, player, server=None, answers=None):
        self.player = player
        self.server = server or _FakeServer()
        self.sent: list = []
        self._answers = list(answers or [])

    async def send(self, *args):
        self.sent.extend(args)

    async def prompt(self, prompt_text='', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._answers.pop(0) if self._answers else 'n'


def _flat(ctx) -> str:
    return '\n'.join(str(x) for x in ctx.sent)


def _make_player(*, energy_weapon: bool, ammo_rounds=2, ammo_max=10):
    p = Player(name='Tester', id='tester')
    if energy_weapon:
        p.readied_weapon = Weapon(
            id_number=60, name='PLASMA RIFLE', stability=60,
            to_hit=90, weapon_class='energy',
        )
        p.ammo_rounds = ammo_rounds
        p.ammo_max = ammo_max
    else:
        p.readied_weapon = Weapon(
            id_number=1, name='LONG SWORD', stability=50,
            to_hit=60, weapon_class='bash/slash',
        )
    return p


_MECH_MONSTER = {'number': 107, 'name': 'GUARD DROID', 'flags': {'mechanical': True}}
_NORMAL_MONSTER = {'number': 1, 'name': 'A GOBLIN', 'flags': {'mechanical': False}}


class TestNonMechanicalMonster(unittest.IsolatedAsyncioTestCase):
    async def test_no_op_when_monster_not_mechanical(self):
        player = _make_player(energy_weapon=True)
        ctx = _FakeCtx(player)
        await apply(ctx, _NORMAL_MONSTER)
        self.assertEqual(ctx.sent, [])


class TestSalvagePartsDrop(unittest.IsolatedAsyncioTestCase):
    async def test_success_roll_adds_item_and_message(self):
        player = _make_player(energy_weapon=False)
        ctx = _FakeCtx(player)
        with patch('encounters.droid_salvage.random.randint', return_value=5):
            await apply(ctx, _MECH_MONSTER)
        self.assertIn('salvage parts', _flat(ctx))
        entries = player.inventory.entries()
        self.assertTrue(any(e.item.name == 'salvage parts' for e in entries))

    async def test_failure_roll_gives_no_item(self):
        player = _make_player(energy_weapon=False)
        ctx = _FakeCtx(player)
        with patch('encounters.droid_salvage.random.randint', return_value=6):
            await apply(ctx, _MECH_MONSTER)
        self.assertIn('No salvageable parts.', ctx.sent)
        self.assertEqual(len(player.inventory), 0)


class TestPowerPakRecharge(unittest.IsolatedAsyncioTestCase):
    async def test_non_energy_weapon_gets_no_recharge_prompt(self):
        player = _make_player(energy_weapon=False)
        ctx = _FakeCtx(player)
        with patch('encounters.droid_salvage.random.randint', return_value=6):
            await apply(ctx, _MECH_MONSTER)
        self.assertNotIn('energized', _flat(ctx))

    async def test_energy_weapon_success_roll_and_accept_recharges_ammo(self):
        player = _make_player(energy_weapon=True, ammo_rounds=1, ammo_max=25)
        ctx = _FakeCtx(player, answers=['y'])
        with patch('encounters.droid_salvage.random.randint', side_effect=[6, 4]):
            await apply(ctx, _MECH_MONSTER)
        self.assertIn('still energized!', _flat(ctx))
        self.assertIn('ZZZZTTT', ctx.sent)
        self.assertEqual(player.ammo_rounds, 25)

    async def test_energy_weapon_success_roll_but_decline_leaves_ammo_unchanged(self):
        player = _make_player(energy_weapon=True, ammo_rounds=1, ammo_max=25)
        ctx = _FakeCtx(player, answers=['n'])
        with patch('encounters.droid_salvage.random.randint', side_effect=[6, 4]):
            await apply(ctx, _MECH_MONSTER)
        self.assertEqual(player.ammo_rounds, 1)
        self.assertNotIn('ZZZZTTT', ctx.sent)

    async def test_energy_weapon_failure_roll_destroys_pak(self):
        player = _make_player(energy_weapon=True, ammo_rounds=1, ammo_max=25)
        ctx = _FakeCtx(player)
        with patch('encounters.droid_salvage.random.randint', side_effect=[6, 5]):
            await apply(ctx, _MECH_MONSTER)
        self.assertIn('was destroyed.', _flat(ctx))
        self.assertEqual(player.ammo_rounds, 1)


if __name__ == '__main__':
    unittest.main()
