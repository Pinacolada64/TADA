"""tests/combat/test_monster_spellcasting.py

Covers combat/monster_spells.py (the trigger+dispatch, ported directly
from SPUR.COMBAT.S's m.attack cast-trigger check and SPUR.MISC4.S's
mon.cst) and its wiring into combat/engine.py's CombatSession. Wires up
monsters.json's cast_one_spell ('+') / cast_multiple_spells ('++') flags,
which existed in monsters.py's flag table but had no behavior anywhere
before this.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from combat.engine import CombatSession
from combat.monster_spells import monster_casts_spell
from combat.resolution import MonsterAttackResult


def run(coro):
    return asyncio.run(coro)


def _monster(name='WITCH', hp=20, multi=False, one=True):
    flags = {}
    if one:
        flags['cast_one_spell'] = True
    if multi:
        flags['cast_multiple_spells'] = True
    return {'name': name, 'number': 42, 'strength': hp, 'flags': flags}


def _player(xp_level=1):
    p = MagicMock()
    p.xp_level = xp_level
    return p


class TestTriggerGating(unittest.TestCase):
    def test_unflagged_monster_never_casts(self):
        monster = {'name': 'GOBLIN', 'strength': 1, 'flags': {}}
        with patch('combat.monster_spells.random.randint', return_value=10):
            result = monster_casts_spell(monster, _player(), set())
        self.assertIsNone(result)

    def test_low_hp_single_caster_triggers(self):
        # ms=1: trigger roll z=1 -> ms(1) < z+3(4) is True regardless of
        # the high-roll branch.
        monster = _monster(hp=1, multi=False)
        with patch('combat.monster_spells.random.randint', return_value=1):
            result = monster_casts_spell(monster, _player(), set())
        self.assertIsNotNone(result)

    def test_high_roll_single_caster_triggers(self):
        # ms=100 (never HP-triggers): z=10 > 8 triggers on the roll alone.
        monster = _monster(hp=100, multi=False)
        with patch('combat.monster_spells.random.randint', return_value=10):
            result = monster_casts_spell(monster, _player(), set())
        self.assertIsNotNone(result)

    def test_mid_roll_healthy_single_caster_does_not_trigger(self):
        # ms=100, z=5: neither ms<z+3 (100<8, false) nor z>8 (false).
        monster = _monster(hp=100, multi=False)
        with patch('combat.monster_spells.random.randint', return_value=5):
            result = monster_casts_spell(monster, _player(), set())
        self.assertIsNone(result)

    def test_multi_caster_has_an_easier_trigger_bar(self):
        # ms=100, z=7: single-caster wouldn't trigger (7 is not >8, and
        # 100 is not < 10), but ++ monsters trigger on z>6.
        monster = _monster(hp=100, multi=True)
        with patch('combat.monster_spells.random.randint', return_value=7):
            result = monster_casts_spell(monster, _player(), set())
        self.assertIsNotNone(result)


class TestEndurance(unittest.TestCase):
    def test_heals_the_monster_by_five_times_xp_level(self):
        monster = _monster(hp=1, multi=False)  # guarantees trigger
        player = _player(xp_level=3)
        # First roll (trigger) -> 1; second roll (dispatch) -> 1 (z<3 -> endurance).
        with patch('combat.monster_spells.random.randint', side_effect=[1, 1]):
            result = monster_casts_spell(monster, player, set())
        self.assertEqual(result.spell_cast, 'endurance')
        self.assertEqual(result.monster_heal, 15)

    def test_marks_spells_used_and_only_fires_once(self):
        monster = _monster(hp=1, multi=False)
        player = _player(xp_level=1)
        spells_used = set()
        with patch('combat.monster_spells.random.randint', side_effect=[1, 1]):
            result = monster_casts_spell(monster, player, spells_used)
        self.assertEqual(result.spell_cast, 'endurance')
        self.assertIn('end', spells_used)

        # Second attempt: 'end' already used, single-caster has no 'end2' --
        # falls through to Destroy instead (also fresh this encounter).
        with patch('combat.monster_spells.random.randint', side_effect=[1, 1]):
            result2 = monster_casts_spell(monster, player, spells_used)
        self.assertEqual(result2.spell_cast, 'destroy')

    def test_multi_caster_gets_a_second_endurance_use_with_bonus(self):
        monster = _monster(hp=1, multi=True)
        player = _player(xp_level=2)
        spells_used = {'end'}  # first use already spent
        # trigger roll high enough, dispatch z=1 -> first branch already
        # blocked by 'end' in spells_used, falls to the ++ 'end2' branch
        # (z+7>ms is true for any ms this low).
        with patch('combat.monster_spells.random.randint', side_effect=[7, 1]):
            result = monster_casts_spell(monster, player, spells_used)
        self.assertEqual(result.spell_cast, 'endurance')
        self.assertEqual(result.monster_heal, 5 * 2 + 2 * 2)
        self.assertIn('end2', spells_used)

    def test_multi_casters_very_first_endurance_cast_also_gets_the_bonus(self):
        """SPUR has one shared 'endrnce' formula -- the ++ bonus applies
        to every cast by a multi-caster, not just a "second" one. Guards
        against reintroducing the bug where the first cast was modeled
        with the un-bonused base formula."""
        monster = _monster(hp=1, multi=True)
        player = _player(xp_level=2)
        with patch('combat.monster_spells.random.randint', side_effect=[1, 1]):
            result = monster_casts_spell(monster, player, set())
        self.assertEqual(result.spell_cast, 'endurance')
        self.assertEqual(result.monster_heal, 5 * 2 + 2 * 2)


class TestDestroy(unittest.TestCase):
    def test_damage_formula(self):
        monster = _monster(hp=1, multi=False)
        player = _player()
        spells_used = {'end'}  # skip straight to Destroy
        # dispatch z=6 -> (6//2)+1+4 = 8
        with patch('combat.monster_spells.random.randint', side_effect=[1, 6]):
            result = monster_casts_spell(monster, player, spells_used)
        self.assertEqual(result.spell_cast, 'destroy')
        self.assertTrue(result.hit)
        self.assertEqual(result.damage, 8)
        self.assertIn('dest', spells_used)

    def test_multi_caster_gets_a_second_destroy_use_with_bonus(self):
        monster = _monster(hp=1, multi=True)
        player = _player()
        spells_used = {'end', 'end2', 'dest'}
        with patch('combat.monster_spells.random.randint', side_effect=[7, 6]):
            result = monster_casts_spell(monster, player, spells_used)
        self.assertEqual(result.spell_cast, 'destroy')
        self.assertEqual(result.damage, 10)  # (6//2)+1+4+2
        self.assertIn('dest2', spells_used)

    def test_multi_casters_very_first_destroy_cast_also_gets_the_bonus(self):
        """SPUR has one shared 'destroy' formula -- same reasoning as
        the equivalent Endurance test above."""
        monster = _monster(hp=1, multi=True)
        player = _player()
        spells_used = {'end', 'end2'}  # skip straight to Destroy
        with patch('combat.monster_spells.random.randint', side_effect=[7, 6]):
            result = monster_casts_spell(monster, player, spells_used)
        self.assertEqual(result.spell_cast, 'destroy')
        self.assertEqual(result.damage, 10)  # (6//2)+1+4+2, bonus on the FIRST use
        self.assertIn('dest', spells_used)
        self.assertNotIn('dest2', spells_used)

    def test_only_fires_once_for_a_single_caster(self):
        # All slots spent, trigger still fires -- SPUR wastes the whole
        # turn silently rather than falling back to a normal swing.
        monster = _monster(hp=1, multi=False)
        player = _player()
        spells_used = {'end', 'dest'}
        with patch('combat.monster_spells.random.randint', side_effect=[1, 5]):
            result = monster_casts_spell(monster, player, spells_used)
        self.assertEqual(result.spell_cast, 'wasted')


class TestTeleport(unittest.TestCase):
    def test_single_caster_never_teleports(self):
        monster = _monster(hp=1, multi=False)
        player = _player()
        spells_used = {'end', 'dest'}
        with patch('combat.monster_spells.random.randint', side_effect=[1, 5]):
            result = monster_casts_spell(monster, player, spells_used)
        self.assertNotEqual(result.spell_cast, 'teleport')

    def test_multi_caster_teleports_once_endurance_and_destroy_are_spent(self):
        monster = _monster(hp=1, multi=True)
        player = _player(xp_level=1)
        spells_used = {'end', 'end2', 'dest', 'dest2'}
        # trigger roll, dispatch roll (z=5 satisfies neither end/end2/dest
        # conditions once already used), teleport roll z2=5 -> triggers.
        with patch('combat.monster_spells.random.randint', side_effect=[7, 1, 5]):
            result = monster_casts_spell(monster, player, spells_used)
        self.assertEqual(result.spell_cast, 'teleport')

    def test_teleport_roll_can_fail_leaving_no_effect(self):
        monster = _monster(hp=100, multi=True)
        player = _player(xp_level=1)
        spells_used = {'end', 'end2', 'dest', 'dest2'}
        # teleport roll z2=1: neither (1+1+8>100) nor z2==5.
        with patch('combat.monster_spells.random.randint', side_effect=[7, 1, 1]):
            result = monster_casts_spell(monster, player, spells_used)
        self.assertEqual(result.spell_cast, 'wasted')


class TestWastedTurnRendersSilently(unittest.IsolatedAsyncioTestCase):
    """SPUR's own fallback (all slots spent, nothing left to cast) has no
    print statement at all -- the monster's turn is silently consumed by
    the failed cast attempt rather than falling back to a normal miss/
    swing message."""

    async def test_no_narration_and_no_damage(self):
        session = CombatSession(_monster(hp=10), room_no=1)
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()
        ctx.player = MagicMock()
        ctx.player.hit_points = 30
        result = MonsterAttackResult(hit=False, damage=0, spell_cast='wasted')
        await session._narrate_monster_swing(ctx, result)
        session._apply_monster_damage(ctx, result)
        ctx.send.assert_not_awaited()
        ctx.send_room.assert_not_awaited()
        self.assertEqual(ctx.player.hit_points, 30)
        self.assertEqual(session.monster['strength'], 10)


class TestEngineNarrationAndDamage(unittest.IsolatedAsyncioTestCase):
    def _ctx(self, player_name='Rulan'):
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()
        ctx.player = MagicMock()
        ctx.player.name = player_name
        ctx.player.hit_points = 30
        return ctx

    async def test_endurance_narration_and_monster_heal(self):
        session = CombatSession(_monster(hp=10), room_no=1)
        ctx = self._ctx()
        result = MonsterAttackResult(
            hit=False, damage=0, spell_cast='endurance', monster_heal=5,
            cast_narration=['WITCH casts an endurance spell, and gains strength!'],
        )
        await session._narrate_monster_swing(ctx, result)
        session._apply_monster_damage(ctx, result)
        self.assertIn('WITCH casts an endurance spell, and gains strength!',
                       [c.args[0] for c in ctx.send.await_args_list])
        self.assertEqual(session.monster['strength'], 15)

    async def test_destroy_narration_and_player_damage(self):
        session = CombatSession(_monster(hp=10), room_no=1)
        ctx = self._ctx()
        result = MonsterAttackResult(
            hit=True, damage=8, spell_cast='destroy',
            cast_narration=['WITCH casts a destroyer spell on you!', 'Zap! You take 8 hits!'],
        )
        await session._narrate_monster_swing(ctx, result)
        session._apply_monster_damage(ctx, result)
        self.assertEqual(ctx.player.hit_points, 22)

    async def test_destroy_damage_bypasses_shield_and_armor(self):
        session = CombatSession(_monster(hp=10), room_no=1)
        ctx = self._ctx()
        ctx.player.shield = 50
        ctx.player.armor = 50
        result = MonsterAttackResult(hit=True, damage=8, spell_cast='destroy',
                                      cast_narration=['x'])
        session._apply_monster_damage(ctx, result)
        self.assertEqual(ctx.player.shield, 50)
        self.assertEqual(ctx.player.armor, 50)

    async def test_teleport_ends_the_session_and_broadcasts(self):
        session = CombatSession(_monster(hp=10), room_no=1)
        ctx = self._ctx(player_name='Rulan')
        result = MonsterAttackResult(
            hit=False, damage=0, spell_cast='teleport',
            cast_narration=['WITCH casts a teleport spell on you!', 'The area fades from view..'],
        )
        await session._monster_teleports_player(ctx, result)
        self.assertTrue(session._done.is_set())
        sent = [c.args[0] for c in ctx.send.await_args_list]
        self.assertIn('WITCH casts a teleport spell on you!', sent)
        ctx.send_room.assert_awaited_once()
        args, kwargs = ctx.send_room.await_args
        self.assertIn('Rulan', args[0])
        self.assertTrue(kwargs.get('exclude_self'))


class TestDestroyBypassesNormalSwingSafetyNets(unittest.IsolatedAsyncioTestCase):
    """SPUR.MISC4.S's destroy branch applies hp=hp-z directly and exits
    (pop:goto c.return) -- it never reaches COMBAT.S's "lurk.a"/"dragon"
    section, which is where mount-redirect and sac.ally (ally death-save)
    actually live. A Destroy-spell hit should skip both, unlike a normal
    weapon swing's damage."""

    def _ctx(self):
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()
        ctx.player = MagicMock()
        ctx.player.name = 'Rulan'
        ctx.player.hit_points = 5  # low enough to qualify for death-save if checked
        return ctx

    async def test_destroy_does_not_check_mount_redirect(self):
        session = CombatSession(_monster(hp=10), room_no=1)
        ctx = self._ctx()
        result = MonsterAttackResult(hit=True, damage=8, spell_cast='destroy',
                                      cast_narration=['x'])
        with patch.object(session, '_try_redirect_to_mount',
                           new=AsyncMock(return_value=True)) as mock_redirect:
            await session._resolve_monster_hit(ctx, result)
        mock_redirect.assert_not_called()

    async def test_destroy_does_not_check_ally_death_save(self):
        session = CombatSession(_monster(hp=10), room_no=1)
        ctx = self._ctx()
        result = MonsterAttackResult(hit=True, damage=8, spell_cast='destroy',
                                      cast_narration=['x'])
        with patch('ally_events.try_ally_death_save',
                    new=AsyncMock(return_value=True)) as mock_save:
            await session._resolve_monster_hit(ctx, result)
        mock_save.assert_not_called()

    async def test_normal_hit_still_checks_mount_redirect(self):
        """Sanity check: the guard is specific to spell_cast, not a
        blanket regression that disables these checks entirely."""
        session = CombatSession(_monster(hp=10), room_no=1)
        ctx = self._ctx()
        result = MonsterAttackResult(hit=True, damage=8)  # no spell_cast
        with patch.object(session, '_try_redirect_to_mount',
                           new=AsyncMock(return_value=True)) as mock_redirect:
            await session._resolve_monster_hit(ctx, result)
        mock_redirect.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
