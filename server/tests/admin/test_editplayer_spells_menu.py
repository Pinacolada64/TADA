"""tests/admin/test_editplayer_spells_menu.py

commands/editplayer.py's Character / NPC Stats > Spells sub-menu: one row
per catalog spell showing the player's remembered cast %
(player.spell_cast_chance, see spellbook.py), editable from the spell's
base up to spellbook.CAST_CHANCE_MAX, or R to reset it to base.
"""
from __future__ import annotations

import asyncio
import unittest

from commands.editplayer import _names_menu, _spells_menu
from player import Player


class _FakeCtx:
    def __init__(self, responses=None, player=None):
        self._q = list(responses or [])
        self.sent: list[str] = []
        self.player = player or Player()

    async def send(self, *args) -> None:
        for a in args:
            if isinstance(a, (list, tuple)):
                self.sent.extend(str(x) for x in a)
            else:
                self.sent.append(str(a))

    async def prompt(self, prompt_text: str = '', preamble_lines=None) -> str:
        if preamble_lines:
            await self.send(preamble_lines)
        return self._q.pop(0) if self._q else ''


def _find_item(menu, label):
    return next(i for i in menu.menu_items if getattr(i, 'text', None) == label)


def _run(item, ctx):
    asyncio.run(item.action(ctx))


class TestSpellsMenu(unittest.TestCase):
    def test_reachable_from_character_npc_stats(self):
        ctx = _FakeCtx()
        item = _find_item(_names_menu(ctx), 'Spells')
        self.assertIsNotNone(item.submenu)

    def test_unpractised_spell_shows_its_base(self):
        ctx = _FakeCtx()
        self.assertEqual(_find_item(_spells_menu(ctx), 'WHEATIES').dot_leader_handler(ctx), '70%')

    def test_practised_spell_is_marked(self):
        player = Player()
        player.spell_cast_chance = {'2': 84}
        ctx = _FakeCtx(player=player)
        self.assertEqual(_find_item(_spells_menu(ctx), 'WHEATIES').dot_leader_handler(ctx), '84%*')

    def test_set_a_value(self):
        player = Player()
        ctx = _FakeCtx(['91'], player=player)
        _run(_find_item(_spells_menu(ctx), 'WHEATIES'), ctx)
        self.assertEqual(player.spell_cast_chance, {'2': 91})
        self.assertTrue(player.unsaved_changes)
        self.assertIn('WHEATIES cast chance set to 91%.', ctx.sent)

    def test_reset_to_base_removes_the_entry(self):
        player = Player()
        player.spell_cast_chance = {'2': 84, '4': 66}
        ctx = _FakeCtx(['r'], player=player)
        _run(_find_item(_spells_menu(ctx), 'WHEATIES'), ctx)
        self.assertEqual(player.spell_cast_chance, {'4': 66})

    def test_below_base_or_over_the_cap_is_refused_then_reprompts(self):
        player = Player()
        ctx = _FakeCtx(['40', '100', '75'], player=player)
        _run(_find_item(_spells_menu(ctx), 'WHEATIES'), ctx)
        self.assertEqual(ctx.sent.count('Enter a number between 70 and 99.'), 2)
        self.assertEqual(player.spell_cast_chance, {'2': 75})

    def test_blank_cancels(self):
        player = Player()
        player.spell_cast_chance = {'2': 84}
        ctx = _FakeCtx([''], player=player)
        _run(_find_item(_spells_menu(ctx), 'WHEATIES'), ctx)
        self.assertEqual(player.spell_cast_chance, {'2': 84})


class TestSpellsMenuHelp(unittest.TestCase):
    """h<number> on a spell row shows its shoppe/wizard.py description."""

    def test_row_help_is_the_wizards_description_plus_chances(self):
        from shoppe.wizard import SPELLS
        player = Player()
        player.name = 'Rulan'
        player.spell_cast_chance = {'2': 84}
        ctx = _FakeCtx(player=player)
        item = _find_item(_spells_menu(ctx), 'WHEATIES')
        text = item.help_text(ctx)
        description = next(sp['description'] for sp in SPELLS if sp['number'] == 2)
        self.assertIn(description, text)
        self.assertIn('Effect: STR.', text)
        self.assertIn("Base cast chance 70%; Rulan's: 84% (raised by practice).", text)

    def test_class_only_spell_says_so(self):
        ctx = _FakeCtx()
        text = _find_item(_spells_menu(ctx), "WIZARD'S GLOW").help_text(ctx)
        self.assertIn("WIZARD'S GLOW (Wizards only):", text)

    def test_spells_item_has_help(self):
        ctx = _FakeCtx()
        self.assertIn('remembered cast %', _find_item(_names_menu(ctx), 'Spells').help_text)


if __name__ == '__main__':
    unittest.main()
