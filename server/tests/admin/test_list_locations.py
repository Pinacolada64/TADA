"""tests/admin/test_list_locations.py — Unit tests for
commands/list_locations.py (admin/DM "list #w/#i/#a/#s/#tel" tool).
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.list_locations import ListLocationsCommand
from flags import PlayerFlags


def _room(name, number=0, item=0, weapon=0):
    r = MagicMock()
    r.name = name
    r.number = number
    r.item = item
    r.weapon = weapon
    return r


def make_ctx(*, admin=False, dm=False, levels=None, items=None, weapons=None,
             prompt_answer=None):
    player = MagicMock()
    player.name = 'Rulan'
    player.map_level = 1
    player.client_settings.screen_columns = 78
    player.client_settings.border_style = 'ascii'

    def _query_flag(flag):
        if flag == PlayerFlags.ADMIN:         return admin
        if flag == PlayerFlags.DUNGEON_MASTER: return dm
        return False
    player.query_flag = MagicMock(side_effect=_query_flag)

    server = MagicMock()
    server.game_map.levels = levels or {}
    server.items   = items or []
    server.weapons = weapons or []

    client = MagicMock()
    client.room = 1

    ctx = MagicMock()
    ctx.player    = player
    ctx.server    = server
    ctx.client    = client
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.prompt    = AsyncMock(return_value=prompt_answer)
    return ctx


def _sent_text(ctx):
    out = []
    for call in ctx.send.await_args_list:
        for a in call.args:
            if isinstance(a, list):
                out.extend(str(x) for x in a)
            else:
                out.append(str(a))
    return '\n'.join(out)


class TestPermission(unittest.IsolatedAsyncioTestCase):
    async def test_non_privileged_denied(self):
        cmd = ListLocationsCommand()
        ctx = make_ctx(admin=False, dm=False)
        res = await cmd.execute(ctx, '#w')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'permission_denied')

    async def test_dm_allowed(self):
        cmd = ListLocationsCommand()
        ctx = make_ctx(dm=True)
        res = await cmd.execute(ctx, '#w')
        self.assertTrue(res.success)


class TestUsage(unittest.IsolatedAsyncioTestCase):
    async def test_no_category_shows_usage(self):
        cmd = ListLocationsCommand()
        ctx = make_ctx(admin=True)
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'missing_args')


class TestWeaponListing(unittest.IsolatedAsyncioTestCase):
    async def test_finds_weapon_by_room_index(self):
        cmd = ListLocationsCommand()
        weapons = [{'number': 1, 'name': 'LONG SWORD'}]
        rooms = {1: _room('Armory', weapon=1), 2: _room('Hallway', weapon=0)}
        ctx = make_ctx(admin=True, levels={1: rooms}, weapons=weapons)
        res = await cmd.execute(ctx, '#weapons')
        self.assertTrue(res.success)
        text = _sent_text(ctx)
        self.assertIn('LONG SWORD', text)
        self.assertIn('Armory', text)
        self.assertNotIn('Hallway', text)

    async def test_short_alias_w(self):
        cmd = ListLocationsCommand()
        weapons = [{'number': 1, 'name': 'BATTLEAXE'}]
        rooms = {1: _room('Armory', weapon=1)}
        ctx = make_ctx(admin=True, levels={1: rooms}, weapons=weapons)
        await cmd.execute(ctx, '#w')
        self.assertIn('BATTLEAXE', _sent_text(ctx))

    async def test_no_matches(self):
        cmd = ListLocationsCommand()
        ctx = make_ctx(admin=True, levels={1: {1: _room('Empty Room')}})
        res = await cmd.execute(ctx, '#w')
        self.assertTrue(res.success)
        self.assertIn('No weapon locations found', _sent_text(ctx))


class TestItemTypeFiltering(unittest.IsolatedAsyncioTestCase):
    def _items(self):
        return [
            {'number': 1, 'name': 'cloth armor', 'type': 'armor'},
            {'number': 2, 'name': 'small shield', 'type': 'shield'},
            {'number': 3, 'name': 'ancient tome', 'type': 'book'},
        ]

    async def test_armor_filter(self):
        cmd = ListLocationsCommand()
        rooms = {
            1: _room('Vault', item=1),
            2: _room('Chapel', item=2),
        }
        ctx = make_ctx(admin=True, levels={1: rooms}, items=self._items())
        await cmd.execute(ctx, '#armor')
        text = _sent_text(ctx)
        self.assertIn('cloth armor', text)
        self.assertNotIn('small shield', text)

    async def test_shield_filter(self):
        cmd = ListLocationsCommand()
        rooms = {1: _room('Vault', item=1), 2: _room('Chapel', item=2)}
        ctx = make_ctx(admin=True, levels={1: rooms}, items=self._items())
        await cmd.execute(ctx, '#s')
        text = _sent_text(ctx)
        self.assertIn('small shield', text)
        self.assertNotIn('cloth armor', text)

    async def test_items_shows_every_type(self):
        cmd = ListLocationsCommand()
        rooms = {1: _room('Vault', item=1), 2: _room('Chapel', item=2), 3: _room('Study', item=3)}
        ctx = make_ctx(admin=True, levels={1: rooms}, items=self._items())
        await cmd.execute(ctx, '#items')
        text = _sent_text(ctx)
        self.assertIn('cloth armor', text)
        self.assertIn('small shield', text)
        self.assertIn('ancient tome', text)

    async def test_arbitrary_type_string(self):
        """Not just w/i/a/s -- any objects.json "type" works directly."""
        cmd = ListLocationsCommand()
        rooms = {1: _room('Study', item=3)}
        ctx = make_ctx(admin=True, levels={1: rooms}, items=self._items())
        await cmd.execute(ctx, '#book')
        self.assertIn('ancient tome', _sent_text(ctx))


class TestMultiLevelScan(unittest.IsolatedAsyncioTestCase):
    async def test_scans_every_level_not_just_current(self):
        cmd = ListLocationsCommand()
        weapons = [{'number': 1, 'name': 'WOOD STAFF'}]
        levels = {
            1: {1: _room('Level 1 Room', weapon=0)},
            3: {5: _room('Level 3 Armory', weapon=1)},
        }
        ctx = make_ctx(admin=True, levels=levels, weapons=weapons)
        ctx.player.map_level = 1  # currently on level 1, match is on level 3
        await cmd.execute(ctx, '#w')
        text = _sent_text(ctx)
        self.assertIn('WOOD STAFF', text)
        self.assertIn('Level 3 Armory', text)  # room name, from the level-3 match
        # The "Level" column cell for this row is "3" -- checked structurally
        # rather than via a "level 3" substring, since the table renderer
        # right-pads/aligns the cell instead of writing prose.
        row_line = next(l for l in text.splitlines() if 'WOOD STAFF' in l)
        cells = [c.strip() for c in row_line.strip('|').split('|')]
        self.assertEqual(cells[2], '3')


class TestTeleportOption(unittest.IsolatedAsyncioTestCase):
    async def test_no_tel_flag_does_not_prompt(self):
        cmd = ListLocationsCommand()
        weapons = [{'number': 1, 'name': 'LONG SWORD'}]
        rooms = {1: _room('Armory', weapon=1)}
        ctx = make_ctx(admin=True, levels={1: rooms}, weapons=weapons)
        await cmd.execute(ctx, '#w')
        ctx.prompt.assert_not_awaited()

    async def test_tel_flag_prompts_and_teleports(self):
        cmd = ListLocationsCommand()
        weapons = [{'number': 1, 'name': 'LONG SWORD'}]
        rooms = {1: _room('Armory', number=1, weapon=1)}
        ctx = make_ctx(admin=True, levels={1: rooms}, weapons=weapons,
                        prompt_answer='1')
        ctx.server.game_map.get_room = lambda level, room_no: rooms.get(room_no)
        ctx.server._show_room = AsyncMock()
        await cmd.execute(ctx, '#w', '#tel')
        ctx.prompt.assert_awaited_once()
        self.assertEqual(ctx.client.room, 1)
        self.assertEqual(ctx.player.map_level, 1)

    async def test_tel_flag_cancel_on_blank(self):
        cmd = ListLocationsCommand()
        weapons = [{'number': 1, 'name': 'LONG SWORD'}]
        rooms = {1: _room('Armory', weapon=1)}
        ctx = make_ctx(admin=True, levels={1: rooms}, weapons=weapons,
                        prompt_answer='')
        original_room = ctx.client.room
        await cmd.execute(ctx, '#w', '#tel')
        self.assertEqual(ctx.client.room, original_room)

    async def test_tel_flag_jumps_to_correct_level(self):
        cmd = ListLocationsCommand()
        weapons = [{'number': 1, 'name': 'WOOD STAFF'}]
        rooms3 = {5: _room('Level 3 Armory', number=5, weapon=1)}
        levels = {1: {1: _room('Level 1 Room')}, 3: rooms3}
        ctx = make_ctx(admin=True, levels=levels, weapons=weapons,
                        prompt_answer='1')
        ctx.player.map_level = 1
        ctx.server.game_map.get_room = lambda level, room_no: levels.get(level, {}).get(room_no)
        ctx.server._show_room = AsyncMock()
        await cmd.execute(ctx, '#w', '#tel')
        self.assertEqual(ctx.player.map_level, 3)
        self.assertEqual(ctx.client.room, 5)


if __name__ == '__main__':
    unittest.main()
