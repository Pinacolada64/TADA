"""tests/commands/test_spell_cast_chance.py

Covers the remembered, practice-raised cast % (player.spell_cast_chance,
spellbook.py's cast_chance()/record_successful_cast()): it belongs to the
player rather than any one scroll, every successful CAST raises it, a
failure never lowers it, and INV / CAST / the Wizard's cave all show it.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import spellbook
from base_classes import PlayerClass, PlayerMoneyTypes, PlayerStat
from commands.cast import CastCommand
from commands.inv import _container_lines, _format_entry
from flags import PlayerFlags
from inventory import Inventory
from items import Spell
from player import Player
from shoppe.wizard import main as wizard_main


def _new_player(char_class=PlayerClass.WIZARD, intelligence=20) -> Player:
    player = Player(name='Rulan', char_class=char_class)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.inventory = Inventory(capacity=14)
    player.stats[PlayerStat.INT] = intelligence
    player.stats[PlayerStat.STR] = 10
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 10_000)
    return player


def _wheaties(cast_chance=70):
    return Spell(id_number=2, name='WHEATIES', cast_chance=cast_chance,
                 effect_type='S', effect_magnitude=1, charges=1, max_charges=1)


class _FakeCtx:
    def __init__(self, player, responses=('1',)):
        self.player = player
        self._q = list(responses)
        self.sent: list = []
        self.client = SimpleNamespace(room=1)
        self.server = SimpleNamespace(active_combats={}, items=[])

    async def send(self, *args):
        for a in args:
            self.sent.extend(a if isinstance(a, list) else [a])

    async def send_room(self, line, exclude_self=False):
        pass

    async def prompt(self, prompt_text='', preamble_lines=None):
        return self._q.pop(0) if self._q else None

    def flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


async def _cast(player, roll):
    spellbook.ensure_spellbook(player).contents.add(_wheaties())
    ctx = _FakeCtx(player)
    with patch('commands.cast.random.randint', **roll):
        await CastCommand().execute(ctx)
    return ctx


_SUCCESS  = {'return_value': 1}
_BACKFIRE = {'side_effect': [10000, 1]}
_FIZZLE   = {'side_effect': [10000, 10]}


class TestRememberedCastChance(unittest.TestCase):
    def test_unpractised_spell_uses_its_own_base_chance(self):
        self.assertEqual(spellbook.cast_chance(_new_player(), _wheaties(70)), 70)

    def test_success_raises_it_by_the_step(self):
        player = _new_player()
        old, new = spellbook.record_successful_cast(player, _wheaties(70))
        self.assertEqual((old, new), (70, 70 + spellbook.CAST_CHANCE_STEP))
        self.assertEqual(player.spell_cast_chance, {'2': 72})
        self.assertTrue(player.unsaved_changes)

    def test_capped(self):
        player = _new_player()
        player.spell_cast_chance = {'2': 98}
        self.assertEqual(spellbook.record_successful_cast(player, _wheaties())[1], 99)
        self.assertEqual(spellbook.record_successful_cast(player, _wheaties()), (99, 99))

    def test_a_new_copy_of_the_spell_remembers_it(self):
        player = _new_player()
        spellbook.record_successful_cast(player, _wheaties(70))
        self.assertEqual(spellbook.cast_chance(player, _wheaties(70)), 72)

    def test_never_below_the_spells_own_base(self):
        player = _new_player()
        player.spell_cast_chance = {'2': 40}
        self.assertEqual(spellbook.cast_chance(player, _wheaties(70)), 70)


class TestCastingRaisesIt(unittest.IsolatedAsyncioTestCase):
    async def test_successful_cast_raises_and_announces_it(self):
        player = _new_player()
        ctx = await _cast(player, _SUCCESS)
        self.assertEqual(player.spell_cast_chance, {'2': 72})
        self.assertIn('(Your skill with WHEATIES improves: 72% to cast.)', ctx.flat())

    async def test_backfire_does_not_lower_it(self):
        player = _new_player()
        player.spell_cast_chance = {'2': 80}
        await _cast(player, _BACKFIRE)
        self.assertEqual(player.spell_cast_chance, {'2': 80})

    async def test_fizzle_does_not_lower_it(self):
        player = _new_player()
        player.spell_cast_chance = {'2': 80}
        await _cast(player, _FIZZLE)
        self.assertEqual(player.spell_cast_chance, {'2': 80})

    async def test_it_survives_the_spell_being_used_up(self):
        player = _new_player()
        await _cast(player, _SUCCESS)
        self.assertEqual(spellbook.spell_entries(player), [])  # scroll gone
        self.assertEqual(player.spell_cast_chance, {'2': 72})  # practice kept

    async def test_aura_on_a_lost_roll_does_not_count_as_practice(self):
        from survival import apply_poison
        player = _new_player()
        apply_poison(player)
        spellbook.ensure_spellbook(player).contents.add(
            Spell(id_number=16, name='DISPEL POISON', cast_chance=90, effect_type='A',
                  effect_magnitude=5, charges=1, max_charges=1))
        ctx = _FakeCtx(player)
        with patch('commands.cast.random.randint', side_effect=[10000, 1]):
            await CastCommand().execute(ctx)
        self.assertIn('Spell successful!', ctx.flat())  # aura still took effect
        self.assertEqual(player.spell_cast_chance, {})

    async def test_the_roll_uses_the_remembered_chance(self):
        player = _new_player()
        player.spell_cast_chance = {'2': 95}
        spellbook.ensure_spellbook(player).contents.add(_wheaties(10))
        with patch('commands.cast._roll_outcome', return_value='fizzle') as roll:
            await CastCommand().execute(_FakeCtx(player))
        self.assertEqual(roll.call_args.args[1], 95)

    async def test_cast_list_shows_the_remembered_chance(self):
        player = _new_player()
        player.spell_cast_chance = {'2': 84}
        spellbook.ensure_spellbook(player).contents.add(_wheaties(70))
        ctx = _FakeCtx(player, responses=['Q'])
        await CastCommand().execute(ctx)
        self.assertIn('84%', ctx.flat())


class TestInventoryShowsIt(unittest.TestCase):
    def test_loose_spell_line(self):
        player = _new_player(PlayerClass.FIGHTER)
        player.spell_cast_chance = {'2': 76}
        player.inventory.add(_wheaties(70))
        entry = player.inventory.entries('Spell')[0]
        self.assertIn('cast: 76%', _format_entry(entry, 1, player=player))
        self.assertIn('cast: 70%', _format_entry(entry, 1))  # no player: base value

    def test_spell_book_pages(self):
        player = _new_player()
        player.spell_cast_chance = {'2': 76}
        book = spellbook.ensure_spellbook(player)
        book.contents.add(_wheaties(70))
        self.assertEqual(_container_lines(book, player),
                         ['         > WHEATIES (cast: 76%)'])


class TestWizardsCaveShowsIt(unittest.IsolatedAsyncioTestCase):
    async def test_info_shows_the_players_cast_chance(self):
        player = _new_player()
        player.spell_cast_chance = {'2': 88}
        ctx = _FakeCtx(player, responses=['Y', 'i2', 'Q'])
        await wizard_main(ctx)
        self.assertIn('  Cast    : 88%', ctx.sent)

    async def test_wide_screen_list_has_a_cast_column(self):
        player = _new_player()
        player.client_settings.screen_columns = 80
        ctx = _FakeCtx(player, responses=['Y', 'Q'])
        await wizard_main(ctx)
        self.assertIn('Cast', ctx.flat())

    async def test_forty_column_list_stays_forty_wide(self):
        player = _new_player()
        player.client_settings.screen_columns = 40
        ctx = _FakeCtx(player, responses=['Y', 'Q'])
        await wizard_main(ctx)
        table = [line for line in ctx.sent
                 if isinstance(line, str) and any(bar in line for bar in '|│║')]
        self.assertTrue(table)
        self.assertLessEqual(max(map(len, table)), 40)


def test_survives_a_relogin(tmp_path, monkeypatch):
    import net_common
    monkeypatch.setattr(net_common, 'run_server_dir', str(tmp_path / 'run' / 'server'))
    original = Player(id='casttest', name='casttest')
    original.spell_cast_chance = {'2': 74, '16': 92}
    assert original.save(force=True)
    relogged = Player(name='casttest', id='casttest')
    assert relogged.spell_cast_chance == {'2': 74, '16': 92}


if __name__ == '__main__':
    unittest.main()
