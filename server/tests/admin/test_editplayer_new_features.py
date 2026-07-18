"""tests/test_editplayer_new_features.py

Unit tests for the nine commands/editplayer.py menu items that were stubbed
out with _not_implemented() before this session:

  - Armor/Shield menu    (main menu)
  - Map Information menu (main menu)
  - Weapons menu         (main menu: readied weapon, battle experience)
  - Character Names      (Ally 1-3, Horse rename)
  - Statistics           (Birthday, Experience, Moves to date, Monsters killed)

Run with:
    python -m pytest tests/test_editplayer_new_features.py -v
"""
from __future__ import annotations

import unittest
from datetime import date, datetime

from base_classes import Alignment, PlayerClass, PlayerRace, PlayerStat
from bar.ally_data import Ally, AllyFlags, AllyStatus
from party import Party
from commands.editplayer import (
    _armor_shield_menu,
    _combinations_menu,
    _give_object,
    _give_ration,
    _give_weapon,
    _inventory_action,
    _map_info_menu,
    _names_menu,
    _statistics_menu,
    _weapons_menu,
)


class _FakeWeapon:
    def __init__(self, id_number, name):
        self.id_number = id_number
        self.name = name


class _FakeServer:
    def __init__(self, weapons=None, monsters=None):
        self.weapons = weapons or []
        self.monsters = monsters or []


class _FakePlayer:
    def __init__(self):
        self.name = 'Rulan'
        self.age = 0
        self.armor = 0
        self.shield = 0
        self.map_level = 1
        self.map_room = 1
        self.readied_weapon = None
        self.weapon_experience: dict = {}
        self.birthday = None
        self.xp_level = 1
        self.experience = 0
        self.moves_today = 0
        self.dead_monsters: list = []
        self.read_books: list = []
        self.party = Party()
        self.unsaved_changes = False
        self.char_class = None
        self.char_race = None
        self.guild = None
        self.is_expert = True


class _FakeCtx:
    def __init__(self, responses=None, player=None, server=None):
        self._q = list(responses or [])
        self.sent: list[str] = []
        self.player = player or _FakePlayer()
        self.server = server or _FakeServer()

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


def _make_mount(name='SILVER'):
    a = Ally(name=name, gender='m', strength=20, to_hit=0, flags=[AllyFlags.MOUNT])
    a.status = AllyStatus.SERVANT
    return a


def _make_ally(name='EMMETT "DOC" BROWN'):
    a = Ally(name=name, gender='m', strength=10, to_hit=5, flags=[])
    a.status = AllyStatus.SERVANT
    return a


# ---------------------------------------------------------------------------
# Armor/Shield
# ---------------------------------------------------------------------------

class TestArmorShieldMenu(unittest.IsolatedAsyncioTestCase):

    async def test_set_armor(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['40'], player=player)
        menu = _armor_shield_menu(ctx)
        await _find_item(menu, 'Armor').action(ctx)
        self.assertEqual(player.armor, 40)
        self.assertTrue(player.unsaved_changes)

    async def test_set_shield(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['25'], player=player)
        menu = _armor_shield_menu(ctx)
        await _find_item(menu, 'Shield').action(ctx)
        self.assertEqual(player.shield, 25)

    async def test_cancel_leaves_unchanged(self):
        player = _FakePlayer()
        player.armor = 10
        ctx = _FakeCtx(responses=[''], player=player)
        menu = _armor_shield_menu(ctx)
        await _find_item(menu, 'Armor').action(ctx)
        self.assertEqual(player.armor, 10)


# ---------------------------------------------------------------------------
# Map Information
# ---------------------------------------------------------------------------

class TestMapInfoMenu(unittest.IsolatedAsyncioTestCase):

    async def test_set_dungeon_level(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['5'], player=player)
        menu = _map_info_menu(ctx)
        await _find_item(menu, 'Dungeon Level').action(ctx)
        self.assertEqual(player.map_level, 5)

    async def test_dungeon_level_rejects_out_of_range(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['9', ''], player=player)
        menu = _map_info_menu(ctx)
        await _find_item(menu, 'Dungeon Level').action(ctx)
        self.assertEqual(player.map_level, 1)   # unchanged -- 9 rejected, then cancel

    async def test_set_room_number(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['157'], player=player)
        menu = _map_info_menu(ctx)
        await _find_item(menu, 'Room Number').action(ctx)
        self.assertEqual(player.map_room, 157)


# ---------------------------------------------------------------------------
# Weapons
# ---------------------------------------------------------------------------

class TestWeaponsMenu(unittest.IsolatedAsyncioTestCase):

    async def test_readied_weapon_dot_leader_shows_none(self):
        player = _FakePlayer()
        ctx = _FakeCtx(player=player)
        menu = _weapons_menu(ctx)
        item = _find_item(menu, 'Readied Weapon')
        self.assertEqual(item.dot_leader_handler(ctx), '(none)')

    async def test_readied_weapon_dot_leader_shows_name(self):
        player = _FakePlayer()
        player.readied_weapon = _FakeWeapon(1, 'LONG SWORD')
        ctx = _FakeCtx(player=player)
        menu = _weapons_menu(ctx)
        item = _find_item(menu, 'Readied Weapon')
        self.assertEqual(item.dot_leader_handler(ctx), 'LONG SWORD')

    async def test_unready_via_change_prompt(self):
        """Bug fix: this menu action used to only ever clear the readied
        weapon -- it now offers Change/Unready when one is already
        readied, reusing the real UnreadyCommand for the 'U' choice."""
        player = _FakePlayer()
        player.readied_weapon = _FakeWeapon(1, 'LONG SWORD')
        ctx = _FakeCtx(responses=['u'], player=player)
        menu = _weapons_menu(ctx)
        await _find_item(menu, 'Readied Weapon').action(ctx)
        self.assertIsNone(player.readied_weapon)
        self.assertIn('repack', ctx.sent[-1].lower())

    async def test_cancel_leaves_readied_weapon_unchanged(self):
        player = _FakePlayer()
        weapon = _FakeWeapon(1, 'LONG SWORD')
        player.readied_weapon = weapon
        ctx = _FakeCtx(responses=[''], player=player)
        menu = _weapons_menu(ctx)
        await _find_item(menu, 'Readied Weapon').action(ctx)
        self.assertIs(player.readied_weapon, weapon)

    async def test_no_weapons_to_ready_when_none_readied_and_inventory_empty(self):
        player = _FakePlayer()
        ctx = _FakeCtx(player=player)
        menu = _weapons_menu(ctx)
        await _find_item(menu, 'Readied Weapon').action(ctx)
        self.assertIn('no weapons to ready', ctx.sent[-1].lower())

    async def test_selecting_a_weapon_from_inventory_readies_it(self):
        """The actual bug: 'Readied Weapon' must scan inventory and let
        an admin pick a weapon to ready, not just clear the current one."""
        from inventory import Inventory
        from items import Weapon

        player = _FakePlayer()
        player.inventory = Inventory(capacity=10)
        player.stats = {PlayerStat.STR: 10}
        sword = Weapon(id_number=5, name='Long Sword', stability=10, to_hit=5)
        player.inventory.add(sword)

        ctx = _FakeCtx(responses=['1'], player=player)
        menu = _weapons_menu(ctx)
        await _find_item(menu, 'Readied Weapon').action(ctx)

        self.assertIsNotNone(player.readied_weapon)
        self.assertEqual(getattr(player.readied_weapon, 'name', ''), 'Long Sword')

    async def test_change_prompt_can_switch_to_a_different_weapon(self):
        from inventory import Inventory
        from items import Weapon

        player = _FakePlayer()
        player.inventory = Inventory(capacity=10)
        player.stats = {PlayerStat.STR: 10}
        old = Weapon(id_number=1, name='Dagger')
        new = Weapon(id_number=2, name='Axe')
        player.readied_weapon = old
        player.inventory.add(new)

        # 'c' to change, then '1' to pick the (only) weapon in inventory.
        ctx = _FakeCtx(responses=['c', '1'], player=player)
        menu = _weapons_menu(ctx)
        await _find_item(menu, 'Readied Weapon').action(ctx)

        self.assertEqual(getattr(player.readied_weapon, 'name', ''), 'Axe')

    async def test_battle_experience_is_a_submenu_of_weapons(self):
        server = _FakeServer(weapons=[{'number': 42, 'name': 'LONG SWORD'}])
        ctx = _FakeCtx(server=server)
        menu = _weapons_menu(ctx)
        item = _find_item(menu, 'Battle Experience')
        self.assertIsNotNone(item.submenu)
        self.assertEqual(item.submenu.rendered_title, 'Battle Experience')

    async def test_battle_experience_lists_every_weapon(self):
        server = _FakeServer(weapons=[
            {'number': 42, 'name': 'LONG SWORD'},
            {'number': 7, 'name': 'DAGGER'},
        ])
        ctx = _FakeCtx(server=server)
        menu = _weapons_menu(ctx)
        be_menu = _find_item(menu, 'Battle Experience').submenu
        labels = [i.text for i in be_menu.menu_items]
        self.assertIn('LONG SWORD', labels)
        self.assertIn('DAGGER', labels)

    async def test_battle_experience_dot_leader_shows_current_value(self):
        player = _FakePlayer()
        player.weapon_experience = {'42': 30}
        server = _FakeServer(weapons=[{'number': 42, 'name': 'LONG SWORD'}])
        ctx = _FakeCtx(player=player, server=server)
        menu = _weapons_menu(ctx)
        be_menu = _find_item(menu, 'Battle Experience').submenu
        item = _find_item(be_menu, 'LONG SWORD')
        self.assertEqual(item.dot_leader_handler(ctx), '30')

    async def test_set_battle_experience_absolute(self):
        player = _FakePlayer()
        server = _FakeServer(weapons=[{'number': 42, 'name': 'LONG SWORD'}])
        ctx = _FakeCtx(responses=['50'], player=player, server=server)
        menu = _weapons_menu(ctx)
        be_menu = _find_item(menu, 'Battle Experience').submenu
        await _find_item(be_menu, 'LONG SWORD').action(ctx)
        self.assertEqual(player.weapon_experience.get('42'), 50)

    async def test_battle_experience_relative_increase(self):
        player = _FakePlayer()
        player.weapon_experience = {'42': 30}
        server = _FakeServer(weapons=[{'number': 42, 'name': 'LONG SWORD'}])
        ctx = _FakeCtx(responses=['+10'], player=player, server=server)
        menu = _weapons_menu(ctx)
        be_menu = _find_item(menu, 'Battle Experience').submenu
        await _find_item(be_menu, 'LONG SWORD').action(ctx)
        self.assertEqual(player.weapon_experience.get('42'), 40)

    async def test_battle_experience_relative_decrease(self):
        player = _FakePlayer()
        player.weapon_experience = {'42': 30}
        server = _FakeServer(weapons=[{'number': 42, 'name': 'LONG SWORD'}])
        ctx = _FakeCtx(responses=['-10'], player=player, server=server)
        menu = _weapons_menu(ctx)
        be_menu = _find_item(menu, 'Battle Experience').submenu
        await _find_item(be_menu, 'LONG SWORD').action(ctx)
        self.assertEqual(player.weapon_experience.get('42'), 20)

    async def test_battle_experience_relative_out_of_range_rejected(self):
        player = _FakePlayer()
        player.weapon_experience = {'42': 95}
        server = _FakeServer(weapons=[{'number': 42, 'name': 'LONG SWORD'}])
        ctx = _FakeCtx(responses=['+10', ''], player=player, server=server)
        menu = _weapons_menu(ctx)
        be_menu = _find_item(menu, 'Battle Experience').submenu
        await _find_item(be_menu, 'LONG SWORD').action(ctx)
        self.assertEqual(player.weapon_experience.get('42'), 95)   # unchanged
        self.assertIn('between 0 and 99', ctx.sent[-2])


# ---------------------------------------------------------------------------
# Character Names — Ally slots + Horse
# ---------------------------------------------------------------------------

class TestNamesMenuAllyAndHorse(unittest.IsolatedAsyncioTestCase):

    async def test_rename_ally_in_slot(self):
        ally = _make_ally('EMMETT "DOC" BROWN')
        player = _FakePlayer()
        player.party = Party(members=[ally])
        ctx = _FakeCtx(responses=['MARTY'], player=player)
        menu = _names_menu(ctx)
        await _find_item(menu, 'Ally 1').action(ctx)
        self.assertEqual(ally.name, 'MARTY')
        self.assertTrue(player.unsaved_changes)

    async def test_second_empty_slot_reports_no_ally(self):
        """Only the first empty slot offers to add -- allies are a flat
        list, not real numbered slots, so a higher slot number with an
        earlier slot still empty just reports read-only as before."""
        player = _FakePlayer()
        player.party = Party(members=[_make_ally('EMMETT "DOC" BROWN')])  # fills slot 1
        ctx = _FakeCtx(player=player)
        menu = _names_menu(ctx)
        await _find_item(menu, 'Ally 3').action(ctx)  # slot 2 -- not next-available (slot 1 is)
        self.assertIn('No ally in that slot', ctx.sent[-1])

    async def test_rename_ally_cancel_leaves_unchanged(self):
        ally = _make_ally('EMMETT "DOC" BROWN')
        player = _FakePlayer()
        player.party = Party(members=[ally])
        ctx = _FakeCtx(responses=[''], player=player)
        menu = _names_menu(ctx)
        await _find_item(menu, 'Ally 1').action(ctx)
        self.assertEqual(ally.name, 'EMMETT "DOC" BROWN')

    async def test_rename_horse(self):
        mount = _make_mount('SILVER')
        player = _FakePlayer()
        player.party = Party(members=[mount])
        ctx = _FakeCtx(responses=['SHADOWFAX'], player=player)
        menu = _names_menu(ctx)
        await _find_item(menu, 'Horse').action(ctx)
        self.assertEqual(mount.name, 'SHADOWFAX')

    async def test_no_horse_owned(self):
        player = _FakePlayer()
        player.party = Party(members=[_make_ally('EMMETT "DOC" BROWN')])   # no MOUNT flag
        ctx = _FakeCtx(player=player)
        menu = _names_menu(ctx)
        await _find_item(menu, 'Horse').action(ctx)
        self.assertIn('No horse owned', ctx.sent[-1])


class TestNamesMenuAddAlly(unittest.IsolatedAsyncioTestCase):
    """Empty-slot "add ally?" flow (Ryan's request): first empty slot
    offers Y/N/? add-an-ally prompt, backed by bar/allies.py's pick_ally()
    numbered picker over the master roster's AllyStatus.FREE entries."""

    def _free_master_list(self):
        return [
            Ally(name='GANDALF', gender='m', strength=30, to_hit=8),
            Ally(name='ARAGORN', gender='m', strength=25, to_hit=9),
        ]

    async def test_decline_leaves_slot_empty(self):
        player = _FakePlayer()
        player.party = Party()
        ctx = _FakeCtx(responses=['N'], player=player)
        menu = _names_menu(ctx)
        await _find_item(menu, 'Ally 1').action(ctx)
        self.assertEqual(len(player.party), 0)

    async def test_blank_response_leaves_slot_empty(self):
        player = _FakePlayer()
        player.party = Party()
        ctx = _FakeCtx(responses=[''], player=player)
        menu = _names_menu(ctx)
        await _find_item(menu, 'Ally 1').action(ctx)
        self.assertEqual(len(player.party), 0)

    async def test_yes_then_pick_adds_ally_as_servant(self):
        from unittest.mock import patch
        player = _FakePlayer()
        player.party = Party()
        ctx = _FakeCtx(responses=['Y', '1'], player=player)
        menu = _names_menu(ctx)
        with patch('bar.ally_data.load_allies', return_value=self._free_master_list()), \
             patch('bar.ally_data.save_ally_roster') as mock_save:
            await _find_item(menu, 'Ally 1').action(ctx)
        self.assertEqual(len(player.party), 1)
        added = list(player.party)[0]
        self.assertEqual(added.name, 'GANDALF')
        self.assertEqual(added.status, AllyStatus.SERVANT)
        self.assertEqual(added.owner, player.name)
        self.assertEqual(added.hit_points, added.strength * 2)
        mock_save.assert_called_once()
        self.assertTrue(player.unsaved_changes)

    async def test_question_mark_skips_straight_to_picker(self):
        from unittest.mock import patch
        player = _FakePlayer()
        player.party = Party()
        ctx = _FakeCtx(responses=['?', '2'], player=player)
        menu = _names_menu(ctx)
        with patch('bar.ally_data.load_allies', return_value=self._free_master_list()), \
             patch('bar.ally_data.save_ally_roster'):
            await _find_item(menu, 'Ally 1').action(ctx)
        self.assertEqual(len(player.party), 1)
        self.assertEqual(list(player.party)[0].name, 'ARAGORN')

    async def test_picker_cancel_leaves_slot_empty(self):
        from unittest.mock import patch
        player = _FakePlayer()
        player.party = Party()
        ctx = _FakeCtx(responses=['Y', ''], player=player)
        menu = _names_menu(ctx)
        with patch('bar.ally_data.load_allies', return_value=self._free_master_list()), \
             patch('bar.ally_data.save_ally_roster') as mock_save:
            await _find_item(menu, 'Ally 1').action(ctx)
        self.assertEqual(len(player.party), 0)
        mock_save.assert_not_called()

    async def test_already_owned_allies_excluded_from_picker(self):
        from unittest.mock import patch
        owned = _make_ally('GANDALF')
        player = _FakePlayer()
        player.party = Party(members=[owned])
        ctx = _FakeCtx(responses=['Y', '1'], player=player)
        menu = _names_menu(ctx)
        with patch('bar.ally_data.load_allies', return_value=self._free_master_list()), \
             patch('bar.ally_data.save_ally_roster'):
            await _find_item(menu, 'Ally 2').action(ctx)  # slot 1, next available
        self.assertEqual(len(player.party), 2)
        # GANDALF is already owned, so choice "1" from the remaining pool is ARAGORN.
        self.assertEqual(list(player.party)[1].name, 'ARAGORN')

    async def test_no_available_allies(self):
        from unittest.mock import patch
        player = _FakePlayer()
        player.party = Party()
        ctx = _FakeCtx(responses=['Y'], player=player)
        menu = _names_menu(ctx)
        with patch('bar.ally_data.load_allies', return_value=[]), \
             patch('bar.ally_data.save_ally_roster') as mock_save:
            await _find_item(menu, 'Ally 1').action(ctx)
        self.assertIn('No allies available to add.', ctx.sent[-1])
        mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# Statistics — Birthday, Experience, Moves to date, Monsters killed
# ---------------------------------------------------------------------------

class TestStatisticsBirthday(unittest.IsolatedAsyncioTestCase):
    """Birthday's year is always derived from age (current_year - age) --
    see characters.birthday_for_age() -- so only MM-DD is ever prompted."""

    async def test_set_birthday_derives_year_from_age(self):
        player = _FakePlayer()
        player.age = 30
        ctx = _FakeCtx(responses=['06-16'], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Birthday').action(ctx)
        self.assertEqual(player.birthday.month, 6)
        self.assertEqual(player.birthday.day, 16)
        self.assertEqual(player.birthday.year, date.today().year - 30)

    async def test_set_birthday_month_day_only(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['12-25'], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Birthday').action(ctx)
        self.assertEqual(player.birthday.month, 12)
        self.assertEqual(player.birthday.day, 25)

    async def test_extra_year_component_is_ignored(self):
        # Old MM-DD-YYYY format still parses (only the first two parts are
        # used) -- the year is always derived from age, never accepted.
        player = _FakePlayer()
        player.age = 30
        ctx = _FakeCtx(responses=['06-16-1901'], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Birthday').action(ctx)
        self.assertEqual(player.birthday.year, date.today().year - 30)

    async def test_invalid_birthday_rejected(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['13-40'], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Birthday').action(ctx)
        self.assertIsNone(player.birthday)
        self.assertIn('Invalid date', ctx.sent[-1])

    async def test_cancel_leaves_birthday_unset(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=[''], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Birthday').action(ctx)
        self.assertIsNone(player.birthday)


class TestStatisticsAgeKeepsBirthdayInSync(unittest.IsolatedAsyncioTestCase):

    async def test_changing_age_recomputes_birthday_year(self):
        player = _FakePlayer()
        player.age = 30
        player.birthday = datetime(date.today().year - 30, 6, 16)
        ctx = _FakeCtx(responses=['40'], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Age').action(ctx)
        self.assertEqual(player.age, 40)
        self.assertEqual(player.birthday.month, 6)
        self.assertEqual(player.birthday.day, 16)
        self.assertEqual(player.birthday.year, date.today().year - 40)

    async def test_changing_age_with_no_birthday_set_is_a_no_op(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['25'], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Age').action(ctx)
        self.assertEqual(player.age, 25)
        self.assertIsNone(player.birthday)


class TestStatisticsExperience(unittest.IsolatedAsyncioTestCase):

    async def test_set_level_and_experience(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['5', '1200'], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Experience').action(ctx)
        self.assertEqual(player.xp_level, 5)
        self.assertEqual(player.experience, 1200)

    async def test_cancel_level_still_allows_experience(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['', '500'], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Experience').action(ctx)
        self.assertEqual(player.xp_level, 1)   # unchanged
        self.assertEqual(player.experience, 500)

    async def test_dot_leader_shows_level_and_experience(self):
        player = _FakePlayer()
        player.xp_level = 3
        player.experience = 42
        ctx = _FakeCtx(player=player)
        menu = _statistics_menu(ctx)
        item = _find_item(menu, 'Experience')
        self.assertEqual(item.dot_leader_handler(ctx), 'L3 / 42')


class TestStatisticsMoves(unittest.IsolatedAsyncioTestCase):

    async def test_set_moves_today(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['999'], player=player)
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Moves to date').action(ctx)
        self.assertEqual(player.moves_today, 999)


class TestStatisticsMonstersKilled(unittest.IsolatedAsyncioTestCase):

    def _server(self):
        return _FakeServer(monsters=[
            {'number': 1, 'name': 'GOBLIN'},
            {'number': 2, 'name': 'TROLL'},
        ])

    async def test_add_monster(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['a', 'GOBLIN', 'q'], player=player, server=self._server())
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Monsters killed').action(ctx)
        self.assertEqual(player.dead_monsters, [1])

    async def test_add_duplicate_monster_refused(self):
        player = _FakePlayer()
        player.dead_monsters = [1]
        ctx = _FakeCtx(responses=['a', 'GOBLIN', 'q'], player=player, server=self._server())
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Monsters killed').action(ctx)
        self.assertEqual(player.dead_monsters, [1])
        self.assertIn('already on the kill list', '\n'.join(ctx.sent))

    async def test_remove_monster(self):
        player = _FakePlayer()
        player.dead_monsters = [1, 2]
        ctx = _FakeCtx(responses=['r', '1', 'q'], player=player, server=self._server())
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Monsters killed').action(ctx)
        self.assertEqual(player.dead_monsters, [2])

    async def test_dot_leader_shows_count(self):
        player = _FakePlayer()
        player.dead_monsters = [1, 2, 3]
        ctx = _FakeCtx(player=player)
        menu = _statistics_menu(ctx)
        item = _find_item(menu, 'Monsters killed')
        self.assertEqual(item.dot_leader_handler(ctx), '3')

    async def test_quit_immediately_makes_no_changes(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['q'], player=player, server=self._server())
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Monsters killed').action(ctx)
        self.assertEqual(player.dead_monsters, [])


# ---------------------------------------------------------------------------
# Class/Race compatibility warning (characters.is_class_race_compatible(),
# shared with commands/new_player.py's validate_class_race_combo())
# ---------------------------------------------------------------------------

class TestClassRaceCompatibilityWarning(unittest.IsolatedAsyncioTestCase):

    async def test_setting_class_onto_incompatible_race_warns(self):
        player = _FakePlayer()
        player.char_race = PlayerRace.OGRE
        ctx = _FakeCtx(responses=['1'], player=player)   # 1 = Wizard
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Class').action(ctx)
        self.assertEqual(player.char_class, PlayerClass.WIZARD)
        self.assertIn('not normally a valid combination', '\n'.join(ctx.sent))

    async def test_setting_race_onto_incompatible_class_warns(self):
        player = _FakePlayer()
        player.char_class = PlayerClass.WIZARD
        ctx = _FakeCtx(responses=['2'], player=player)   # 2 = Ogre
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Race').action(ctx)
        self.assertEqual(player.char_race, PlayerRace.OGRE)
        self.assertIn('not normally a valid combination', '\n'.join(ctx.sent))

    async def test_compatible_combo_no_warning(self):
        player = _FakePlayer()
        player.char_race = PlayerRace.HUMAN
        ctx = _FakeCtx(responses=['3'], player=player)   # 3 = Fighter
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Class').action(ctx)
        self.assertEqual(player.char_class, PlayerClass.FIGHTER)
        self.assertNotIn('not normally a valid combination', '\n'.join(ctx.sent))

    async def test_incompatible_combo_still_applies_the_change(self):
        # Non-blocking by design: an admin editing class/race one field at a
        # time can end up with an "invalid" combo mid-edit; this only warns.
        player = _FakePlayer()
        player.char_race = PlayerRace.OGRE
        ctx = _FakeCtx(responses=['1'], player=player)   # 1 = Wizard
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Class').action(ctx)
        self.assertEqual(player.char_class, PlayerClass.WIZARD)   # not reverted
        self.assertTrue(player.unsaved_changes)

    async def test_race_not_yet_set_no_warning(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['1'], player=player)   # 1 = Wizard, no race set
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Class').action(ctx)
        self.assertNotIn('not normally a valid combination', '\n'.join(ctx.sent))


# ---------------------------------------------------------------------------
# Natural alignment reporting on class/race edit
# (characters.apply_natural_alignment(), see tests/test_characters.py for
# the underlying table)
# ---------------------------------------------------------------------------

class TestNaturalAlignmentReporting(unittest.IsolatedAsyncioTestCase):

    async def test_setting_race_to_ogre_reports_updated(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['2'], player=player)   # 2 = Ogre
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Race').action(ctx)
        self.assertEqual(player.natural_alignment, Alignment.EVIL)
        self.assertIn('Natural alignment updated to Evil.', ctx.sent)

    async def test_setting_race_to_human_reports_unchanged(self):
        # Human's natural alignment (Neutral) matches the player's unset
        # (None) starting value... no: unset -> None != NEUTRAL, so this
        # is still an update the first time. Confirm a *second* edit that
        # doesn't change the resulting alignment reports "unchanged".
        player = _FakePlayer()
        player.char_race = PlayerRace.HUMAN
        player.natural_alignment = Alignment.NEUTRAL
        ctx = _FakeCtx(responses=['3'], player=player)   # 3 = Fighter
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Class').action(ctx)
        self.assertIn('Natural alignment unchanged (Neutral).', ctx.sent)

    async def test_setting_class_alone_still_reports_alignment(self):
        # Alignment is race-driven only, but editing class re-reports the
        # (unchanged) alignment so an admin sees consistent feedback either
        # way (SPUR.MISC5.S:196-199).
        player = _FakePlayer()
        player.char_race = PlayerRace.OGRE
        player.natural_alignment = Alignment.EVIL
        ctx = _FakeCtx(responses=['1'], player=player)   # 1 = Wizard
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Class').action(ctx)
        self.assertIn('Natural alignment unchanged (Evil).', ctx.sent)

    async def test_switching_race_updates_alignment(self):
        player = _FakePlayer()
        player.char_race = PlayerRace.OGRE
        player.natural_alignment = Alignment.EVIL
        ctx = _FakeCtx(responses=['4'], player=player)   # 4 = Elf
        menu = _statistics_menu(ctx)
        await _find_item(menu, 'Race').action(ctx)
        self.assertEqual(player.natural_alignment, Alignment.GOOD)
        self.assertIn('Natural alignment updated to Good.', ctx.sent)


class TestCombinationsMenuClear(unittest.IsolatedAsyncioTestCase):
    """'X' in the Combinations menu clears a combination by setting its
    .combination (the 3-number tuple) to None -- it does NOT remove the
    Combination object or any of its dict alias keys (combo_type/.value/
    .name all point at the same object), so _fmt()'s existing 'obj is
    None -> (none)' fallback isn't what renders it as cleared; rather
    str(None or '(none)') does, once .combination itself is None."""

    def _seeded_player(self):
        from base_classes import Combination, CombinationTypes
        player = _FakePlayer()
        combo_type = CombinationTypes.CASTLE
        combo = Combination(combo_type)
        combo.combination = (40, 10, 5)
        player.combinations = {
            combo_type: combo,
            combo_type.value: combo,
            combo_type.name: combo,
        }
        return player, combo_type

    async def test_x_clears_the_combination_tuple(self):
        from base_classes import CombinationTypes
        player, combo_type = self._seeded_player()
        ctx = _FakeCtx(responses=['x'], player=player)
        menu = _combinations_menu(ctx)
        await _find_item(menu, combo_type.value).action(ctx)

        self.assertIsNone(player.combinations[CombinationTypes.CASTLE].combination)
        self.assertIn(f'{combo_type.value} cleared.', ctx.sent)

    async def test_clear_updates_all_alias_keys_at_once(self):
        """All three keys reference the same object, so clearing via any
        one of them is visible through the other two as well."""
        player, combo_type = self._seeded_player()
        ctx = _FakeCtx(responses=['x'], player=player)
        menu = _combinations_menu(ctx)
        await _find_item(menu, combo_type.value).action(ctx)

        self.assertIsNone(player.combinations[combo_type.value].combination)
        self.assertIsNone(player.combinations[combo_type.name].combination)

    async def test_clear_with_no_existing_combination_does_not_crash(self):
        player = _FakePlayer()
        player.combinations = {}
        ctx = _FakeCtx(responses=['x'], player=player)
        menu = _combinations_menu(ctx)
        from base_classes import CombinationTypes
        await _find_item(menu, CombinationTypes.CASTLE.value).action(ctx)
        self.assertIn(f'{CombinationTypes.CASTLE.value} cleared.', ctx.sent)

    async def test_blank_leaves_combination_unchanged(self):
        player, combo_type = self._seeded_player()
        ctx = _FakeCtx(responses=[''], player=player)
        menu = _combinations_menu(ctx)
        await _find_item(menu, combo_type.value).action(ctx)

        self.assertEqual(player.combinations[combo_type].combination, (40, 10, 5))
        self.assertIn('Combination unchanged.', ctx.sent)

    async def test_setting_new_combination_after_clear(self):
        player, combo_type = self._seeded_player()
        ctx = _FakeCtx(responses=['x'], player=player)
        menu = _combinations_menu(ctx)
        await _find_item(menu, combo_type.value).action(ctx)

        ctx2 = _FakeCtx(responses=['07-08-09'], player=player)
        menu2 = _combinations_menu(ctx2)
        await _find_item(menu2, combo_type.value).action(ctx2)

        self.assertEqual(player.combinations[combo_type].combination, (7, 8, 9))


class TestInventoryActionPreamble(unittest.IsolatedAsyncioTestCase):
    """The inventory menu's option list moved from the prompt_text (which
    word-wrapped on narrower screens) into preamble_lines."""

    async def test_options_in_preamble_not_prompt_text(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['q'], player=player)
        await _inventory_action(ctx)(ctx)

        # First prompt() call is the menu prompt (after _show_inventory's
        # own ctx.send()); its preamble should carry every option, and the
        # prompt text itself should be short.
        prompt_calls = [c for c in ctx.sent]  # _FakeCtx.send() records preamble too
        flat = '\n'.join(prompt_calls)
        self.assertIn('[W]eapon', flat)
        self.assertIn('[L]ist weapons', flat)
        self.assertIn('[Q]uit', flat)

    async def test_quit_exits_the_loop(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['q'], player=player)
        await _inventory_action(ctx)(ctx)  # would hang/raise if the loop didn't exit

    async def test_unknown_command_reports_and_reprompts(self):
        player = _FakePlayer()
        ctx = _FakeCtx(responses=['z', 'q'], player=player)
        await _inventory_action(ctx)(ctx)
        self.assertIn('Unknown option.', ctx.sent)


class TestGiveItemQuestionMarkListsAll(unittest.IsolatedAsyncioTestCase):
    """'?' at any 'type part of the name' prompt lists every item of that
    type, then re-prompts for a name -- instead of only being reachable
    via the separate top-level 'L' (list weapons) menu option."""

    async def test_give_weapon_question_mark_lists_all(self):
        server = _FakeServer(weapons=[
            {'number': 1, 'name': 'Sword', 'weapon_class': 'hack_slash_bash', 'stability': 10},
            {'number': 2, 'name': 'Axe', 'weapon_class': 'hack_slash_bash', 'stability': 12},
        ])
        ctx = _FakeCtx(responses=['?', ''], player=_FakePlayer(), server=server)
        await _give_weapon(ctx)
        self.assertIn('Weapons (2):', ctx.sent)
        self.assertTrue(any('Sword' in s for s in ctx.sent))
        self.assertTrue(any('Axe' in s for s in ctx.sent))

    async def test_give_ration_question_mark_lists_all(self):
        server = _FakeServer()
        server.rations = [
            {'number': 1, 'name': 'Bread', 'kind': 'food'},
            {'number': 2, 'name': 'Water', 'kind': 'drink'},
        ]
        ctx = _FakeCtx(responses=['?', ''], player=_FakePlayer(), server=server)
        await _give_ration(ctx)
        self.assertIn('Rations (2):', ctx.sent)
        self.assertTrue(any('Bread' in s for s in ctx.sent))
        self.assertTrue(any('Water' in s for s in ctx.sent))

    async def test_give_object_question_mark_lists_all(self):
        server = _FakeServer()
        server.items = [
            {'number': 1, 'name': 'Ring', 'type': 'treasure'},
            {'number': 2, 'name': 'Compass', 'type': 'compass'},
        ]
        ctx = _FakeCtx(responses=['?', ''], player=_FakePlayer(), server=server)
        await _give_object(ctx, {'treasure', 'compass'}, 'object')
        self.assertIn('Object (2):', ctx.sent)
        self.assertTrue(any('Ring' in s for s in ctx.sent))
        self.assertTrue(any('Compass' in s for s in ctx.sent))


class TestGiveToAllyOrMount(unittest.IsolatedAsyncioTestCase):
    """New in TADA: EditPlayer's inventory menu can now target an owned
    ally (or the mount specifically, respecting saddlebags capacity)
    instead of only ever adding to the admin's own inventory. Ryan's
    request."""

    def _player_with_inventory(self, party=None):
        from inventory import Inventory
        player = _FakePlayer()
        player.inventory = Inventory(capacity=10)
        if party is not None:
            player.party = party
        return player

    async def test_no_allies_skips_recipient_prompt(self):
        from commands.editplayer import _pick_recipient
        ctx = _FakeCtx(player=self._player_with_inventory())
        kind, target = await _pick_recipient(ctx)
        self.assertEqual(kind, 'player')
        self.assertEqual(ctx.sent, [])  # no prompt shown at all

    async def test_blank_response_defaults_to_player(self):
        from commands.editplayer import _pick_recipient
        ally = Ally(name='BATMAN', gender='m', strength=14, to_hit=5)
        player = self._player_with_inventory(party=Party(members=[ally]))
        ctx = _FakeCtx(responses=[''], player=player)
        kind, target = await _pick_recipient(ctx)
        self.assertEqual(kind, 'player')

    async def test_picking_ally_by_number(self):
        from commands.editplayer import _pick_recipient
        ally = Ally(name='BATMAN', gender='m', strength=14, to_hit=5)
        player = self._player_with_inventory(party=Party(members=[ally]))
        ctx = _FakeCtx(responses=['1'], player=player)
        kind, target = await _pick_recipient(ctx)
        self.assertEqual(kind, 'ally')
        self.assertIs(target, ally)

    async def test_picking_zero_means_player(self):
        from commands.editplayer import _pick_recipient
        ally = Ally(name='BATMAN', gender='m', strength=14, to_hit=5)
        player = self._player_with_inventory(party=Party(members=[ally]))
        ctx = _FakeCtx(responses=['0'], player=player)
        kind, target = await _pick_recipient(ctx)
        self.assertEqual(kind, 'player')

    async def test_invalid_selection_defaults_to_player(self):
        from commands.editplayer import _pick_recipient
        ally = Ally(name='BATMAN', gender='m', strength=14, to_hit=5)
        player = self._player_with_inventory(party=Party(members=[ally]))
        ctx = _FakeCtx(responses=['99'], player=player)
        kind, target = await _pick_recipient(ctx)
        self.assertEqual(kind, 'player')
        self.assertIn('Invalid selection', '\n'.join(ctx.sent))

    async def test_give_weapon_to_ally_end_to_end(self):
        ally = Ally(name='BATMAN', gender='m', strength=14, to_hit=5)
        player = self._player_with_inventory(party=Party(members=[ally]))
        server = _FakeServer(weapons=[
            {'number': 1, 'name': 'Sword', 'weapon_class': 'hack_slash_bash', 'stability': 10},
        ])
        # 'sword' picks the weapon; '1' at the recipient prompt picks BATMAN.
        ctx = _FakeCtx(responses=['sword', '1'], player=player, server=server)
        await _give_weapon(ctx)
        self.assertEqual(len(ally.items), 1)
        self.assertEqual(len(player.inventory.entries()), 0)
        self.assertTrue(any('BATMAN' in s for s in ctx.sent))

    async def test_give_object_to_mount_without_saddlebags_refused(self):
        from bar.ally_data import AllyFlags
        mount = Ally(name='TRIGGER', gender='m', strength=20, to_hit=0, flags=[AllyFlags.MOUNT])
        player = self._player_with_inventory(party=Party(members=[mount]))
        server = _FakeServer()
        server.items = [{'number': 1, 'name': 'Ring', 'type': 'treasure'}]
        ctx = _FakeCtx(responses=['ring', '1'], player=player, server=server)
        await _give_object(ctx, {'treasure'}, 'object')
        self.assertEqual(len(mount.items), 0)
        self.assertIn('needs saddlebags', '\n'.join(ctx.sent))

    async def test_give_object_to_mount_with_saddlebags_succeeds(self):
        from bar.ally_data import AllyFlags
        mount = Ally(name='TRIGGER', gender='m', strength=20, to_hit=0,
                     flags=[AllyFlags.MOUNT, AllyFlags.SADDLEBAGS])
        player = self._player_with_inventory(party=Party(members=[mount]))
        server = _FakeServer()
        server.items = [{'number': 1, 'name': 'Ring', 'type': 'treasure'}]
        ctx = _FakeCtx(responses=['ring', '1'], player=player, server=server)
        await _give_object(ctx, {'treasure'}, 'object')
        self.assertEqual(len(mount.items), 1)


class TestInventoryReadNumberedBook(unittest.IsolatedAsyncioTestCase):
    """'r<#>' at the inventory prompt reads inventory slot # (matching
    _show_inventory()'s numbering) by delegating to the real ReadCommand --
    a plain 'r' with no number still means Ration, unaffected."""

    def _player_with_books(self):
        from inventory import Inventory
        from items import Item, ItemCategory
        from item_system import ItemType

        player = _FakePlayer()
        player.stats = {}
        player.inventory = Inventory(capacity=10)
        sword = Item(id_number=1, name='Sword', category=ItemCategory.WEAPON)
        book = Item(id_number=30, name='The Howling', category=ItemCategory.ITEM)
        book.type = ItemType.BOOK
        player.inventory.add(sword)
        player.inventory.add(book)
        return player

    async def test_show_inventory_numbers_entries(self):
        player = self._player_with_books()
        ctx = _FakeCtx(responses=[], player=player)
        from commands.editplayer import _show_inventory
        await _show_inventory(ctx)
        flat = '\n'.join(ctx.sent)
        self.assertIn('1. Sword', flat)
        self.assertIn('2. The Howling', flat)

    async def test_r_number_reads_that_book(self):
        player = self._player_with_books()
        # '2' picks the book from ReadCommand's own book list (only one
        # BOOK-typed entry, so it's listed as choice 1 there).
        ctx = _FakeCtx(responses=['r2', '1', 'q'], player=player)
        await _inventory_action(ctx)(ctx)
        flat = '\n'.join(ctx.sent)
        self.assertIn('Howling', flat)

    async def test_bare_r_still_means_ration(self):
        player = self._player_with_books()
        server = _FakeServer()
        server.rations = []
        ctx = _FakeCtx(responses=['r', 'q'], player=player, server=server)
        await _inventory_action(ctx)(ctx)
        self.assertIn('No ration data loaded on server.', ctx.sent)

    async def test_out_of_range_number_reports_error(self):
        player = self._player_with_books()
        ctx = _FakeCtx(responses=['r99', 'q'], player=player)
        await _inventory_action(ctx)(ctx)
        self.assertIn('No such inventory item.', ctx.sent)

    async def test_admin_granted_book_is_readable(self):
        """A book added via the [B]ook sub-option (_give_object) must carry
        a real ItemType.BOOK, same as a book found in the world via get.py --
        otherwise read.py's _book_entries() never sees it and 'r<#>' (or
        the standalone READ command) wrongly reports 'You have no books!'"""
        from inventory import Inventory

        player = _FakePlayer()
        player.stats = {}
        player.inventory = Inventory(capacity=10)
        server = _FakeServer()
        server.items = [{'number': 30, 'name': 'The Howling', 'type': 'book'}]

        ctx = _FakeCtx(responses=['howling', '1'], player=player, server=server)
        await _give_object(ctx, {'book'}, 'book')

        entries = list(player.inventory.entries())
        self.assertEqual(len(entries), 1)
        from item_system import ItemType
        self.assertEqual(entries[0].item.type, ItemType.BOOK)

        ctx2 = _FakeCtx(responses=['r1', '1', 'q'], player=player)
        await _inventory_action(ctx2)(ctx2)
        self.assertNotIn('You have no books!', ctx2.sent)
        self.assertTrue(any('Howling' in s for s in ctx2.sent))


if __name__ == '__main__':
    unittest.main(verbosity=2)
