"""tests/test_ready.py

Unit tests for commands/ready.py's two SPUR.WEAPON.S mechanics added this
session (no test file existed for ReadyCommand before):

  - Excalibur (#17): Knight class + honor >= 1200 gate. Below the bar,
    rejection blast (same shape as a STORM weapon refusing an unfit class).
    At/above the bar, unique "fiery sheen" flavor text and a normal ready.
  - Death Amulet (#56, matched by name): a Y/N gamble -- 20% instant death,
    reduced to 10% if carrying the Amulet of Life (#76).

Run with:
    python -m pytest tests/test_ready.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import sys, types
nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from base_classes import PlayerClass
from commands.ready import ReadyCommand
from inventory import Inventory
from items import Item, ItemCategory


def _weapon(name, item_id=1, **kwargs):
    return Item(id_number=item_id, name=name, category=ItemCategory.WEAPON,
                stability=kwargs.pop('stability', 10),
                to_hit=kwargs.pop('to_hit', 50),
                weapon_class=kwargs.pop('weapon_class', None),
                **kwargs)


class _FakePlayer:
    def __init__(self, char_class=PlayerClass.FIGHTER, honor=1000, str_stat=10,
                 weapons=None, extra_items=None, is_expert=False):
        self.char_class = char_class
        self.honor = honor
        self.stats = {'Strength': str_stat}
        self.hit_points = 30
        self.readied_weapon = None
        self.storm_servant_bonus = None
        self.weapon_experience = {}
        self.unsaved_changes = False
        self.is_expert = is_expert
        self.inventory = Inventory()
        for w in (weapons or []):
            self.inventory.add(w)
        for it in (extra_items or []):
            self.inventory.add(it)


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self._sent: list[str] = []
        self._answers = iter([])

    def set_answers(self, answers):
        self._answers = iter(answers)

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def prompt(self, *a, **kw):
        return next(self._answers, None)

    def sent(self) -> str:
        return '\n'.join(self._sent)


class TestExcaliburGate(unittest.IsolatedAsyncioTestCase):

    async def test_non_knight_rejected(self):
        excalibur = _weapon('EXCALIBUR', item_id=17)
        player = _FakePlayer(char_class=PlayerClass.FIGHTER, honor=2000, weapons=[excalibur])
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'excalibur')
        self.assertIn('YOU ARE NOT MINE', ctx.sent())
        self.assertIsNone(player.readied_weapon)

    async def test_knight_below_honor_threshold_rejected(self):
        excalibur = _weapon('EXCALIBUR', item_id=17)
        player = _FakePlayer(char_class=PlayerClass.KNIGHT, honor=1199, weapons=[excalibur])
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'excalibur')
        self.assertIn('YOU ARE NOT MINE', ctx.sent())
        self.assertIsNone(player.readied_weapon)

    async def test_rejection_can_be_fatal(self):
        excalibur = _weapon('EXCALIBUR', item_id=17)
        player = _FakePlayer(char_class=PlayerClass.FIGHTER, honor=0, weapons=[excalibur])
        player.hit_points = 1
        ctx = _FakeCtx(player)
        with patch('commands.ready.random.randint', return_value=10):
            await ReadyCommand().execute(ctx, 'excalibur')
        self.assertEqual(player.hit_points, 0)
        self.assertIn('perished', ctx.sent().lower())

    async def test_knight_at_honor_threshold_succeeds_with_flavor(self):
        excalibur = _weapon('EXCALIBUR', item_id=17)
        player = _FakePlayer(char_class=PlayerClass.KNIGHT, honor=1200, weapons=[excalibur])
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'excalibur')
        self.assertIn('fiery sheen', ctx.sent())
        self.assertIs(player.readied_weapon, excalibur)

    async def test_worthy_knight_above_threshold_succeeds(self):
        excalibur = _weapon('EXCALIBUR', item_id=17)
        player = _FakePlayer(char_class=PlayerClass.KNIGHT, honor=5000, weapons=[excalibur])
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'excalibur')
        self.assertIs(player.readied_weapon, excalibur)
        self.assertIn('READIED', ctx.sent())


class TestDeathAmuletGamble(unittest.IsolatedAsyncioTestCase):

    async def test_declining_the_gamble_leaves_weapon_unreadied(self):
        amulet = _weapon('DEATH AMULET', item_id=56, stability=50)
        player = _FakePlayer(weapons=[amulet])
        ctx = _FakeCtx(player)
        ctx.set_answers(['N'])
        await ReadyCommand().execute(ctx, 'death amulet')
        self.assertIn('WARNING', ctx.sent())
        self.assertIsNone(player.readied_weapon)

    async def test_survives_gamble_and_readies(self):
        amulet = _weapon('DEATH AMULET', item_id=56, stability=50)
        player = _FakePlayer(weapons=[amulet])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        with patch('commands.ready.random.random', return_value=0.99):   # >= 0.20 -> survive
            await ReadyCommand().execute(ctx, 'death amulet')
        self.assertIn('YOU LIVE', ctx.sent())
        self.assertIs(player.readied_weapon, amulet)

    async def test_dies_from_gamble(self):
        amulet = _weapon('DEATH AMULET', item_id=56, stability=50)
        player = _FakePlayer(weapons=[amulet])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        with patch('commands.ready.random.random', return_value=0.01):   # < 0.20 -> death
            await ReadyCommand().execute(ctx, 'death amulet')
        self.assertIn('TORN TO PIECES', ctx.sent())
        self.assertEqual(player.hit_points, 0)
        self.assertIsNone(player.readied_weapon)

    async def test_amulet_of_life_shown_in_warning(self):
        amulet = _weapon('DEATH AMULET', item_id=56, stability=50)
        amulet_of_life = Item(id_number=76, name='AMULET OF LIFE', category=ItemCategory.ITEM)
        player = _FakePlayer(weapons=[amulet], extra_items=[amulet_of_life])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        with patch('commands.ready.random.random', return_value=0.99):
            await ReadyCommand().execute(ctx, 'death amulet')
        self.assertIn('AMULET OF LIFE reduces this to 10%', ctx.sent())

    async def test_amulet_of_life_survives_a_roll_that_would_otherwise_kill(self):
        # 0.15 is death territory at the normal 20%, but survival territory
        # once the Amulet of Life drops the odds to 10%.
        amulet = _weapon('DEATH AMULET', item_id=56, stability=50)
        amulet_of_life = Item(id_number=76, name='AMULET OF LIFE', category=ItemCategory.ITEM)
        player = _FakePlayer(weapons=[amulet], extra_items=[amulet_of_life])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        with patch('commands.ready.random.random', return_value=0.15):
            await ReadyCommand().execute(ctx, 'death amulet')
        self.assertIn('YOU LIVE', ctx.sent())
        self.assertIs(player.readied_weapon, amulet)

    async def test_no_amulet_of_life_keeps_death_chance_at_20_percent(self):
        amulet = _weapon('DEATH AMULET', item_id=56, stability=50)
        player = _FakePlayer(weapons=[amulet])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        with patch('commands.ready.random.random', return_value=0.15):   # death at 20%, not at 10%
            await ReadyCommand().execute(ctx, 'death amulet')
        self.assertIn('TORN TO PIECES', ctx.sent())


class TestBestTargetsExpertGating(unittest.IsolatedAsyncioTestCase):
    """The '[ Best targets ]' hint (combat/resolution.py's hit_threshold()
    table, described in plain English) is shown to non-expert players and
    hidden for expert players, matching the rest of the codebase's
    convention of terser output once a player knows the ropes."""

    async def test_non_expert_sees_best_targets(self):
        sword = _weapon('LONG SWORD', item_id=2, weapon_class='hack_slash_bash')
        player = _FakePlayer(weapons=[sword], is_expert=False)
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'sword')
        self.assertIn('Best targets', ctx.sent())

    async def test_expert_does_not_see_best_targets(self):
        sword = _weapon('LONG SWORD', item_id=2, weapon_class='hack_slash_bash')
        player = _FakePlayer(weapons=[sword], is_expert=True)
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'sword')
        self.assertNotIn('Best targets', ctx.sent())
        self.assertIn('Weapon class', ctx.sent())

    async def test_best_targets_is_its_own_line(self):
        """'[ Best targets ]' must be a separate ctx.send() list element,
        not glued onto 'Weapon class: X' with an embedded '\\n' -- the
        rest of the pipeline (word-wrap, pagination) works in terms of
        one string per line."""
        sword = _weapon('LONG SWORD', item_id=2, weapon_class='hack_slash_bash')
        player = _FakePlayer(weapons=[sword], is_expert=False)
        ctx = _FakeCtx(player)
        await ReadyCommand().execute(ctx, 'sword')
        weapon_class_lines = [l for l in ctx._sent if l.startswith('Weapon class:')]
        best_target_lines  = [l for l in ctx._sent if 'Best targets' in l]
        self.assertEqual(len(weapon_class_lines), 1)
        self.assertEqual(len(best_target_lines), 1)
        self.assertNotIn('\n', weapon_class_lines[0])
        self.assertNotIn('\n', best_target_lines[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
