"""spellbook.py — the Spell Book container item.

Wizards/Druids have the smallest inventory capacities in the game
(inventory.py's _CLASS_LIMITS: Wizard 8, Druid 10, vs. 12-14 for most
other classes) while being the only classes that actually accumulate
spell scrolls -- up to 10 of them (shoppe/wizard.py's _SPELL_MAX), each
competing with weapons/armor/food for a slot. This module gives adepts a
dedicated container (same ItemCategory.CONTAINER/entry.contents mechanism
Bag of Holding already uses, see inventory.py's Inventory.add()) so
learned spells stop eating into their general-purpose capacity.

Shared between commands/new_player.py (starting grant), shoppe/wizard.py
(routes purchases here), and commands/cast.py (reads known spells from
here) -- kept at the root level, same tier as inventory.py/party.py,
rather than under commands/ or shoppe/, so none of them have to import
"up" or "sideways" through each other.
"""
from __future__ import annotations

from base_classes import PlayerClass
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory

# Deliberately outside objects.json's real range (max 165), same pattern
# as logon_events/birthday.py's _CAKE_ID = 9001 -- not a catalog item.
SPELLBOOK_ITEM_NUMBER = 9003
SPELLBOOK_NAME        = 'Spell Book'
SPELLBOOK_CAPACITY    = 10  # covers shoppe/wizard.py's _SPELL_MAX

_ADEPT_CLASSES = (PlayerClass.WIZARD, PlayerClass.DRUID)


def make_spellbook_item() -> Item:
    return Item(
        id_number=SPELLBOOK_ITEM_NUMBER,
        name=SPELLBOOK_NAME,
        category=ItemCategory.CONTAINER,
        capacity=SPELLBOOK_CAPACITY,
    )


def find_spellbook(player) -> InventoryEntry | None:
    """Return the player's Spell Book entry, or None if they don't have one."""
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return None
    found = inv.find(item_id=SPELLBOOK_ITEM_NUMBER, category=str(ItemCategory.CONTAINER))
    return found[0] if found else None


def ensure_spellbook(player) -> InventoryEntry | None:
    """Return the player's Spell Book entry, granting one on the spot if
    they're an adept (Wizard/Druid) and don't already have one -- covers
    characters created before this feature existed. Returns None for
    non-adepts (who never get a book -- their spells stay in the main
    inventory, unchanged from before this feature) or if the player's
    main pack has no room left for the book itself."""
    existing = find_spellbook(player)
    if existing is not None:
        return existing

    if getattr(player, 'char_class', None) not in _ADEPT_CLASSES:
        return None

    inv = getattr(player, 'inventory', None)
    if inv is None or not inv.add(make_spellbook_item()):
        return None
    return find_spellbook(player)


def spell_entries(player) -> list[InventoryEntry]:
    """All of a player's known spells: their Spell Book's contents (if
    they have one) plus any Spell-category entries sitting loose in the
    main inventory -- backward compatibility for non-adepts (who never
    get a book) and any spells learned before this feature existed."""
    entries: list[InventoryEntry] = []

    book = find_spellbook(player)
    if book is not None and book.contents is not None:
        entries.extend(book.contents.entries(category=str(ItemCategory.SPELL)))

    inv = getattr(player, 'inventory', None)
    if inv is not None:
        entries.extend(inv.entries(category=str(ItemCategory.SPELL)))

    return entries


def remove_spell(player, item) -> bool:
    """Remove one known spell (by identity/id_number) from wherever
    spell_entries() found it -- the Spell Book's contents first, then the
    main inventory. commands/cast.py's one-shot consumption hook."""
    book = find_spellbook(player)
    if book is not None and book.contents is not None:
        if book.contents.remove(item):
            return True

    inv = getattr(player, 'inventory', None)
    if inv is not None:
        return inv.remove(item)
    return False
