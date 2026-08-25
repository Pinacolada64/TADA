"""tests/shoppe/test_school.py

Covers shoppe/school.py -- Formal Shield Training (SPUR.MISC2.S school.3),
reached from the Merchant Shoppe via the free-text SCHOOL command word,
same dispatch pattern as LOCKER (see test_shoppe_locker.py).
"""
from __future__ import annotations

import unittest

from shoppe.school import main as school_main, _training_cost
from base_classes import PlayerClass, PlayerRace
from flags import PlayerFlags
from player import Player


class _FakeServer:
    def __init__(self):
        import json
        import os
        path = os.path.join(os.path.dirname(__file__), '..', '..', 'messages.json')
        with open(path) as f:
            self.messages = {int(k): v for k, v in json.load(f).items()}


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.server = _FakeServer()

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestTrainingCost(unittest.TestCase):
    def test_paladin_human(self):
        # (300 + 500) * 3 // 2 = 1200 (SPUR.MISC2.S:451-454)
        self.assertEqual(_training_cost(PlayerClass.PALADIN, PlayerRace.HUMAN), 1200)

    def test_wizard_pixie(self):
        # (900 + 400) * 3 // 2 = 1950
        self.assertEqual(_training_cost(PlayerClass.WIZARD, PlayerRace.PIXIE), 1950)


class TestPurchase(unittest.IsolatedAsyncioTestCase):
    def _player(self, gold=2000):
        player = Player(name='Rulan')
        player.char_class = PlayerClass.PALADIN
        player.char_race = PlayerRace.HUMAN
        from base_classes import PlayerMoneyTypes
        player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, gold)
        return player

    async def test_successful_purchase_sets_flag_and_deducts_gold(self):
        player = self._player(gold=2000)
        ctx = _FakeCtx(['Y'], player)
        await school_main(ctx)

        self.assertTrue(player.query_flag(PlayerFlags.SHIELD_TRAINED))
        from base_classes import PlayerMoneyTypes
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 800)
        self.assertIn('Odin', ctx._flat())

    async def test_declining_leaves_flag_and_gold_untouched(self):
        player = self._player(gold=2000)
        ctx = _FakeCtx(['N'], player)
        await school_main(ctx)

        self.assertFalse(player.query_flag(PlayerFlags.SHIELD_TRAINED))
        from base_classes import PlayerMoneyTypes
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 2000)

    async def test_insufficient_gold_is_rejected_before_prompting(self):
        player = self._player(gold=100)
        ctx = _FakeCtx([], player)
        await school_main(ctx)

        self.assertFalse(player.query_flag(PlayerFlags.SHIELD_TRAINED))
        self.assertIn('Ye do not have enough gold.', ctx._flat())

    async def test_already_trained_short_circuits(self):
        player = self._player(gold=2000)
        player.set_flag(PlayerFlags.SHIELD_TRAINED)
        ctx = _FakeCtx([], player)
        await school_main(ctx)
        self.assertIn('already has shield training', ctx._flat())


class TestShoppeDispatch(unittest.IsolatedAsyncioTestCase):
    """shoppe/main.py recognizes the free-text 'school' command word ahead
    of its single-letter menu-key truncation, same as 'locker'."""

    async def test_school_command_enters_school(self):
        from shoppe.main import _shoppe_session

        player = Player(name='Rulan')
        player.char_class = PlayerClass.PALADIN
        player.char_race = PlayerRace.HUMAN
        player.set_flag(PlayerFlags.EXPERT_MODE)
        ctx = _FakeCtx(['school', 'N', 'x'], player)
        await _shoppe_session(ctx, player)
        self.assertIn('Cost for your Race/Class combo', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
