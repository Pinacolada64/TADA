"""tests/commands/test_cast.py

Covers commands/cast.py -- CastCommand, a faithful port of SPUR.MISC3.S's
`cast`/`cst.outc`/`cast.spl` labels (verified directly against source, see
that module's docstring). One test class per effect family, plus the
deferred/flavor-stub scope boundary and the Druid/staff bonus.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import spellbook
from base_classes import PlayerClass, PlayerMoneyTypes, PlayerRace, PlayerStat
from combat.engine import CombatSession
from commands.cast import CastCommand
from flags import PlayerFlags
from inventory import Inventory
from items import Spell
from player import Player


def _new_player(char_class=None, char_race=None, intelligence=15) -> Player:
    player = Player(name='Rulan', char_class=char_class, char_race=char_race)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.inventory = Inventory(capacity=14)
    player.stats[PlayerStat.INT] = intelligence
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 1_000)
    player.set_silver_absolute(PlayerMoneyTypes.IN_BANK, 0)
    return player


def _spell(number=1, name='ESP', effect_type='I', magnitude=4, cast_chance=90):
    return Spell(id_number=number, name=name, cast_chance=cast_chance,
                 effect_type=effect_type, effect_magnitude=magnitude,
                 charges=1, max_charges=1)


class _FakeCtx:
    def __init__(self, responses, player, room=1, active_combats=None):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.client = SimpleNamespace(room=room)
        self.server = SimpleNamespace(active_combats=active_combats or {})

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def send_room(self, *args, **kwargs):
        pass

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


async def _cast_first_known_spell(ctx):
    return await CastCommand().execute(ctx)


class TestNoSpellsKnown(unittest.IsolatedAsyncioTestCase):
    async def test_says_you_have_no_spells(self):
        player = _new_player(PlayerClass.WIZARD)
        ctx = _FakeCtx([], player)
        await _cast_first_known_spell(ctx)
        self.assertIn('You have no spells.', ctx._flat())


class TestSpellListing(unittest.IsolatedAsyncioTestCase):
    async def test_lists_a_known_spell_by_name(self):
        player = _new_player(PlayerClass.WIZARD)
        spellbook.ensure_spellbook(player).contents.add(_spell(), charges=1)
        ctx = _FakeCtx(['Q'], player)
        await _cast_first_known_spell(ctx)
        self.assertIn('ESP', ctx._flat())

    async def test_question_mark_relists(self):
        player = _new_player(PlayerClass.WIZARD)
        spellbook.ensure_spellbook(player).contents.add(_spell(), charges=1)
        ctx = _FakeCtx(['?', 'Q'], player)
        await _cast_first_known_spell(ctx)
        self.assertEqual(ctx._flat().count('Known Spells'), 2)

    async def test_unknown_number_refuses_and_reprompts(self):
        player = _new_player(PlayerClass.WIZARD)
        spellbook.ensure_spellbook(player).contents.add(_spell(), charges=1)
        ctx = _FakeCtx(['99', 'Q'], player)
        await _cast_first_known_spell(ctx)
        self.assertIn('You do not know that spell.', ctx._flat())


class TestOneShotConsumption(unittest.IsolatedAsyncioTestCase):
    async def test_spell_is_removed_regardless_of_outcome(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=3)  # near-certain fizzle/backfire
        spellbook.ensure_spellbook(player).contents.add(_spell(cast_chance=1), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', side_effect=[10000, 6]):  # forces fizzle
            await _cast_first_known_spell(ctx)
        self.assertEqual(spellbook.spell_entries(player), [])


class TestFizzleMessage(unittest.IsolatedAsyncioTestCase):
    """SPUR spl.fail: "Your spell fizzles..." plus a low-INT hint (ported
    with SPUR's own "Prehaps" typo corrected to "Perhaps")."""

    async def test_low_intelligence_gets_the_extra_hint(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=10)
        player.inventory.add(_spell(cast_chance=1), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', side_effect=[10000, 10]):  # forces fizzle
            await _cast_first_known_spell(ctx)
        self.assertIn('Your spell fizzles...', ctx._flat())
        self.assertIn('(Perhaps, if you were smarter..)', ctx._flat())

    async def test_high_intelligence_does_not_get_the_hint(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.inventory.add(_spell(cast_chance=1), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', side_effect=[10000, 10]):  # forces fizzle
            await _cast_first_known_spell(ctx)
        self.assertIn('Your spell fizzles...', ctx._flat())
        self.assertNotIn('smarter', ctx._flat())


class TestStatSpells(unittest.IsolatedAsyncioTestCase):
    async def test_success_raises_the_stat(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.stats[PlayerStat.STR] = 10
        spellbook_entries = player.inventory
        player.inventory.add(_spell(effect_type='S', magnitude=3, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):  # a=1.01 always < threshold
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.stats[PlayerStat.STR], 13)
        self.assertIn('Spell successful!', ctx._flat())

    async def test_intelligence_success_uses_spurs_exact_smart_line(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.stats[PlayerStat.INT] = 10
        player.inventory.add(_spell(effect_type='I', magnitude=3, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertIn('(You feel a bit smarter)', ctx._flat())

    async def test_backfire_lowers_the_stat(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=3)
        player.stats[PlayerStat.STR] = 10
        player.inventory.add(_spell(effect_type='S', magnitude=3, cast_chance=1), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', side_effect=[10000, 1]):  # fail roll, then <5: backfire
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.stats[PlayerStat.STR], 7)
        self.assertIn('Spell backfired!', ctx._flat())

    async def test_at_cap_success_roll_still_collapses_to_a_decrease(self):
        """Faithful to SPUR: a successful roll against an already-capped
        stat falls through to the backfire branch instead of doing
        nothing."""
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.stats[PlayerStat.STR] = 20  # already at the default cap
        player.inventory.add(_spell(effect_type='S', magnitude=3, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.stats[PlayerStat.STR], 17)
        self.assertIn('Spell backfired!', ctx._flat())

    async def test_ogre_strength_cap_is_24_not_20(self):
        player = _new_player(PlayerClass.FIGHTER, char_race=PlayerRace.OGRE, intelligence=20)
        player.stats[PlayerStat.STR] = 20
        player.inventory.add(_spell(effect_type='S', magnitude=3, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.stats[PlayerStat.STR], 23)  # raised, not collapsed

    async def test_human_energy_cap_is_24(self):
        player = _new_player(PlayerClass.FIGHTER, char_race=PlayerRace.HUMAN, intelligence=20)
        player.stats[PlayerStat.EGY] = 21
        player.inventory.add(_spell(effect_type='E', magnitude=2, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.stats[PlayerStat.EGY], 23)  # raised: 21+2 < 24 cap

    async def test_half_elf_energy_cap_is_22(self):
        player = _new_player(PlayerClass.FIGHTER, char_race=PlayerRace.HALF_ELF, intelligence=20)
        player.stats[PlayerStat.EGY] = 20  # below the 22 cap, above the default-20 cap
        player.inventory.add(_spell(effect_type='E', magnitude=1, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        # A non-Half-Elf at 20 (the default cap) would collapse to a
        # decrease here; the 22 cap lets this one actually succeed.
        self.assertEqual(player.stats[PlayerStat.EGY], 21)


class TestHealSpell(unittest.IsolatedAsyncioTestCase):
    async def test_heals_under_the_cap(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.xp_level = 1
        player.hit_points = 10  # cap = 23 + 1 = 24
        player.inventory.add(_spell(effect_type='P', magnitude=5, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.hit_points, 15)
        self.assertIn('Spell successful!', ctx._flat())

    async def test_backfire_subtracts(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=3)
        player.hit_points = 10
        player.inventory.add(_spell(effect_type='P', magnitude=5, cast_chance=1), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', side_effect=[10000, 1]):
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.hit_points, 5)
        self.assertIn('Spell backfired!', ctx._flat())

    async def test_at_or_above_cap_success_roll_collapses_to_a_decrease(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.xp_level = 1
        player.hit_points = 24  # already at cap (23+1)
        player.inventory.add(_spell(effect_type='P', magnitude=5, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.hit_points, 19)
        self.assertIn('Spell backfired!', ctx._flat())


class TestTransferSpell(unittest.IsolatedAsyncioTestCase):
    async def test_success_moves_hand_silver_to_bank(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 500)
        player.set_silver_absolute(PlayerMoneyTypes.IN_BANK, 0)
        player.inventory.add(_spell(effect_type='T', magnitude=0, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 0)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_BANK), 500)

    async def test_backfire_moves_bank_silver_to_hand(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=3)
        player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 100)
        player.set_silver_absolute(PlayerMoneyTypes.IN_BANK, 500)
        player.inventory.add(_spell(effect_type='T', magnitude=0, cast_chance=1), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', side_effect=[10000, 1]):
            await _cast_first_known_spell(ctx)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 600)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_BANK), 0)


def _monster(name='GOBLIN', hp=20, flags=None):
    return {'name': name, 'number': 42, 'strength': hp, 'flags': flags or {}}


class TestMonsterDamageSpell(unittest.IsolatedAsyncioTestCase):
    async def test_refuses_without_an_active_combat_session(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.inventory.add(_spell(effect_type='M', magnitude=5, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)  # no active_combats entry
        await _cast_first_known_spell(ctx)
        self.assertIn("You'll need to be in combat first.", ctx._flat())
        # Not consumed -- refused before the one-shot spend.
        self.assertEqual(len(player.inventory.entries('Spell')), 1)

    async def test_damages_the_monster_on_success(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.inventory.add(_spell(effect_type='M', magnitude=5, cast_chance=90), charges=1)
        session = CombatSession(_monster(hp=20), room_no=1)
        ctx = _FakeCtx(['1'], player, active_combats={1: session})
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertEqual(session.monster['strength'], 15)
        self.assertIn('Spell successful!', ctx._flat())

    async def test_kills_the_monster_when_hp_drops_to_zero(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.inventory.add(_spell(effect_type='M', magnitude=50, cast_chance=90), charges=1)
        session = CombatSession(_monster(hp=20), room_no=1)
        ctx = _FakeCtx(['1'], player, active_combats={1: session})
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertTrue(session._done.is_set())
        self.assertIn('You have slain the GOBLIN!', ctx._flat())

    async def test_mechanical_monster_blocks_the_spell(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.inventory.add(_spell(effect_type='M', magnitude=5, cast_chance=90), charges=1)
        session = CombatSession(_monster(flags={'mechanical': True}), room_no=1)
        ctx = _FakeCtx(['1'], player, active_combats={1: session})
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertIn('Mechanical devices are unaffected by magic!', ctx._flat())
        self.assertEqual(session.monster['strength'], 20)  # untouched

    async def test_magic_resistant_monster_blocks_the_spell(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.inventory.add(_spell(effect_type='M', magnitude=5, cast_chance=90), charges=1)
        session = CombatSession(_monster(flags={'magic_resistant': True}), room_no=1)
        ctx = _FakeCtx(['1'], player, active_combats={1: session})
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertIn('sneers at your feats of magic.', ctx._flat())

    async def test_non_wizard_backfire_heals_the_monster(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=3)
        player.inventory.add(_spell(effect_type='M', magnitude=5, cast_chance=1), charges=1)
        session = CombatSession(_monster(hp=20), room_no=1)
        ctx = _FakeCtx(['1'], player, active_combats={1: session})
        with patch('commands.cast.random.randint', side_effect=[10000, 1]):
            await _cast_first_known_spell(ctx)
        self.assertEqual(session.monster['strength'], 25)
        self.assertIn('stronger!', ctx._flat())

    async def test_wizard_gets_xp_and_staff_blast_bonus(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        player.readied_weapon = SimpleNamespace(id_number=3)  # WOOD STAFF
        player.inventory.add(_spell(effect_type='M', magnitude=5, cast_chance=90), charges=1)
        session = CombatSession(_monster(hp=30), room_no=1)
        ctx = _FakeCtx(['1'], player, active_combats={1: session})
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertIn('Power BLASTS from the staff!', ctx._flat())
        self.assertEqual(player.experience, 5)
        self.assertEqual(session.monster['strength'], 30 - 5 - 4)  # magnitude + staff M-bonus

    async def test_wizard_backfire_still_damages_rather_than_healing(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=3)
        player.inventory.add(_spell(effect_type='M', magnitude=5, cast_chance=1), charges=1)
        session = CombatSession(_monster(hp=30), room_no=1)
        ctx = _FakeCtx(['1'], player, active_combats={1: session})
        with patch('commands.cast.random.randint', side_effect=[10000, 1]):
            await _cast_first_known_spell(ctx)
        self.assertEqual(session.monster['strength'], 25)  # damaged, not healed


class TestDeferredEffectTypes(unittest.IsolatedAsyncioTestCase):
    async def test_level_up_is_refused_and_not_consumed(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='U', name='ELEVATOR UP'), charges=1)
        ctx = _FakeCtx(['1'], player)
        await _cast_first_known_spell(ctx)
        self.assertIn("hasn't taught anyone how to unlock", ctx._flat())
        self.assertEqual(len(spellbook.spell_entries(player)), 1)

    async def test_level_down_is_refused_and_not_consumed(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='L', name='ELEVATOR DOWN'), charges=1)
        ctx = _FakeCtx(['1'], player)
        await _cast_first_known_spell(ctx)
        self.assertEqual(len(spellbook.spell_entries(player)), 1)

    async def test_teleport_to_shoppe_is_refused_and_not_consumed(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='R', name='TRANSPORT TO SHOPPE'), charges=1)
        ctx = _FakeCtx(['1'], player)
        await _cast_first_known_spell(ctx)
        self.assertEqual(len(spellbook.spell_entries(player)), 1)

    async def test_wizards_glow_aura_is_refused_and_not_consumed(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='A', name="WIZARD'S GLOW"), charges=1)
        ctx = _FakeCtx(['1'], player)
        await _cast_first_known_spell(ctx)
        self.assertEqual(len(spellbook.spell_entries(player)), 1)

    async def test_dispel_poison_aura_is_refused_and_not_consumed(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='A', name='DISPEL POISON'), charges=1)
        ctx = _FakeCtx(['1'], player)
        await _cast_first_known_spell(ctx)
        self.assertEqual(len(spellbook.spell_entries(player)), 1)


class TestFlavorStubbedEffectTypes(unittest.IsolatedAsyncioTestCase):
    async def test_summon_spur_is_consumed_and_rolls_normally(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='G', name='SUMMON SPUR', cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertEqual(spellbook.spell_entries(player), [])
        self.assertIn('Spell successful!', ctx._flat())
        self.assertIn('does not answer your call', ctx._flat())

    async def test_boots_of_speed_aura_is_consumed_and_rolls_normally(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='A', name='BOOTS OF SPEED', cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertEqual(spellbook.spell_entries(player), [])
        self.assertIn('burst of speed', ctx._flat())


class TestCasterBonuses(unittest.IsolatedAsyncioTestCase):
    async def test_druid_gets_a_bonus_on_stat_spells(self):
        player = _new_player(PlayerClass.DRUID, intelligence=20)
        player.stats[PlayerStat.STR] = 10
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='S', magnitude=3, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertIn('DRUID POWER!', ctx._flat())
        self.assertEqual(player.stats[PlayerStat.STR], 15)  # 10 + 3 magnitude + 2 bonus

    async def test_druid_gets_no_bonus_on_monster_damage(self):
        player = _new_player(PlayerClass.DRUID, intelligence=20)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='M', magnitude=5, cast_chance=90), charges=1)
        session = CombatSession(_monster(hp=30), room_no=1)
        ctx = _FakeCtx(['1'], player, active_combats={1: session})
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertNotIn('DRUID POWER!', ctx._flat())
        self.assertEqual(session.monster['strength'], 25)  # no bonus applied

    async def test_wizard_with_staff_gets_a_stat_spell_bonus(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        player.readied_weapon = SimpleNamespace(id_number=47)  # STORM STAFF
        player.stats[PlayerStat.INT] = 10
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='I', magnitude=3, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertIn('The staff trembles..', ctx._flat())
        self.assertEqual(player.stats[PlayerStat.INT], 14)  # 10 + 3 + 1 bonus

    async def test_wizard_without_a_staff_gets_no_bonus(self):
        player = _new_player(PlayerClass.WIZARD, intelligence=20)
        player.stats[PlayerStat.INT] = 10
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_spell(effect_type='I', magnitude=3, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertNotIn('The staff trembles..', ctx._flat())
        self.assertEqual(player.stats[PlayerStat.INT], 13)  # 10 + 3, no bonus

    async def test_non_wizard_readying_a_staff_gets_no_bonus(self):
        player = _new_player(PlayerClass.FIGHTER, intelligence=20)
        player.readied_weapon = SimpleNamespace(id_number=3)
        player.stats[PlayerStat.STR] = 10
        player.inventory.add(_spell(effect_type='S', magnitude=3, cast_chance=90), charges=1)
        ctx = _FakeCtx(['1'], player)
        with patch('commands.cast.random.randint', return_value=1):
            await _cast_first_known_spell(ctx)
        self.assertNotIn('The staff trembles..', ctx._flat())
        self.assertEqual(player.stats[PlayerStat.STR], 13)


if __name__ == '__main__':
    unittest.main()
