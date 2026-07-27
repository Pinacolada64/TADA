"""tests/test_spellbook.py

Covers spellbook.py -- the Spell Book container item. Wizards/Druids have
the smallest inventory capacities in the game while being the only
classes that accumulate spell scrolls, so learned spells get a dedicated
container instead of competing with weapons/armor/food for a slot.
"""
from __future__ import annotations

import unittest

import spellbook
from base_classes import PlayerClass
from inventory import Inventory
from items import Item, ItemCategory, Spell
from player import Player


def _new_player(char_class=None) -> Player:
    player = Player(name='Rulan', char_class=char_class)
    player.inventory = Inventory(capacity=14)
    return player


class TestMakeSpellbookItem(unittest.TestCase):
    def test_is_a_container_with_the_right_capacity(self):
        book = spellbook.make_spellbook_item()
        self.assertEqual(book.category, ItemCategory.CONTAINER)
        self.assertEqual(book.capacity, spellbook.SPELLBOOK_CAPACITY)
        self.assertEqual(book.id_number, spellbook.SPELLBOOK_ITEM_NUMBER)


class TestFindSpellbook(unittest.TestCase):
    def test_none_when_player_has_no_book(self):
        player = _new_player(PlayerClass.WIZARD)
        self.assertIsNone(spellbook.find_spellbook(player))

    def test_finds_an_existing_book(self):
        player = _new_player(PlayerClass.WIZARD)
        player.inventory.add(spellbook.make_spellbook_item())
        entry = spellbook.find_spellbook(player)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.item.id_number, spellbook.SPELLBOOK_ITEM_NUMBER)
        # Inventory.add() auto-creates entry.contents for any capacity>0 item.
        self.assertIsNotNone(entry.contents)


class TestEnsureSpellbook(unittest.TestCase):
    def test_grants_one_for_a_wizard_with_none(self):
        player = _new_player(PlayerClass.WIZARD)
        entry = spellbook.ensure_spellbook(player)
        self.assertIsNotNone(entry)
        self.assertEqual(len(player.inventory.entries(str(ItemCategory.CONTAINER))), 1)

    def test_grants_one_for_a_druid_with_none(self):
        player = _new_player(PlayerClass.DRUID)
        self.assertIsNotNone(spellbook.ensure_spellbook(player))

    def test_returns_the_existing_book_rather_than_granting_a_second_one(self):
        player = _new_player(PlayerClass.WIZARD)
        first  = spellbook.ensure_spellbook(player)
        second = spellbook.ensure_spellbook(player)
        self.assertIs(first.item, second.item)
        self.assertEqual(len(player.inventory.entries(str(ItemCategory.CONTAINER))), 1)

    def test_none_for_a_non_adept(self):
        player = _new_player(PlayerClass.FIGHTER)
        self.assertIsNone(spellbook.ensure_spellbook(player))
        self.assertEqual(len(player.inventory), 0)

    def test_none_when_the_main_pack_is_full(self):
        player = _new_player(PlayerClass.WIZARD)
        player.inventory = Inventory(capacity=0)
        self.assertIsNone(spellbook.ensure_spellbook(player))


class TestSpellEntries(unittest.TestCase):
    def _spell(self, number=1, name='ESP'):
        return Spell(id_number=number, name=name, cast_chance=70,
                     effect_type='I', effect_magnitude=4, charges=1, max_charges=1)

    def test_empty_for_a_player_with_no_spells(self):
        player = _new_player(PlayerClass.WIZARD)
        self.assertEqual(spellbook.spell_entries(player), [])

    def test_reads_spells_from_the_book(self):
        player = _new_player(PlayerClass.WIZARD)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(self._spell(), charges=1)
        entries = spellbook.spell_entries(player)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.name, 'ESP')

    def test_reads_spells_sitting_loose_in_the_main_inventory_too(self):
        """Backward compatibility: non-adepts never get a book, and any
        spell learned before this feature existed sits in the main
        inventory -- both must still show up as "known"."""
        player = _new_player(PlayerClass.FIGHTER)
        player.inventory.add(self._spell(), charges=1)
        entries = spellbook.spell_entries(player)
        self.assertEqual(len(entries), 1)

    def test_merges_both_sources(self):
        player = _new_player(PlayerClass.WIZARD)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(self._spell(number=1, name='ESP'), charges=1)
        player.inventory.add(self._spell(number=2, name='WHEATIES'), charges=1)
        entries = spellbook.spell_entries(player)
        self.assertEqual({e.item.name for e in entries}, {'ESP', 'WHEATIES'})

    def test_ignores_non_spell_items_in_both_places(self):
        player = _new_player(PlayerClass.WIZARD)
        book = spellbook.ensure_spellbook(player)
        book.contents.add(Item(id_number=1, name='trinket', category=ItemCategory.ITEM))
        player.inventory.add(Item(id_number=2, name='sword', category=ItemCategory.WEAPON))
        self.assertEqual(spellbook.spell_entries(player), [])


class TestRemoveSpell(unittest.TestCase):
    def _spell(self, number=1, name='ESP'):
        return Spell(id_number=number, name=name, cast_chance=70,
                     effect_type='I', effect_magnitude=4, charges=1, max_charges=1)

    def test_removes_from_the_book_when_present_there(self):
        player = _new_player(PlayerClass.WIZARD)
        book = spellbook.ensure_spellbook(player)
        spell = self._spell()
        book.contents.add(spell, charges=1)
        self.assertTrue(spellbook.remove_spell(player, spell))
        self.assertEqual(spellbook.spell_entries(player), [])

    def test_removes_from_the_main_inventory_when_theres_no_book(self):
        player = _new_player(PlayerClass.FIGHTER)
        spell = self._spell()
        player.inventory.add(spell, charges=1)
        self.assertTrue(spellbook.remove_spell(player, spell))
        self.assertEqual(spellbook.spell_entries(player), [])

    def test_false_when_the_spell_isnt_found_anywhere(self):
        player = _new_player(PlayerClass.WIZARD)
        spellbook.ensure_spellbook(player)
        self.assertFalse(spellbook.remove_spell(player, self._spell()))


if __name__ == '__main__':
    unittest.main()
