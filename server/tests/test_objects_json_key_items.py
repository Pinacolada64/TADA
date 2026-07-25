"""tests/test_objects_json_key_items.py

objects.json had every unique/quest item (guild_hq/main.py's own
_LOCKER_FORBIDDEN list -- "quest items, keys, unique relics, and sci-fi
zone gear" Lurch refuses to store) mistakenly tagged "type": "treasure".
commands/get.py's _is_treasure() converts any "treasure"-typed item
straight to silver on GET instead of adding it to inventory (SPUR.MISC.S
get.itm4's real behavior, ported deliberately for genuine treasure like
"gold nugget") -- so none of these 22 items could ever actually be
carried. Found while tracing the SPUR boat/vehicle-launch mechanic (the
inflatable dinghy and spacesuit are both on this list) -- confirmed via
SPUR.MISC.S's own get.itm4 that the *real* SPUR only treasure-converts
items whose name contains COIN/DIAMOND/GOLD/SILVER/JEWEL, none of which
any of these 22 names match.

Retyped all 22 to "misc" (not a recognized ItemType member, so
get.py/item_system.py's `ItemType(raw_type)` conversion just silently
no-ops -- same as any other non-treasure/non-cursed/non-book item).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from commands.get import _is_treasure


class TestKeyItemsAreNotTreasure(unittest.TestCase):

    # guild_hq/main.py's _LOCKER_FORBIDDEN -- every one of these is a
    # unique/quest item, never ordinary treasure.
    _KEY_ITEM_NUMBERS = {
        67, 73, 74, 76, 80, 82, 96, 97,
        122, 123, 124, 131, 132, 133, 134, 135, 138, 140, 142, 143, 144, 145,
    }

    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parent.parent / 'objects.json'
        data = json.loads(path.read_text())
        cls._by_number = {it['number']: it for it in data['items']}

    def test_every_locker_forbidden_item_exists(self):
        missing = self._KEY_ITEM_NUMBERS - self._by_number.keys()
        self.assertEqual(missing, set())

    def test_no_key_item_is_typed_treasure(self):
        still_treasure = [
            (n, self._by_number[n]['name']) for n in self._KEY_ITEM_NUMBERS
            if _is_treasure(self._by_number[n])
        ]
        self.assertEqual(still_treasure, [])

    def test_dinghy_spacesuit_and_space_tracker_specifically(self):
        for number, name in ((74, 'inflatable dinghy'), (122, 'spacesuit'), (138, 'space tracker')):
            item = self._by_number[number]
            self.assertEqual(item['name'], name)
            self.assertFalse(_is_treasure(item), f'{name} (#{number}) is still typed treasure')

    def test_key_items_are_not_typed_cursed_either(self):
        # A different special-case GET path (_is_cursed()) -- these items
        # shouldn't trip that one either.
        from commands.get import _is_cursed
        wrongly_cursed = [
            (n, self._by_number[n]['name']) for n in self._KEY_ITEM_NUMBERS
            if _is_cursed(self._by_number[n])
        ]
        self.assertEqual(wrongly_cursed, [])


class TestToolKitRepairItemsAreNotTreasure(unittest.TestCase):
    """communicator (#66) and broken communicator (#141) had the same
    treasure-typing bug, but aren't part of guild_hq's _LOCKER_FORBIDDEN
    list (confirmed against the real SPUR.GUILD.S drp.a check -- neither
    genuinely appears there, so nothing to fix on that side). Found
    while porting commands/use.py's tool-kit repair mechanic
    (SPUR.USE.S's 'tool' label): a broken communicator has to be
    carryable to ever reach the USE command that repairs it."""

    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parent.parent / 'objects.json'
        data = json.loads(path.read_text())
        cls._by_number = {it['number']: it for it in data['items']}

    def test_communicator_and_broken_communicator_not_treasure(self):
        for number, name in ((66, 'communicator'), (141, 'broken communicator')):
            item = self._by_number[number]
            self.assertEqual(item['name'], name)
            self.assertFalse(_is_treasure(item), f'{name} (#{number}) is still typed treasure')


if __name__ == '__main__':
    unittest.main(verbosity=2)
