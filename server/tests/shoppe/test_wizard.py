"""tests/shoppe/test_wizard.py

Covers shoppe/wizard.py -- the Wizard's cave spell shop. Regression test
for the bug an alpha tester found live: main() never showed the spell
list up front -- a player walked in, answered "Y" to "are you here to
learn a spell?", and landed straight on a bare "Learn which spell?
(?=List, i#=Info, Q to leave)" prompt, having never actually seen a
spell name. The list was only reachable by already knowing to type '?'
first. Fixed by sending the list automatically right after "A scroll
appears before you..." -- '?' still re-shows it afterward.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from base_classes import PlayerClass, PlayerMoneyTypes, PlayerRace, PlayerStat
from flags import PlayerFlags
from inventory import Inventory
from player import Player
from shoppe.wizard import main as wizard_main


def _new_player(name: str, char_class=None, char_race=None, intelligence=None) -> Player:
    player = Player(name=name, char_class=char_class, char_race=char_race)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    player.inventory = Inventory(capacity=14)
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 10_000)
    if intelligence is not None:
        player.stats[PlayerStat.INT] = intelligence
    return player


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.server = SimpleNamespace(items=[])

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


class TestWizardShowsSpellListUpFront(unittest.IsolatedAsyncioTestCase):
    async def test_spell_list_shown_before_first_prompt_without_typing_question_mark(self):
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        ctx = _FakeCtx(['Y', 'Q'], player)
        await wizard_main(ctx)
        flat = ctx._flat()
        # Never typed '?' -- the list should still have appeared.
        self.assertIn('Available Spells', flat)
        self.assertIn('ESP', flat)
        self.assertIn('WHEATIES', flat)

    async def test_declining_never_sees_the_spell_list(self):
        """Saying N to "are you here to learn a spell?" shouldn't dump
        the spell list on someone who just wanted to leave."""
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        ctx = _FakeCtx(['N'], player)
        await wizard_main(ctx)
        self.assertNotIn('Available Spells', ctx._flat())

    async def test_question_mark_still_re_shows_the_list(self):
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        ctx = _FakeCtx(['Y', '?', 'Q'], player)
        await wizard_main(ctx)
        # Shown twice: once automatically, once via '?'.
        self.assertEqual(ctx._flat().count('Available Spells'), 2)

    async def test_non_adept_also_sees_the_list_up_front(self):
        player = _new_player('Rulan', char_class=PlayerClass.FIGHTER)
        ctx = _FakeCtx(['Y', 'Q'], player)
        await wizard_main(ctx)
        self.assertIn('Available Spells', ctx._flat())


class TestWizardSpellTableFollowsPlayerContext(unittest.IsolatedAsyncioTestCase):
    """The spell table's border=True Table() call hardcoded no border_style
    at all, so it always fell back to Table's own ASCII '+--+' default --
    a PETSCII connection or an ANSI player's own PREFS border-style choice
    (single/double, commands/prefs.py) were both silently ignored. Fixed
    by passing formatting.border_style_for_ctx(ctx), the same helper
    commands/list_locations.py already uses."""

    async def test_default_single_border_style_is_used_not_ascii_plusses(self):
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        player.client_settings.border_style = 'single'
        ctx = _FakeCtx(['Y', 'Q'], player)
        await wizard_main(ctx)
        flat = ctx._flat()
        self.assertIn('┌', flat)
        self.assertNotIn('+--', flat)

    async def test_double_border_style_is_honored(self):
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        player.client_settings.border_style = 'double'
        ctx = _FakeCtx(['Y', 'Q'], player)
        await wizard_main(ctx)
        self.assertIn('╔', ctx._flat())

    async def test_petscii_translation_forces_petscii_border_regardless_of_border_style(self):
        from terminal import Translation

        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        player.client_settings.translation = Translation.PETSCII
        player.client_settings.border_style = 'double'  # should be overridden
        ctx = _FakeCtx(['Y', 'Q'], player)
        await wizard_main(ctx)
        self.assertIn('┌', ctx._flat())
        self.assertNotIn('╔', ctx._flat())


class TestNonAdeptSpellLearningRoll(unittest.IsolatedAsyncioTestCase):
    """SPUR wiz3: non-adepts (anyone but Wizard/Druid) roll against
    Intelligence to actually learn a spell after paying for it -- gold is
    already spent by the time the roll happens, and a hard failure gets
    none of it back. Never ported until now; this port previously let
    every class succeed unconditionally. Learning spell #1 (ESP, 100
    silver) throughout -- responses are ['Y' enter, '1' pick ESP,
    'Y' confirm, 'Q' leave]."""

    _LEARN_ESP = ['Y', '1', 'Y', 'Q']

    async def test_adept_skips_the_roll_entirely(self):
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD, intelligence=3)
        ctx = _FakeCtx(self._LEARN_ESP, player)
        with patch('shoppe.wizard.random.randint') as mock_randint:
            await wizard_main(ctx)
        mock_randint.assert_not_called()
        self.assertIn('Your calling makes learning simple!', ctx._flat())
        self.assertIn('Spell taught!', ctx._flat())

    async def test_hard_failure_grants_no_spell_and_keeps_the_silver_spent(self):
        player = _new_player('Rulan', char_class=PlayerClass.FIGHTER,
                              char_race=None, intelligence=3)
        ctx = _FakeCtx(self._LEARN_ESP, player)
        # First roll (1-25) -> 1, so roll = 1+5+0 = 6 > intelligence(3): fails.
        # Second roll (1-10) -> 5, >=3: a hard failure, not the soft near-miss.
        with patch('shoppe.wizard.random.randint', side_effect=[1, 5]):
            await wizard_main(ctx)
        flat = ctx._flat()
        self.assertIn("Alas! My efforts to teach thee were in vain", flat)
        self.assertNotIn('Spell taught!', flat)
        self.assertEqual(len(player.inventory.entries('Spell')), 0)
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), 10_000 - 100)

    async def test_low_intelligence_shows_the_warning_before_the_roll(self):
        player = _new_player('Rulan', char_class=PlayerClass.FIGHTER, intelligence=9)
        ctx = _FakeCtx(self._LEARN_ESP, player)
        with patch('shoppe.wizard.random.randint', side_effect=[1, 5]):
            await wizard_main(ctx)
        self.assertIn('Thy intelligence may hinder thee from learning this spell.', ctx._flat())

    async def test_high_intelligence_passes_without_any_fail_message(self):
        player = _new_player('Rulan', char_class=PlayerClass.FIGHTER, intelligence=40)
        ctx = _FakeCtx(self._LEARN_ESP, player)
        # roll = 1+5+0 = 6 <= intelligence(40): passes on the first roll,
        # so the near-miss roll (side_effect's 2nd item) must never fire.
        with patch('shoppe.wizard.random.randint', side_effect=[1]):
            await wizard_main(ctx)
        flat = ctx._flat()
        self.assertNotIn('Alas!', flat)
        self.assertNotIn('After much study', flat)
        self.assertIn('Spell taught!', flat)
        self.assertEqual(len(player.inventory.entries('Spell')), 1)

    async def test_soft_near_miss_still_grants_the_spell(self):
        player = _new_player('Rulan', char_class=PlayerClass.FIGHTER, intelligence=3)
        ctx = _FakeCtx(self._LEARN_ESP, player)
        # First roll fails (6 > 3), but the near-miss roll (1-10) -> 1
        # is < 3: a soft near-miss, spell is still granted.
        with patch('shoppe.wizard.random.randint', side_effect=[1, 1]):
            await wizard_main(ctx)
        flat = ctx._flat()
        self.assertIn('After much study..', flat)
        self.assertIn('Spell taught!', flat)
        self.assertEqual(len(player.inventory.entries('Spell')), 1)

    async def test_dull_race_gets_extra_penalty_and_insult_on_hard_failure(self):
        player = _new_player('Rulan', char_class=PlayerClass.FIGHTER,
                              char_race=PlayerRace.OGRE, intelligence=8)
        ctx = _FakeCtx(self._LEARN_ESP, player)
        # roll = 1+5+3(dull race) = 9 > intelligence(8): fails even though
        # a Human with the same INT/first-roll (1+5+0=6) would have passed.
        with patch('shoppe.wizard.random.randint', side_effect=[1, 5]):
            await wizard_main(ctx)
        self.assertIn("'Your kind never did make good wizards,' the voice sniffs..", ctx._flat())

    async def test_non_dull_race_never_shows_the_insult_line(self):
        player = _new_player('Rulan', char_class=PlayerClass.FIGHTER,
                              char_race=PlayerRace.HUMAN, intelligence=3)
        ctx = _FakeCtx(self._LEARN_ESP, player)
        with patch('shoppe.wizard.random.randint', side_effect=[1, 5]):
            await wizard_main(ctx)
        self.assertNotIn('never did make good wizards', ctx._flat())


class TestPurchasedSpellsRouteToTheSpellBook(unittest.IsolatedAsyncioTestCase):
    """Ryan's spell book feature: adepts' learned spells go into a
    dedicated Spell Book container (spellbook.py) instead of the main
    inventory, so they stop competing with weapons/armor/food for a slot
    in the smaller Wizard/Druid inventory. Non-adepts are unaffected."""

    async def test_wizard_purchase_lands_in_the_spell_book_not_main_inventory(self):
        import spellbook
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        ctx = _FakeCtx(['Y', '1', 'Y', 'Q'], player)
        await wizard_main(ctx)
        book = spellbook.find_spellbook(player)
        self.assertIsNotNone(book)
        self.assertEqual(len(book.contents.entries('Spell')), 1)
        self.assertEqual(len(player.inventory.entries('Spell')), 0)

    async def test_druid_purchase_also_routes_to_the_spell_book(self):
        import spellbook
        player = _new_player('Rulan', char_class=PlayerClass.DRUID)
        ctx = _FakeCtx(['Y', '1', 'Y', 'Q'], player)
        await wizard_main(ctx)
        book = spellbook.find_spellbook(player)
        self.assertEqual(len(book.contents.entries('Spell')), 1)

    async def test_pre_existing_wizard_with_no_book_gets_one_auto_granted(self):
        """Covers a character created before this feature existed --
        ensure_spellbook() grants one on the spot at their first purchase."""
        import spellbook
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        self.assertIsNone(spellbook.find_spellbook(player))
        ctx = _FakeCtx(['Y', '1', 'Y', 'Q'], player)
        await wizard_main(ctx)
        self.assertIsNotNone(spellbook.find_spellbook(player))

    async def test_non_adept_purchase_still_uses_the_main_inventory(self):
        import spellbook
        # High INT guarantees the non-adept learning roll passes (max
        # possible roll is 25+5+3=33, comfortably under 40) without
        # needing to patch random.randint.
        player = _new_player('Rulan', char_class=PlayerClass.FIGHTER, intelligence=40)
        ctx = _FakeCtx(['Y', '1', 'Y', 'Q'], player)
        await wizard_main(ctx)
        self.assertIsNone(spellbook.find_spellbook(player))
        self.assertEqual(len(player.inventory.entries('Spell')), 1)

    async def test_has_spell_and_spell_count_check_the_book_not_just_inventory(self):
        """_has_spell()/_spell_count() (used for the '(known)' tag and the
        10-spell cap) must see spells that live in the book, or an adept
        could buy the same spell twice / never hit the cap."""
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        ctx = _FakeCtx(['Y', '1', 'Y', '1', 'Q'], player)  # buy ESP, try again
        await wizard_main(ctx)
        self.assertIn('You already know ESP.', ctx._flat())

    async def test_spell_book_full_refunds_and_refuses_like_main_inventory_did(self):
        import spellbook
        player = _new_player('Rulan', char_class=PlayerClass.WIZARD)
        # Pre-fill the book to capacity so the next purchase can't fit.
        book = spellbook.ensure_spellbook(player)
        from items import Item, ItemCategory
        for i in range(spellbook.SPELLBOOK_CAPACITY):
            book.contents.add(Item(id_number=500 + i, name=f'filler {i}', category=ItemCategory.ITEM))
        starting_silver = player.get_silver(PlayerMoneyTypes.IN_HAND)
        ctx = _FakeCtx(['Y', '1', 'Y', 'Q'], player)
        await wizard_main(ctx)
        self.assertIn('Your pack is full', ctx._flat())
        self.assertEqual(player.get_silver(PlayerMoneyTypes.IN_HAND), starting_silver)


if __name__ == '__main__':
    unittest.main()
