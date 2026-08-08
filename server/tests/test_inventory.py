"""tests/test_inventory.py — unit tests for inventory.py's JSON round-trip.

Regression coverage: InventoryEntry.to_json()/Inventory.from_json() used to
drop item.flags entirely, so any item's flags (e.g. ammo's
rounds/damage/used_with) silently reset to [] on the very next save/load
cycle -- independent of whatever a shop set them to at purchase time. This
is what actually broke commands/use.py's ammo-loading branch in practice
(see that module's _apply_item docstring): even with the correct flags at
purchase time, Player.__init__ reloading from disk erased them before USE
ever got a chance to read them.
"""
from __future__ import annotations

import unittest

from base_classes import WeaponClass
from inventory import Inventory
from items import Item, ItemCategory, Rations, Spell, Weapon


class TestInventoryFlagsRoundTrip(unittest.TestCase):

    def test_item_flags_survive_to_json_from_json(self):
        inv = Inventory()
        ammo = Item(id_number=104, name='.357 ammo', category=ItemCategory.ITEM,
                    flags={'rounds': 6, 'damage': 4, 'used_with': '.357 magnum'})
        inv.add(ammo)

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='.357 ammo')[0]

        self.assertEqual(entry.item.flags, {'rounds': 6, 'damage': 4, 'used_with': '.357 magnum'})

    def test_item_without_flags_round_trips_to_empty_list(self):
        inv = Inventory()
        inv.add(Item(id_number=6, name='large ruby', category=ItemCategory.ITEM))

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='large ruby')[0]

        self.assertEqual(entry.item.flags, [])
        self.assertNotIn('item_flags', inv.to_json()[0])


class TestInventoryStacking(unittest.TestCase):
    """Inventory.add()/remove() stack same-id_number items into a single
    entry with a quantity counter, rather than creating a duplicate slot
    per copy."""

    def test_add_same_item_twice_stacks_quantity_to_two(self):
        inv = Inventory()
        torch1 = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)
        torch2 = Item(id_number=1, name='Torch', category=ItemCategory.ITEM)

        inv.add(torch1)
        inv.add(torch2)

        self.assertEqual(len(inv), 1)  # one slot, not two
        entry = inv.find(item_id=1)[0]
        self.assertEqual(entry.quantity, 2)

    def test_remove_one_of_two_leaves_quantity_one(self):
        inv = Inventory()
        inv.add(Item(id_number=1, name='Torch', category=ItemCategory.ITEM))
        inv.add(Item(id_number=1, name='Torch', category=ItemCategory.ITEM))

        removed = inv.remove(inv.find(item_id=1)[0].item, quantity=1)

        self.assertTrue(removed)
        entry = inv.find(item_id=1)[0]
        self.assertEqual(entry.quantity, 1)

    def test_remove_last_one_drops_the_entry(self):
        inv = Inventory()
        inv.add(Item(id_number=1, name='Torch', category=ItemCategory.ITEM))

        removed = inv.remove(inv.find(item_id=1)[0].item, quantity=1)

        self.assertTrue(removed)
        self.assertEqual(len(inv), 0)
        self.assertEqual(inv.find(item_id=1), [])


class TestInventoryPruneZombieEntries(unittest.TestCase):
    """Inventory._prune() self-heals a quantity<=0 entry that got left
    behind by code mutating entry.quantity directly instead of going
    through remove(). Found live: the ally.items InventoryEntry-aliasing
    bug (fixed in commands/give.py) let a shared entry get decremented to
    0 via ally-side consumption, but only popped from the ally's own
    list, not from the player's own Inventory._entries -- leaving a
    zombie "cloth armor" that `inv` displayed forever and every future
    GIVE attempt silently refused with a false "insufficient quantity"
    (0 < 1). _prune() runs on every read/write entry point so it
    self-heals the moment the Inventory is touched again, without
    needing a save-file edit."""

    def _inv_with_zombie(self) -> Inventory:
        inv = Inventory()
        inv.add(Item(id_number=2, name='cloth armor', category=ItemCategory.ITEM))
        # Simulate the aliasing bug's outcome directly, matching how it
        # was actually produced (mutated in place, not via remove()).
        inv._entries[0].quantity = 0
        return inv

    def test_entries_hides_zombie(self):
        inv = self._inv_with_zombie()
        self.assertEqual(inv.entries(), [])

    def test_find_hides_zombie(self):
        inv = self._inv_with_zombie()
        self.assertEqual(inv.find(item_id=2), [])

    def test_len_and_slot_count_dont_count_zombie(self):
        inv = self._inv_with_zombie()
        self.assertEqual(len(inv), 0)
        self.assertEqual(inv.slot_count(), 0)

    def test_is_full_ignores_zombie_slot(self):
        inv = self._inv_with_zombie()
        inv.capacity = 1
        self.assertFalse(inv.is_full())

    def test_zombie_does_not_block_re_adding_the_same_item(self):
        inv = self._inv_with_zombie()
        added = inv.add(Item(id_number=2, name='cloth armor', category=ItemCategory.ITEM))
        self.assertTrue(added)
        self.assertEqual(inv.find(item_id=2)[0].quantity, 1)


class TestInventoryKindRoundTrip(unittest.TestCase):
    """Regression: Ryan reported "you have nothing matching bread" for a
    loaf of bread genuinely in inventory -- from_json() rebuilt every
    persisted item as a plain Item(), which has no .kind at all unless
    explicitly passed in, and to_json() never wrote one out to begin
    with. commands/eat.py's/commands/drink.py's food/drink filters both
    key off item.kind == 'food'/'drink', so any ration silently
    stopped showing up in EAT/DRINK the moment a player reconnected
    (Inventory.from_json() runs on every Player load, including a plain
    reconnect, not just a full server restart).
    """

    def test_rations_kind_survives_to_json_from_json(self):
        inv = Inventory()
        bread = Rations(number=5, name='LOAF OF BREAD', kind='food', price=30)
        inv.add(bread)

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='LOAF OF BREAD')[0]

        self.assertEqual(entry.item.kind, 'food')

    def test_drink_kind_survives_to_json_from_json(self):
        inv = Inventory()
        water = Rations(number=12, name='MINERAL WATER', kind='drink', price=10)
        inv.add(water)

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='MINERAL WATER')[0]

        self.assertEqual(entry.item.kind, 'drink')

    def test_item_without_kind_round_trips_to_none(self):
        inv = Inventory()
        inv.add(Item(id_number=6, name='large ruby', category=ItemCategory.ITEM))

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='large ruby')[0]

        self.assertIsNone(entry.item.kind)
        self.assertNotIn('item_kind', inv.to_json()[0])


class TestInventoryKindBackfill(unittest.TestCase):
    """Regression: the to_json()/from_json() round-trip fix above only
    protects an item that already has .kind *at save time*. Ryan's own
    test character still couldn't eat a loaf of bread after that fix
    shipped, because that bread had been saved (with no item_kind field
    at all) by an older build, before item.kind existed on it in the
    first place -- from_json() had nothing to preserve. from_json() now
    falls back to looking the item up in rations.json by number when
    item_kind is missing, healing any pre-existing save on next load.
    """

    def _legacy_entry(self, item_id: int, name: str, category: str = 'Item') -> dict:
        """A save record shaped exactly like one written before item_kind
        existed -- no 'item_kind' key at all."""
        return {'item_id': item_id, 'item_name': name, 'item_category': category, 'quantity': 1}

    def test_legacy_bread_entry_heals_kind_and_category(self):
        restored = Inventory.from_json([self._legacy_entry(5, 'LOAF OF BREAD')])
        entry = restored.find(name='LOAF OF BREAD')[0]

        self.assertEqual(entry.item.kind, 'food')
        self.assertEqual(entry.item.category, ItemCategory.FOOD)

    def test_legacy_drink_entry_heals_kind_and_category(self):
        restored = Inventory.from_json([self._legacy_entry(1, 'TEA')])
        entry = restored.find(name='TEA')[0]

        self.assertEqual(entry.item.kind, 'drink')
        self.assertEqual(entry.item.category, ItemCategory.DRINK)

    def test_healed_bread_is_visible_to_eat_command_filter(self):
        from commands.eat import _food_entries

        restored = Inventory.from_json([self._legacy_entry(5, 'LOAF OF BREAD')])
        player = type('P', (), {'inventory': restored})()
        matches = _food_entries(player)

        self.assertEqual(len(matches), 1)

    def test_number_match_alone_is_not_enough_without_name_match(self):
        """rations.json #1 is TEA, but item numbering is only unique
        within its own category -- a legacy weapon or misc item that
        happens to share id_number 1 with a ration must NOT be
        misidentified as that ration just because the number matches."""
        restored = Inventory.from_json([self._legacy_entry(1, 'RUSTY DAGGER', category='Weapon')])
        entry = restored.find(name='RUSTY DAGGER')[0]

        self.assertIsNone(entry.item.kind)

    def test_unknown_item_id_is_left_alone(self):
        restored = Inventory.from_json([self._legacy_entry(99999, 'MYSTERY BOX')])
        entry = restored.find(name='MYSTERY BOX')[0]

        self.assertIsNone(entry.item.kind)


class TestInventoryTypeRoundTrip(unittest.TestCase):
    """Regression: item.type (item_system.ItemType -- armor/book/compass/
    cursed/shield/treasure) is a separate, independently-used property from
    item.kind above (rations' food/drink/cursed) -- commands/wear.py,
    commands/use.py and commands/read.py all filter on .type, not .kind.
    Like .kind before it, to_json()/from_json() dropped .type entirely, so
    an editplayer-granted armor/shield/book item silently stopped being
    WEAR/USE/READ-able after any save/load round trip (found live testing
    commands/wear.py's active_armor_id addition, 2026-08-08: a freshly
    granted "leather armor" worked in-session, but a second copy stacked
    onto a reloaded entry from an earlier session fell through USE's
    fallback "You play with the X.." branch)."""

    def test_armor_type_survives_to_json_from_json(self):
        from item_system import ItemType
        inv = Inventory()
        armor = Item(id_number=24, name='leather armor', category=ItemCategory.ITEM)
        armor.type = ItemType.ARMOR
        inv.add(armor)

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='leather armor')[0]

        self.assertEqual(entry.item.type, ItemType.ARMOR)

    def test_shield_type_survives_to_json_from_json(self):
        from item_system import ItemType
        inv = Inventory()
        shield = Item(id_number=4, name='small shield', category=ItemCategory.ITEM)
        shield.type = ItemType.SHIELD
        inv.add(shield)

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='small shield')[0]

        self.assertEqual(entry.item.type, ItemType.SHIELD)

    def test_item_without_type_round_trips_to_none(self):
        # id_number 6 deliberately avoided here -- it collides with
        # objects.json #6 "large ruby" (type "treasure"), whose *own*
        # name also happens to be "large ruby", so the backfill below
        # would legitimately (and correctly) attach a type to it.
        inv = Inventory()
        inv.add(Item(id_number=99999, name='mystery trinket', category=ItemCategory.ITEM))

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='mystery trinket')[0]

        self.assertIsNone(entry.item.type)
        self.assertNotIn('item_type', inv.to_json()[0])

    def test_kind_and_type_are_independent_fields(self):
        """The bug this fixes was Ryan momentarily suspecting .kind and
        .type were the same property under two names -- confirm both
        survive a round trip independently on the same item."""
        from item_system import ItemType
        inv = Inventory()
        cursed_armor = Item(id_number=57, name='magical armor', category=ItemCategory.ITEM)
        cursed_armor.type = ItemType.CURSED
        cursed_armor.kind = 'cursed'
        inv.add(cursed_armor)

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='magical armor')[0]

        self.assertEqual(entry.item.type, ItemType.CURSED)
        self.assertEqual(entry.item.kind, 'cursed')


class TestInventoryTypeBackfill(unittest.TestCase):
    """Regression: same "heal a save file written before the fix existed"
    gap as TestInventoryKindBackfill, but for item_type against
    objects.json instead of item_kind against rations.json."""

    def _legacy_entry(self, item_id: int, name: str, category: str = 'Item') -> dict:
        return {'item_id': item_id, 'item_name': name, 'item_category': category, 'quantity': 1}

    def test_legacy_armor_entry_heals_type(self):
        from item_system import ItemType
        restored = Inventory.from_json([self._legacy_entry(24, 'leather armor')])
        entry = restored.find(name='leather armor')[0]

        self.assertEqual(entry.item.type, ItemType.ARMOR)

    def test_legacy_shield_entry_heals_type(self):
        from item_system import ItemType
        restored = Inventory.from_json([self._legacy_entry(4, 'small shield')])
        entry = restored.find(name='small shield')[0]

        self.assertEqual(entry.item.type, ItemType.SHIELD)

    def test_healed_armor_is_wearable(self):
        from commands.wear import _wearable_entries

        restored = Inventory.from_json([self._legacy_entry(24, 'leather armor')])
        player = type('P', (), {'inventory': restored})()
        matches = _wearable_entries(player)

        self.assertEqual(len(matches), 1)

    def test_number_match_alone_is_not_enough_without_name_match(self):
        """objects.json #24 is leather armor, but item numbering is only
        unique within its own category -- an unrelated legacy weapon or
        ration sharing id_number 24 must NOT be misidentified as armor
        just because the number matches. (A resolved Weapon has no .type
        attribute at all -- weapons never carry one -- so this checks via
        getattr rather than asserting the attribute exists as None.)"""
        restored = Inventory.from_json([self._legacy_entry(24, 'RUSTY DAGGER', category='Weapon')])
        entry = restored.find(name='RUSTY DAGGER')[0]

        self.assertIsNone(getattr(entry.item, 'type', None))

    def test_unknown_item_id_is_left_alone(self):
        restored = Inventory.from_json([self._legacy_entry(99999, 'MYSTERY BOX')])
        entry = restored.find(name='MYSTERY BOX')[0]

        self.assertIsNone(entry.item.type)


class TestInventoryWeaponResolution(unittest.TestCase):
    """Regression: Inventory.from_json() used to rebuild every carried
    weapon as a bare Item -- id_number/name/category/flags/kind only --
    dropping sound_effect/stability/to_hit/weapon_class entirely. Any
    weapon readied after a save/load round trip then crashed combat's
    weapon_sfx() (AttributeError: 'Item' object has no attribute
    'sound_effect'), which the command dispatcher's blanket except-handler
    swallowed, silently dropping the player back to the main prompt on
    ATTACK. from_json() now resolves weapon-category entries back to a
    real Weapon via items.resolve_weapon() when given the server's raw
    weapons.json list.
    """

    _LONG_SWORD = {
        'number': 1, 'location': 2, 'name': 'LONG SWORD', 'kind': 'standard',
        'sound_effect': ['SWISH!', 'SLASH!'], 'stability': 50, 'to_hit': 60,
        'price': 250, 'weapon_class': 'bash/slash',
    }

    def test_weapon_fields_survive_round_trip_with_weapons_data(self):
        inv = Inventory()
        inv.add(Weapon(id_number=1, name='LONG SWORD', location=0,
                        kind='standard', sound_effect=('SWISH!', 'SLASH!'),
                        stability=50, to_hit=60, price=250,
                        weapon_class=WeaponClass.BASH_SLASH))

        restored = Inventory.from_json(inv.to_json(), weapons_data=[self._LONG_SWORD])
        entry = restored.find(name='LONG SWORD')[0]

        self.assertIsInstance(entry.item, Weapon)
        self.assertEqual(entry.item.sound_effect, ('SWISH!', 'SLASH!'))
        self.assertEqual(entry.item.weapon_class, 'bash/slash')
        self.assertEqual(entry.item.stability, 50)
        self.assertEqual(entry.item.to_hit, 60)
        self.assertEqual(entry.item.price, 250)

    def test_weapon_without_matching_weapons_data_falls_back_to_bare_item(self):
        inv = Inventory()
        inv.add(Weapon(id_number=1, name='LONG SWORD'))

        restored = Inventory.from_json(inv.to_json())  # no weapons_data at all
        entry = restored.find(name='LONG SWORD')[0]

        self.assertIsInstance(entry.item, Item)
        self.assertNotIsInstance(entry.item, Weapon)

        restored_unmatched = Inventory.from_json(inv.to_json(), weapons_data=[])
        entry2 = restored_unmatched.find(name='LONG SWORD')[0]
        self.assertIsInstance(entry2.item, Item)
        self.assertNotIsInstance(entry2.item, Weapon)

    def test_weapon_id_collision_across_categories_does_not_misresolve(self):
        """weapons.json #1 is LONG SWORD, but item numbering is only
        unique within its own category -- a legacy weapon save entry
        that happens to share id_number 1 with LONG SWORD but has a
        different name must not be misresolved into LONG SWORD's stats."""
        inv = Inventory()
        inv.add(Weapon(id_number=1, name='RUSTY DAGGER'))

        restored = Inventory.from_json(inv.to_json(), weapons_data=[self._LONG_SWORD])
        entry = restored.find(name='RUSTY DAGGER')[0]

        self.assertIsInstance(entry.item, Item)
        self.assertNotIsInstance(entry.item, Weapon)


class TestInventorySpellResolution(unittest.TestCase):
    """Regression: same gap as TestInventoryWeaponResolution, for spells.
    A learned spell that survived a save/load round trip came back as a
    bare Item missing effect_type/cast_chance/effect_magnitude entirely
    (getattr defaults: '' / 0 / 0). commands/cast.py's _stat_enum(effect_type)
    does a bare dict lookup keyed by effect_type -- an empty string isn't a
    valid key, so casting a reloaded spell raised KeyError, caught by the
    command dispatcher's blanket except-handler and silently dropping the
    player back to the main prompt on CAST, the same failure shape as the
    ATTACK bug. from_json() now resolves spell-category entries back to a
    real Spell via items.resolve_spell(), keyed against shoppe/wizard.py's
    static SPELLS list (no ctx.server plumbing needed -- it's hardcoded
    data, not a per-server JSON file).
    """

    # shoppe/wizard.py's SPELLS #4 = KILL (monster-damage spell)
    _KILL_ID = 4

    def test_spell_fields_survive_round_trip(self):
        inv = Inventory()
        inv.add(Spell(id_number=self._KILL_ID, name='KILL', charges=1, max_charges=1,
                       cast_chance=60, effect_type='M', effect_magnitude=6))

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='KILL')[0]

        self.assertIsInstance(entry.item, Spell)
        self.assertEqual(entry.item.effect_type, 'M')
        self.assertEqual(entry.item.cast_chance, 60)
        self.assertEqual(entry.item.effect_magnitude, 6)

    def test_spell_id_collision_across_categories_does_not_misresolve(self):
        """SPELLS #4 is KILL, but item numbering is only unique within
        its own category -- a legacy entry sharing id_number 4 with KILL
        but a different name must not be misresolved into KILL's stats."""
        inv = Inventory()
        inv.add(Spell(id_number=self._KILL_ID, name='MYSTERY SCROLL'))

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='MYSTERY SCROLL')[0]

        self.assertIsInstance(entry.item, Item)
        self.assertNotIsInstance(entry.item, Spell)

    def test_unknown_spell_id_falls_back_to_bare_item(self):
        inv = Inventory()
        inv.add(Spell(id_number=99999, name='HOMEBREW HEX'))

        restored = Inventory.from_json(inv.to_json())
        entry = restored.find(name='HOMEBREW HEX')[0]

        self.assertIsInstance(entry.item, Item)
        self.assertNotIsInstance(entry.item, Spell)


if __name__ == '__main__':
    unittest.main(verbosity=2)
