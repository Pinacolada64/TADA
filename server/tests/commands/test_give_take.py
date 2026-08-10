"""tests/test_give_take.py

Unit tests for:
  - commands/give.py  (GiveCommand)
  - commands/take.py  (TakeCommand)

Coverage:
  GIVE
    - give item to ally (item leaves player inv, lands in ally.items)
    - give item to ally by partial name match
    - give to ally when player has no servants (falls through to "no such target")
    - give item to co-located player (item transfers between inventories)
    - give item to player in full inventory (rejected)
    - give to monster (various humorous response categories; item consumed/returned)
    - give food to monster → consumed
    - give gold to greedy monster → kept
    - give gold to non-greedy monster → returned (generic fallback)
    - give with no target → "give to whom?" prompt
    - give with no inventory → "nothing to give"
    - give item name not in inventory → error message
    - interactive item selection (no name arg)

  BODY BUILDING (give food to ally)
    - weak ally (str < 11) eats food → strength +1, message shown
    - weak ally eats drink → strength +1
    - strong ally (str >= 11) eats food → no strength change, no message
    - non-food item given to weak ally → no strength change
    - cursed ration → strength -1, sickness message
    - cursed ration on ally at str 1 → strength floors at 1

  TAKE
    - take item from ally → item in player inv, removed from ally.items
    - take by partial item name
    - take by partial ally name
    - take with no servants → error
    - take from ally carrying nothing → error
    - take when player inventory is full → rejected
    - interactive item selection (no name arg)
    - "take from <ally>" lists only that ally's items

Run with:
    python -m pytest tests/test_give_take.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Minimal stubs so tests run without the full networking stack
# ---------------------------------------------------------------------------

import sys, types

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from bar.ally_data import Ally, AllyStatus
from commands.give import GiveCommand, _monster_give_response
from commands.take import TakeCommand
from inventory import Inventory, InventoryEntry
from items import Item, ItemCategory, Weapon
from party import Party


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(name: str, item_id: int = 1,
               kind: str = '', category=None) -> Item:
    cat = category or ItemCategory.ITEM
    return Item(id_number=item_id, name=name, kind=kind, category=cat)


def _make_ally(name: str = 'BATMAN', strength: int = 14,
               to_hit: int = 5) -> Ally:
    ally = Ally(name, 'm', strength, to_hit)
    ally.status = AllyStatus.SERVANT
    return ally


def _make_player(name: str = 'Rulan', inv_capacity: int | None = None):
    """Return a minimal player-like object with an Inventory and a Party."""
    player = MagicMock()
    player.name = name
    player.inventory = Inventory(capacity=inv_capacity)
    player.party = Party()
    player.unsaved_changes = False
    return player


class _FakeServer:
    def __init__(self, game_map=None, monsters=None):
        self.clients: dict = {}
        self.game_map = game_map
        self.monsters = monsters or []


class _FakeClient:
    def __init__(self, room=1):
        self.room = room


class _FakeCtx:
    def __init__(self, player, server=None, room=1):
        self.player = player
        self.client = _FakeClient(room=room)
        self.server = server or _FakeServer()
        self._sent:  list[str] = []
        self._prompt_answer: str = ''

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        pass   # bystander messages; not tested here

    async def prompt(self, *args, **kwargs) -> str:
        return self._prompt_answer

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _monster_give_response unit tests (pure logic, no I/O)
# ---------------------------------------------------------------------------

class TestMonsterGiveResponse(unittest.TestCase):

    def _monster(self, name='TROLL'):
        return {'name': name, 'strength': 10}

    def test_food_is_consumed(self):
        item = _make_item('RATION', kind='food')
        lines, consumed = _monster_give_response(item, self._monster())
        self.assertTrue(consumed)
        self.assertTrue(lines)

    def test_weapon_is_returned(self):
        item = _make_item('SWORD', category=ItemCategory.WEAPON)
        lines, consumed = _monster_give_response(item, self._monster())
        self.assertFalse(consumed)

    def test_greedy_monster_keeps_gold(self):
        item = _make_item('GOLD COIN')
        lines, consumed = _monster_give_response(item, self._monster('DRAGON!'))
        self.assertTrue(consumed)

    def test_non_greedy_monster_returns_gold(self):
        # SAND CRAB is not in the greedy keyword list
        item = _make_item('GOLD COIN')
        lines, consumed = _monster_give_response(item, self._monster('SAND CRAB'))
        self.assertFalse(consumed)

    def test_compass_is_returned(self):
        item = _make_item('COMPASS')
        lines, consumed = _monster_give_response(item, self._monster())
        self.assertFalse(consumed)
        self.assertTrue(any('compass' in l.lower() or 'needle' in l.lower()
                            for l in lines))

    def test_shield_becomes_hat(self):
        item = _make_item('BATTLE SHIELD')
        lines, consumed = _monster_give_response(item, self._monster())
        self.assertFalse(consumed)
        self.assertTrue(any('hat' in l.lower() for l in lines))

    def test_ammo_is_returned(self):
        item = _make_item('ARROW')
        lines, consumed = _monster_give_response(item, self._monster())
        self.assertFalse(consumed)

    def test_grenade_thrown_back(self):
        item = _make_item('GRENADE')
        lines, consumed = _monster_give_response(item, self._monster())
        self.assertFalse(consumed)
        self.assertTrue(any('hurl' in l.lower() or 'throws' in l.lower()
                            or 'hurls' in l.lower() for l in lines))

    def test_generic_item_is_returned(self):
        item = _make_item('MYSTERIOUS WIDGET')
        lines, consumed = _monster_give_response(item, self._monster())
        self.assertFalse(consumed)
        self.assertTrue(lines)


# ---------------------------------------------------------------------------
# GiveCommand — ally targets
# ---------------------------------------------------------------------------

class TestGiveToAlly(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.cmd = GiveCommand()
        self.player = _make_player()
        self.ally   = _make_ally('BATMAN')
        self.player.party.add_member(self.player, self.ally)
        self.item   = _make_item('RATION', item_id=5, kind='food')
        self.player.inventory.add(self.item)
        self.ctx = _FakeCtx(self.player)

    async def test_give_item_to_ally_removes_from_inventory(self):
        await self.cmd.execute(self.ctx, 'ration', 'to', 'batman')
        self.assertEqual(len(self.player.inventory.entries()), 0)

    async def test_give_item_to_ally_marks_player_unsaved(self):
        # Bug: none of the give-to-ally branches set
        # player.unsaved_changes, so the removal happened correctly in
        # memory but Player.save() (player.py:1016, a no-op unless
        # unsaved_changes or force=True) never persisted it -- the item
        # was still in the last-saved file, so it reappeared on the next
        # reconnect/server restart even though the live session showed it
        # gone. Ryan's follow-up bug report after the stacked-item fix.
        self.assertFalse(self.player.unsaved_changes)
        await self.cmd.execute(self.ctx, 'ration', 'to', 'batman')
        self.assertTrue(self.player.unsaved_changes)

    async def test_give_item_to_ally_adds_to_ally_items(self):
        await self.cmd.execute(self.ctx, 'ration', 'to', 'batman')
        self.assertEqual(len(self.ally.items), 1)
        self.assertEqual(self.ally.items[0].item.name, 'RATION')

    async def test_repeated_gives_of_same_item_stack_on_ally(self):
        # Bug: ally.items.append(entry) always created a new entry, never
        # stacking onto a matching one the way player.inventory.add() (or
        # another player's, via GIVE) already does -- giving the same
        # item type to an ally 4 times over produced 4 separate quantity-1
        # entries in ally.items instead of one entry at quantity 4. Ryan
        # found this live: "you can see that Betty has 4 CLOTH ARMORs --
        # that shouldn't be possible."
        for _ in range(3):
            self.player.inventory.add(_make_item('RATION', item_id=5, kind='food'))
            await self.cmd.execute(self.ctx, 'ration', 'to', 'batman')
        self.assertEqual(len(self.ally.items), 1)
        self.assertEqual(self.ally.items[0].quantity, 3)

    async def test_give_item_to_ally_sends_confirmation(self):
        await self.cmd.execute(self.ctx, 'ration', 'to', 'batman')
        self.assertIn('BATMAN', self.ctx.sent().upper())

    async def test_give_stacked_item_to_ally_gives_only_one_unit(self):
        # Bug: inventory.remove(item) only decrements a stacked entry's
        # quantity in place (rather than always popping it), and the ally
        # branch reused that same source InventoryEntry object instead of
        # building a fresh one -- so giving 1 ration out of a stack of 3
        # left the ally holding the same object as the player's own
        # remaining-2 entry (aliased, not copied), showing the ally with
        # 2 rations instead of 1, and any further mutation of either
        # corrupted both. Ryan's bug report.
        self.player.inventory.remove(self.item)  # undo setUp's qty-1 add
        self.player.inventory.add(self.item, quantity=3)
        await self.cmd.execute(self.ctx, 'ration', 'to', 'batman')

        player_entries = self.player.inventory.entries()
        self.assertEqual(len(player_entries), 1)
        self.assertEqual(player_entries[0].quantity, 2)
        self.assertEqual(len(self.ally.items), 1)
        self.assertEqual(self.ally.items[0].quantity, 1)
        self.assertIsNot(player_entries[0], self.ally.items[0])

    async def test_give_item_to_ally_partial_name(self):
        """'bat' should match 'BATMAN'."""
        await self.cmd.execute(self.ctx, 'ration', 'to', 'bat')
        self.assertEqual(len(self.ally.items), 1)

    async def test_dead_bug_ration_giveable_while_ring_worn_flag_set(self):
        # Regression: id_number is only unique within its own category
        # (weapons/items/rations each number independently -- items.py:364).
        # objects.json #67 "ring" collides with ration #67 "DEAD BUG" --
        # giving away the ration must not be blocked by RING_WORN.
        self.player.query_flag = lambda f: True   # RING_WORN
        dead_bug = _make_item('DEAD BUG', item_id=67, category=ItemCategory.FOOD, kind='food')
        self.player.inventory.add(dead_bug)
        await self.cmd.execute(self.ctx, 'dead bug', 'to', 'batman')
        self.assertNotIn('wearing it', self.ctx.sent())
        self.assertEqual(len(self.ally.items), 1)

    async def test_give_nothing_when_inventory_empty(self):
        self.player.inventory.remove(self.item)
        await self.cmd.execute(self.ctx, 'ration', 'to', 'batman')
        self.assertIn('nothing', self.ctx.sent().lower())
        self.assertEqual(len(self.ally.items), 0)

    async def test_give_worn_armor_clears_active_armor_id(self):
        # Bug: giving away the piece of armor currently backing
        # player.active_armor_id never cleared that id or refreshed
        # player.armor, so STATS kept showing it "(worn)" at its old
        # rating even though it was now sitting in the ally's pack
        # instead of the player's own -- JoyfulColor's playtesting report,
        # "give the bishop some armor, it still shows READYed in STATS."
        from item_system import ItemType
        armor = _make_item('CLOTH ARMOR', item_id=2, category=ItemCategory.ARMOR)
        armor.type = ItemType.ARMOR
        armor.condition = 100
        self.player.inventory.add(armor)
        self.player.active_armor_id = 2
        self.player.armor = 50

        await self.cmd.execute(self.ctx, 'cloth armor', 'to', 'batman')

        self.assertIsNone(self.player.active_armor_id)
        self.assertEqual(self.player.armor, 0)
        self.assertEqual(self.ally.items[0].item.name, 'CLOTH ARMOR')

    async def test_give_nonexistent_item(self):
        await self.cmd.execute(self.ctx, 'sword', 'to', 'batman')
        self.assertIn('not carrying', self.ctx.sent().lower())
        self.assertEqual(len(self.ally.items), 0)

    async def test_give_no_target_asks_whom(self):
        await self.cmd.execute(self.ctx, 'ration')
        self.assertIn('whom', self.ctx.sent().lower())

    async def test_give_to_unknown_target(self):
        await self.cmd.execute(self.ctx, 'ration', 'to', 'nobody')
        self.assertIn('nobody', self.ctx.sent().lower())
        self.assertEqual(len(self.ally.items), 0)

    async def test_give_interactive_item_selection(self):
        """No item name → show list, player picks by number."""
        self.ctx._prompt_answer = '1'   # pick the first (and only) item
        await self.cmd.execute(self.ctx, 'to', 'batman')
        self.assertEqual(len(self.ally.items), 1)


# ---------------------------------------------------------------------------
# GiveCommand — weapon auto-ready + ammo load-in for allies
#
# Regression coverage for the bug fixed 2026-08-01: GiveCommand's
# weapon-auto-ready branch checked `isinstance(item, Weapon)` against
# item_system.Weapon, a class nothing in production code ever
# constructs -- every real weapon (armory purchases, items.resolve_weapon()
# reconstruction) is an items.Weapon instead, so the isinstance check was
# always False. A GIVEn weapon silently fell through to the generic "takes
# it and tucks it away" branch, ally.readied_weapon was never set, and a
# follow-up GIVE of matching ammo always hit "has no weapon readied" even
# though the player had just handed over the weapon. Fixed by importing
# the real items.Weapon. This test drives GiveCommand end-to-end with a
# real items.Weapon (built the way shoppe/armory.py builds one) rather
# than hand-assigning ally.readied_weapon, so a regression of the
# wrong-class import trips this test again.
# ---------------------------------------------------------------------------

def _make_weapon(name: str = '.357 MAGNUM', item_id: int = 145) -> Weapon:
    return Weapon(id_number=item_id, name=name, category=ItemCategory.WEAPON)


def _make_ammo(name: str = '.357 AMMO', item_id: int = 104,
               used_with: str = '.357 magnum', rounds: int = 6, damage: int = 4) -> Item:
    return Item(id_number=item_id, name=name, category=ItemCategory.ITEM,
                flags={'rounds': rounds, 'damage': damage, 'used_with': used_with})


class TestGiveWeaponAndAmmoToAlly(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.cmd = GiveCommand()
        self.player = _make_player()
        self.ally   = _make_ally('MYSTIC MORGANNA')
        self.player.party.add_member(self.player, self.ally)
        self.ctx = _FakeCtx(self.player)

    async def test_give_weapon_to_ally_readies_it(self):
        weapon = _make_weapon()
        self.player.inventory.add(weapon)
        await self.cmd.execute(self.ctx, '.357', 'magnum', 'to', 'morganna')

        self.assertIs(self.ally.readied_weapon, weapon)
        self.assertIn('READIES', self.ctx.sent().upper())
        self.assertEqual(len(self.player.inventory.entries()), 0)
        # See TestGiveToAlly.test_give_item_to_ally_marks_player_unsaved.
        self.assertTrue(self.player.unsaved_changes)

    async def test_give_matching_ammo_after_weapon_loads_it(self):
        weapon = _make_weapon()
        self.player.inventory.add(weapon)
        await self.cmd.execute(self.ctx, '.357', 'magnum', 'to', 'morganna')

        ammo = _make_ammo()
        self.player.inventory.add(ammo)
        self.player.unsaved_changes = False   # isolate this give's own effect
        await self.cmd.execute(self.ctx, '.357', 'ammo', 'to', 'morganna')

        self.assertEqual(self.ally.ammo_rounds, 6)
        self.assertEqual(self.ally.ammo_damage, 4)
        self.assertIn('LOADS', self.ctx.sent().upper())
        self.assertTrue(self.player.unsaved_changes)

    async def test_give_ammo_before_weapon_reports_no_weapon_readied(self):
        """The exact bug report: GIVE ammo with no weapon readied yet."""
        ammo = _make_ammo()
        self.player.inventory.add(ammo)
        await self.cmd.execute(self.ctx, '.357', 'ammo', 'to', 'morganna')

        self.assertIn('no weapon readied', self.ctx.sent().lower())
        self.assertEqual(self.ally.ammo_rounds, 0)

    async def test_give_mismatched_ammo_after_weapon_is_rejected(self):
        weapon = _make_weapon()
        self.player.inventory.add(weapon)
        await self.cmd.execute(self.ctx, '.357', 'magnum', 'to', 'morganna')

        wrong_ammo = _make_ammo(name='.44 AMMO', item_id=105, used_with='.44 magnum')
        self.player.inventory.add(wrong_ammo)
        await self.cmd.execute(self.ctx, '.44', 'ammo', 'to', 'morganna')

        self.assertIn('not for the', self.ctx.sent().lower())
        self.assertEqual(self.ally.ammo_rounds, 0)


class TestGiveArmorAndShieldToAlly(unittest.IsolatedAsyncioTestCase):
    # Bug: allies have no WEAR command, so GIVEing one an armor- or
    # shield-type Item fell all the way through to the generic plain-item
    # branch -- "{ally} takes the {item} and tucks it away", same wording
    # as a book or trinket, instead of anything suggesting it got worn.
    # Ryan's report, direct follow-up to the STATS "still shows READYed"
    # fix above.

    def setUp(self):
        self.cmd = GiveCommand()
        self.player = _make_player()
        self.ally   = _make_ally('THE BISHOP')
        self.player.party.add_member(self.player, self.ally)
        self.ctx = _FakeCtx(self.player)

    def _armor(self, name='CLOTH ARMOR', item_id=2):
        from item_system import ItemType
        item = _make_item(name, item_id=item_id, category=ItemCategory.ARMOR)
        item.type = ItemType.ARMOR
        return item

    def _shield(self, name='SMALL SHIELD', item_id=4):
        from item_system import ItemType
        item = _make_item(name, item_id=item_id, category=ItemCategory.ARMOR)
        item.type = ItemType.SHIELD
        return item

    async def test_give_armor_to_ally_wears_it(self):
        armor = self._armor()
        self.player.inventory.add(armor)
        await self.cmd.execute(self.ctx, 'cloth', 'armor', 'to', 'bishop')

        self.assertIs(self.ally.readied_armor, armor)
        self.assertIn('WEARS', self.ctx.sent().upper())
        self.assertNotIn('TUCKS', self.ctx.sent().upper())
        self.assertEqual(len(self.player.inventory.entries()), 0)
        self.assertEqual(self.ally.items[0].item, armor)
        self.assertTrue(self.player.unsaved_changes)

    async def test_give_shield_to_ally_straps_it_on(self):
        shield = self._shield()
        self.player.inventory.add(shield)
        await self.cmd.execute(self.ctx, 'small', 'shield', 'to', 'bishop')

        self.assertIs(self.ally.readied_shield, shield)
        self.assertIn('STRAPS ON', self.ctx.sent().upper())

    async def test_giving_second_armor_replaces_the_first(self):
        first  = self._armor('CLOTH ARMOR', item_id=2)
        second = self._armor('CHAINMAIL ARMOR', item_id=28)
        self.player.inventory.add(first)
        self.player.inventory.add(second)
        await self.cmd.execute(self.ctx, 'cloth', 'armor', 'to', 'bishop')
        await self.cmd.execute(self.ctx, 'chainmail', 'armor', 'to', 'bishop')

        self.assertIs(self.ally.readied_armor, second)
        # The replaced piece stays in the ally's pack rather than vanishing
        # -- same behavior as the Weapon branch's readied_weapon swap.
        self.assertEqual(len(self.ally.items), 2)

    async def test_give_worn_armor_to_ally_clears_players_active_armor_id(self):
        armor = self._armor()
        armor.condition = 100
        self.player.inventory.add(armor)
        self.player.active_armor_id = 2
        self.player.armor = 50

        await self.cmd.execute(self.ctx, 'cloth', 'armor', 'to', 'bishop')

        self.assertIsNone(self.player.active_armor_id)
        self.assertEqual(self.player.armor, 0)


# ---------------------------------------------------------------------------
# GiveCommand — mount carrying capacity (New in TADA, Ryan's request)
# ---------------------------------------------------------------------------

def _make_mount(name: str = 'TRIGGER', saddlebags: bool = False) -> Ally:
    from bar.ally_data import AllyFlags
    flags = [AllyFlags.MOUNT]
    if saddlebags:
        flags.append(AllyFlags.SADDLEBAGS)
    ally = Ally(name, 'm', 20, 0, flags=flags)
    ally.status = AllyStatus.SERVANT
    return ally


class TestGiveToMount(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.cmd = GiveCommand()
        self.player = _make_player()
        self.item   = _make_item('TORCH', item_id=5)
        self.player.inventory.add(self.item)
        self.ctx = _FakeCtx(self.player)

    async def test_mount_without_saddlebags_refuses_item(self):
        mount = _make_mount(saddlebags=False)
        self.player.party.add_member(self.player, mount)
        await self.cmd.execute(self.ctx, 'torch', 'to', 'trigger')
        self.assertEqual(len(mount.items), 0)
        self.assertIn('saddlebags', self.ctx.sent().lower())

    async def test_mount_without_saddlebags_item_stays_in_player_inventory(self):
        mount = _make_mount(saddlebags=False)
        self.player.party.add_member(self.player, mount)
        await self.cmd.execute(self.ctx, 'torch', 'to', 'trigger')
        self.assertEqual(len(self.player.inventory.entries()), 1)

    async def test_mount_with_saddlebags_accepts_item(self):
        mount = _make_mount(saddlebags=True)
        self.player.party.add_member(self.player, mount)
        await self.cmd.execute(self.ctx, 'torch', 'to', 'trigger')
        self.assertEqual(len(mount.items), 1)
        self.assertEqual(len(self.player.inventory.entries()), 0)

    async def test_mount_saddlebags_full_refuses_further_items(self):
        from commands.give import _MOUNT_CAPACITY_WITH_SADDLEBAGS
        mount = _make_mount(saddlebags=True)
        self.player.party.add_member(self.player, mount)
        for i in range(_MOUNT_CAPACITY_WITH_SADDLEBAGS):
            mount.items.append(InventoryEntry(item=_make_item(f'ITEM{i}', item_id=100 + i)))
        await self.cmd.execute(self.ctx, 'torch', 'to', 'trigger')
        self.assertEqual(len(mount.items), _MOUNT_CAPACITY_WITH_SADDLEBAGS)
        self.assertIn('full', self.ctx.sent().lower())

    async def test_non_mount_ally_still_unlimited(self):
        """Regular allies (not mounts) are unaffected by capacity."""
        ally = _make_ally('BATMAN')
        self.player.party.add_member(self.player, ally)
        await self.cmd.execute(self.ctx, 'torch', 'to', 'batman')
        self.assertEqual(len(ally.items), 1)

    async def test_giving_saddlebags_to_non_mount_shows_message(self):
        ally = _make_ally('BATMAN')
        self.player.party.add_member(self.player, ally)
        bags = _make_item('SADDLEBAGS', item_id=165)
        self.player.inventory.add(bags)
        await self.cmd.execute(self.ctx, 'saddlebags', 'to', 'batman')
        self.assertIn('no back to strap', self.ctx.sent().lower())

    async def test_giving_saddlebags_to_non_mount_still_completes(self):
        """The message is informational -- the give still happens, same
        as handing over any other object."""
        ally = _make_ally('BATMAN')
        self.player.party.add_member(self.player, ally)
        bags = _make_item('SADDLEBAGS', item_id=165)
        self.player.inventory.add(bags)
        await self.cmd.execute(self.ctx, 'saddlebags', 'to', 'batman')
        self.assertEqual(len(ally.items), 1)

    async def test_giving_saddlebags_to_mount_no_extra_message(self):
        mount = _make_mount(saddlebags=False)
        self.player.party.add_member(self.player, mount)
        bags = _make_item('SADDLEBAGS', item_id=165)
        self.player.inventory.add(bags)
        await self.cmd.execute(self.ctx, 'saddlebags', 'to', 'trigger')
        self.assertNotIn('no back to strap', self.ctx.sent().lower())


# ---------------------------------------------------------------------------
# GiveCommand — player targets
# ---------------------------------------------------------------------------

class TestGiveToPlayer(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.cmd    = GiveCommand()
        self.server = _FakeServer()

        # Giver
        self.giver  = _make_player('Rulan')
        self.item   = _make_item('SWORD', item_id=99,
                                 category=ItemCategory.WEAPON)
        self.giver.inventory.add(self.item)
        self.giver_client      = _FakeClient(room=5)
        self.server.clients['rulan'] = self.giver_client

        # Receiver in same room
        self.receiver = _make_player('Skye')
        self.recv_client      = _FakeClient(room=5)
        self.recv_client.player = self.receiver
        self.server.clients['skye'] = self.recv_client

        self.ctx = _FakeCtx(self.giver, server=self.server, room=5)

    async def test_give_to_player_removes_from_giver(self):
        await self.cmd.execute(self.ctx, 'sword', 'to', 'skye')
        self.assertEqual(len(self.giver.inventory.entries()), 0)

    async def test_give_to_player_marks_giver_unsaved(self):
        # Bug: only the receiver's unsaved_changes was set, not the
        # giver's -- the giver's own inventory loss never got persisted.
        self.assertFalse(self.giver.unsaved_changes)
        await self.cmd.execute(self.ctx, 'sword', 'to', 'skye')
        self.assertTrue(self.giver.unsaved_changes)

    async def test_give_to_player_adds_to_receiver(self):
        await self.cmd.execute(self.ctx, 'sword', 'to', 'skye')
        self.assertEqual(len(self.receiver.inventory.entries()), 1)

    async def test_give_to_player_in_different_room_fails(self):
        self.recv_client.room = 99   # different room
        await self.cmd.execute(self.ctx, 'sword', 'to', 'skye')
        # Item should not have transferred
        self.assertEqual(len(self.giver.inventory.entries()), 1)
        self.assertEqual(len(self.receiver.inventory.entries()), 0)

    async def test_give_to_player_full_inventory(self):
        self.receiver.inventory = Inventory(capacity=0)   # zero-slot inventory
        await self.cmd.execute(self.ctx, 'sword', 'to', 'skye')
        self.assertIn('cannot carry', self.ctx.sent().lower())
        self.assertEqual(len(self.giver.inventory.entries()), 1)

    async def test_give_stacked_item_to_player_gives_only_one_unit(self):
        # Same bug as test_give_stacked_item_to_ally_gives_only_one_unit,
        # different branch: other_inv.add(item, quantity=entry.quantity)
        # read the stack's *remaining* count -- after inventory.remove()
        # on the line just above it had already decremented that same
        # entry -- instead of the fixed 1 unit inventory.remove() actually
        # took off the giver's stack.
        ration = _make_item('RATION', item_id=5, kind='food')
        self.giver.inventory.add(ration, quantity=3)
        await self.cmd.execute(self.ctx, 'ration', 'to', 'skye')

        giver_rations = self.giver.inventory.find(item_id=5)
        self.assertEqual(len(giver_rations), 1)
        self.assertEqual(giver_rations[0].quantity, 2)
        receiver_rations = self.receiver.inventory.find(item_id=5)
        self.assertEqual(len(receiver_rations), 1)
        self.assertEqual(receiver_rations[0].quantity, 1)


# ---------------------------------------------------------------------------
# GiveCommand — monster targets
# ---------------------------------------------------------------------------

class TestGiveToMonster(unittest.IsolatedAsyncioTestCase):

    def _make_ctx_with_monster(self, monster_name='TROLL', m_hp=10):
        # Build a minimal game_map stub
        room_stub = MagicMock()
        room_stub.monster = 1   # matches monsters[0]'s 'number' below
        game_map = MagicMock()
        game_map.rooms.get.return_value = room_stub

        server = _FakeServer(
            game_map=game_map,
            monsters=[{'number': 1, 'name': monster_name, 'strength': m_hp}],
        )
        player = _make_player()
        return player, _FakeCtx(player, server=server, room=1)

    async def test_give_food_to_monster_consumes_item(self):
        player, ctx = self._make_ctx_with_monster('TROLL')
        item = _make_item('RATION', item_id=1, kind='food')
        player.inventory.add(item)
        await GiveCommand().execute(ctx, 'ration', 'to', 'troll')
        self.assertEqual(len(player.inventory.entries()), 0,
                         'food should be consumed by monster')

    async def test_give_weapon_to_monster_returns_item(self):
        player, ctx = self._make_ctx_with_monster('TROLL')
        item = _make_item('SWORD', item_id=2, category=ItemCategory.WEAPON)
        player.inventory.add(item)
        await GiveCommand().execute(ctx, 'sword', 'to', 'troll')
        self.assertEqual(len(player.inventory.entries()), 1,
                         'weapon should be handed back')

    async def test_give_gold_to_dragon_keeps_item(self):
        player, ctx = self._make_ctx_with_monster('DRAGON!')
        item = _make_item('GOLD COIN', item_id=3)
        player.inventory.add(item)
        await GiveCommand().execute(ctx, 'gold', 'to', 'dragon')
        self.assertEqual(len(player.inventory.entries()), 0,
                         'dragon should keep the gold')

    async def test_give_to_dead_monster_rejected(self):
        player, ctx = self._make_ctx_with_monster('TROLL', m_hp=0)
        item = _make_item('RATION', item_id=1, kind='food')
        player.inventory.add(item)
        await GiveCommand().execute(ctx, 'ration', 'to', 'troll')
        self.assertIn('dead', ctx.sent().lower())
        self.assertEqual(len(player.inventory.entries()), 1,
                         'item should not be consumed by a dead monster')


# ---------------------------------------------------------------------------
# TakeCommand
# ---------------------------------------------------------------------------

class TestTakeFromAlly(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.cmd    = TakeCommand()
        self.player = _make_player()
        self.ally   = _make_ally('GANDALF THE GREY')
        self.player.party.add_member(self.player, self.ally)

        # Give ally an item
        self.carried_item  = _make_item('LANTERN', item_id=10)
        carried_entry      = InventoryEntry(item=self.carried_item)
        self.ally.items    = [carried_entry]

        self.ctx = _FakeCtx(self.player)

    async def test_take_item_from_ally(self):
        await self.cmd.execute(self.ctx, 'lantern', 'from', 'gandalf')
        self.assertEqual(len(self.player.inventory.entries()), 1)
        self.assertEqual(len(self.ally.items), 0)

    async def test_take_item_lands_in_player_inventory(self):
        await self.cmd.execute(self.ctx, 'lantern', 'from', 'gandalf')
        entries = self.player.inventory.entries()
        self.assertEqual(entries[0].item.name, 'LANTERN')

    async def test_take_sends_confirmation(self):
        await self.cmd.execute(self.ctx, 'lantern', 'from', 'gandalf')
        self.assertIn('GANDALF', self.ctx.sent().upper())

    async def test_take_partial_item_name(self):
        await self.cmd.execute(self.ctx, 'lan', 'from', 'gandalf')
        self.assertEqual(len(self.player.inventory.entries()), 1)

    async def test_take_partial_ally_name(self):
        await self.cmd.execute(self.ctx, 'lantern', 'from', 'gand')
        self.assertEqual(len(self.player.inventory.entries()), 1)

    async def test_take_no_servants(self):
        self.player.party.remove(self.ally)
        await self.cmd.execute(self.ctx)
        self.assertIn('no servants', self.ctx.sent().lower())

    async def test_take_ally_carrying_nothing(self):
        self.ally.items = []
        await self.cmd.execute(self.ctx, 'from', 'gandalf')
        self.assertIn('not carrying', self.ctx.sent().lower())

    async def test_take_item_not_found(self):
        await self.cmd.execute(self.ctx, 'sword', 'from', 'gandalf')
        self.assertIn('sword', self.ctx.sent().lower())   # error names the missing item

    async def test_take_unknown_ally(self):
        await self.cmd.execute(self.ctx, 'lantern', 'from', 'nobody')
        self.assertIn('no servant named', self.ctx.sent().lower())

    async def test_take_full_inventory_rejected(self):
        self.player.inventory = Inventory(capacity=0)
        await self.cmd.execute(self.ctx, 'lantern', 'from', 'gandalf')
        self.assertIn('cannot carry', self.ctx.sent().lower())
        self.assertEqual(len(self.ally.items), 1,
                         'item should stay with ally when player is full')

    async def test_take_interactive_selection(self):
        """No item name → present numbered list; player picks by number."""
        self.ctx._prompt_answer = '1'
        await self.cmd.execute(self.ctx, 'from', 'gandalf')
        self.assertEqual(len(self.player.inventory.entries()), 1)

    async def test_take_bare_command_shows_all_allies(self):
        """'take' with no args lists everything across all servants."""
        second_ally = _make_ally('CONAN')
        extra_item  = _make_item('TORCH', item_id=20)
        second_ally.items = [InventoryEntry(item=extra_item)]
        self.player.party.add_member(self.player, second_ally)

        self.ctx._prompt_answer = '2'   # pick Conan's torch
        await self.cmd.execute(self.ctx)
        entries = self.player.inventory.entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item.name, 'TORCH')


# ---------------------------------------------------------------------------
# get command no longer aliases 'take'
# ---------------------------------------------------------------------------

class TestGetNoLongerAliasesTake(unittest.TestCase):
    def test_take_not_in_get_aliases(self):
        from commands.get import GetCommand
        self.assertNotIn('take', GetCommand.aliases)


# ---------------------------------------------------------------------------
# Body building: give food/drink to a weak ally
# ---------------------------------------------------------------------------

class TestBodyBuilding(unittest.IsolatedAsyncioTestCase):

    def _setup(self, ally_strength=8):
        player = _make_player()
        ally   = _make_ally(name='ALAN OF YOR', strength=ally_strength)
        player.party.add_member(player, ally)
        ctx    = _FakeCtx(player)
        cmd    = GiveCommand()
        return player, ally, ctx, cmd

    async def test_food_boosts_weak_ally_strength(self):
        player, ally, ctx, cmd = self._setup(ally_strength=8)
        food = _make_item('RATION', item_id=1, kind='food')
        player.inventory.add(food)
        await cmd.execute(ctx, 'ration', 'to', 'alan')
        self.assertEqual(ally.strength, 9)

    async def test_drink_boosts_weak_ally_strength(self):
        player, ally, ctx, cmd = self._setup(ally_strength=6)
        drink = _make_item('ALE', item_id=2, kind='drink')
        player.inventory.add(drink)
        await cmd.execute(ctx, 'ale', 'to', 'alan')
        self.assertEqual(ally.strength, 7)

    async def test_food_boost_shows_message(self):
        player, ally, ctx, cmd = self._setup(ally_strength=8)
        food = _make_item('RATION', item_id=1, kind='food')
        player.inventory.add(food)
        await cmd.execute(ctx, 'ration', 'to', 'alan')
        self.assertIn('stronger', ctx.sent().lower())

    async def test_strong_ally_no_boost(self):
        """Ally at or above strength cap gets no bonus."""
        player, ally, ctx, cmd = self._setup(ally_strength=11)
        food = _make_item('RATION', item_id=1, kind='food')
        player.inventory.add(food)
        await cmd.execute(ctx, 'ration', 'to', 'alan')
        self.assertEqual(ally.strength, 11)
        self.assertNotIn('stronger', ctx.sent().lower())

    async def test_non_food_no_boost(self):
        """Non-food items do not trigger body building."""
        player, ally, ctx, cmd = self._setup(ally_strength=8)
        sword = _make_item('SHORT SWORD', item_id=3, kind='', category=ItemCategory.WEAPON)
        player.inventory.add(sword)
        await cmd.execute(ctx, 'sword', 'to', 'alan')
        self.assertEqual(ally.strength, 8)

    async def test_cursed_food_weakens_ally(self):
        """Poisoned (cursed) ration reduces ally strength by 1."""
        player, ally, ctx, cmd = self._setup(ally_strength=8)
        cursed = _make_item('CURSED RATION', item_id=4, kind='cursed')
        player.inventory.add(cursed)
        await cmd.execute(ctx, 'cursed', 'to', 'alan')
        self.assertEqual(ally.strength, 7)

    async def test_cursed_food_shows_sickness_message(self):
        player, ally, ctx, cmd = self._setup(ally_strength=8)
        cursed = _make_item('CURSED RATION', item_id=4, kind='cursed')
        player.inventory.add(cursed)
        await cmd.execute(ctx, 'cursed', 'to', 'alan')
        self.assertIn('wrong with that food', ctx.sent().lower())

    async def test_cursed_food_floors_at_one(self):
        """Strength cannot drop below 1 from cursed food."""
        player, ally, ctx, cmd = self._setup(ally_strength=1)
        cursed = _make_item('CURSED RATION', item_id=4, kind='cursed')
        player.inventory.add(cursed)
        await cmd.execute(ctx, 'cursed', 'to', 'alan')
        self.assertEqual(ally.strength, 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main()
