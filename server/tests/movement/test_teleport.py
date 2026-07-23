"""tests/test_teleport.py"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from command_settings import CommandSettings
from commands.teleport import TeleportCommand, _lookup_destination, _room_monster
from flags import PlayerFlags


def make_ctx(*, is_admin=True, is_dm=False, room=1, rooms=None):
    if rooms is None:
        rooms = {1: object(), 37: object()}

    player = MagicMock()
    player.name = 'TestPlayer'

    def _query_flag(f):
        if f == PlayerFlags.ADMIN:         return is_admin
        if f == PlayerFlags.DUNGEON_MASTER: return is_dm
        return False
    player.query_flag = MagicMock(side_effect=_query_flag)

    server = MagicMock()
    server.game_map.rooms = rooms
    server.game_map.levels = {1: rooms}
    server.game_map.get_room = lambda level, room_no: rooms.get(room_no)
    server._show_room = AsyncMock()

    client = MagicMock()
    client.room = room

    ctx = MagicMock()
    ctx.player   = player
    ctx.server   = server
    ctx.client   = client
    ctx.send     = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


def make_named_ctx(*, is_admin=True, room=1, rooms=None, destinations=None):
    """Like make_ctx() but with named rooms and a real CommandSettings
    (not a MagicMock) so #learn/#list/named-destination lookups actually
    read and write a real dict instead of an auto-mocked attribute."""
    if rooms is None:
        # MagicMock(name=...) sets the mock's repr, not a .name attribute
        # -- set .name explicitly instead.
        rooms = {1: MagicMock(), 37: MagicMock()}
        rooms[1].name = 'Room One'
        rooms[37].name = 'Room 37'

    player = MagicMock()
    player.name = 'TestPlayer'
    player.map_level = 1
    player.query_flag = MagicMock(return_value=is_admin)
    player.command_settings = CommandSettings()
    if destinations:
        player.command_settings.teleport.destinations.update(destinations)

    server = MagicMock()
    server.game_map.rooms = rooms
    server.game_map.levels = {1: rooms}
    server.game_map.get_room = lambda level, room_no: rooms.get(room_no)
    server._show_room = AsyncMock()

    client = MagicMock()
    client.room = room

    ctx = MagicMock()
    ctx.player    = player
    ctx.server    = server
    ctx.client    = client
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


class TestTeleportLearn(unittest.IsolatedAsyncioTestCase):

    async def test_learn_with_name_saves_destination(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(room=1)
        res = await cmd.execute(ctx, '#learn', 'armory')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.command_settings.teleport.destinations['armory'], (1, 1))

    async def test_learn_bare_word_via_hash_alias_saves_destination(self):
        # '#learn armory' typed via the bare '#' alias loses its leading
        # '#' in command_processor's splitting -- simulate that by passing
        # 'learn' (no '#') as the first arg.
        cmd = TeleportCommand()
        ctx = make_named_ctx(room=1)
        res = await cmd.execute(ctx, 'learn', 'armory')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.command_settings.teleport.destinations['armory'], (1, 1))

    async def test_learn_without_name_falls_back_to_room_name(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(room=1)
        res = await cmd.execute(ctx, '#learn')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.command_settings.teleport.destinations['Room One'], (1, 1))

    async def test_learn_sends_confirmation(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(room=1)
        await cmd.execute(ctx, '#learn', 'armory')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Learned teleport destination "armory"', sent)


class TestTeleportForget(unittest.IsolatedAsyncioTestCase):

    async def test_forget_with_alias_removes_destination(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(destinations={'armory': (1, 37)})
        res = await cmd.execute(ctx, '#forget', 'armory')
        self.assertTrue(res.success)
        self.assertNotIn('armory', ctx.player.command_settings.teleport.destinations)

    async def test_forget_is_case_insensitive(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(destinations={'Armory': (1, 37)})
        res = await cmd.execute(ctx, '#forget', 'armory')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.command_settings.teleport.destinations, {})

    async def test_forget_bare_word_via_hash_alias(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(destinations={'armory': (1, 37)})
        res = await cmd.execute(ctx, 'forget', 'armory')
        self.assertTrue(res.success)
        self.assertNotIn('armory', ctx.player.command_settings.teleport.destinations)

    async def test_forget_unknown_alias_fails(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(destinations={'armory': (1, 37)})
        res = await cmd.execute(ctx, '#forget', 'dungeon')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'no_match')
        self.assertIn('armory', ctx.player.command_settings.teleport.destinations)

    async def test_forget_without_alias_falls_back_to_room_name(self):
        # Mirrors #learn's fallback: no <alias> -> forget the destination
        # saved under the current room's own name.
        cmd = TeleportCommand()
        ctx = make_named_ctx(room=1, destinations={'Room One': (1, 1)})
        res = await cmd.execute(ctx, '#forget')
        self.assertTrue(res.success)
        self.assertNotIn('Room One', ctx.player.command_settings.teleport.destinations)

    async def test_forget_sends_confirmation(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(destinations={'armory': (1, 37)})
        await cmd.execute(ctx, '#forget', 'armory')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Forgot teleport destination "armory"', sent)


class TestTeleportListDestinations(unittest.IsolatedAsyncioTestCase):

    async def test_list_empty_says_none_saved(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx()
        res = await cmd.execute(ctx, '#list')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('No teleport destinations saved', sent)

    async def test_list_shows_saved_destinations(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(destinations={'armory': (1, 37)})
        res = await cmd.execute(ctx, '#list')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('armory', sent)
        self.assertIn('level 1', sent)
        self.assertIn('room 37', sent)

    async def test_show_is_a_synonym_for_list(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(destinations={'armory': (1, 37)})
        res = await cmd.execute(ctx, '#show')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('armory', sent)

    async def test_bare_teleport_still_requires_args(self):
        # Bare 'teleport' with no args is NOT the same as '#list' -- it
        # still fails with the usage message (Ryan wanted an explicit
        # '#list'/'#show' rather than bare teleport auto-listing).
        cmd = TeleportCommand()
        ctx = make_named_ctx()
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'missing_args')


def make_multi_level_named_ctx():
    """Two levels of named rooms, for '#find' tests -- '#find' searches
    every level, unlike the bare-name substring search which is scoped to
    the player's current level only."""
    r1 = MagicMock(); r1.name = 'The Armory'
    r2 = MagicMock(); r2.name = 'Dark Cavern'
    r3 = MagicMock(); r3.name = "The Ocean"  # room 157's real name, per level_5.json

    player = MagicMock()
    player.name = 'TestPlayer'
    player.map_level = 1
    player.query_flag = MagicMock(return_value=True)
    player.command_settings = CommandSettings()

    server = MagicMock()
    server.game_map.levels = {1: {1: r1, 2: r2}, 5: {157: r3}}
    server.game_map.get_room = lambda level, room_no: server.game_map.levels.get(level, {}).get(room_no)
    server._show_room = AsyncMock()

    client = MagicMock()
    client.room = 1

    ctx = MagicMock()
    ctx.player, ctx.server, ctx.client = player, server, client
    ctx.send, ctx.send_room = AsyncMock(), AsyncMock()
    return ctx


class TestTeleportFind(unittest.IsolatedAsyncioTestCase):

    async def test_find_requires_query_text(self):
        cmd = TeleportCommand()
        ctx = make_multi_level_named_ctx()
        res = await cmd.execute(ctx, '#find')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'missing_args')

    async def test_find_no_matches(self):
        cmd = TeleportCommand()
        ctx = make_multi_level_named_ctx()
        res = await cmd.execute(ctx, '#find', 'nonexistentplace')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'no_match')

    async def test_find_searches_across_levels(self):
        # 'armory' is on level 1, but the player's current level doesn't
        # matter for #find -- unlike the bare-name search.
        cmd = TeleportCommand()
        ctx = make_multi_level_named_ctx()
        ctx.player.map_level = 5
        res = await cmd.execute(ctx, '#find', 'armory')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Level 1, room 1: The Armory', sent)

    async def test_find_does_not_teleport(self):
        cmd = TeleportCommand()
        ctx = make_multi_level_named_ctx()
        await cmd.execute(ctx, '#find', 'armory')
        self.assertEqual(ctx.client.room, 1)  # unchanged

    async def test_find_bare_word_via_hash_alias(self):
        cmd = TeleportCommand()
        ctx = make_multi_level_named_ctx()
        res = await cmd.execute(ctx, 'find', 'armory')
        self.assertTrue(res.success)

    @patch('commands.teleport._special_locations',
           return_value={"Jake's Stable": (5, 157)})
    async def test_find_matches_special_location_despite_apostrophe(self, _mock):
        # Room 157's real name is "The Ocean" (see level_5.json) -- Jake's
        # Stable is a hardcoded movement.py interception, not a named
        # room, and the query "jakes" has no apostrophe while the special
        # location's name does -- normalization must bridge that gap.
        cmd = TeleportCommand()
        ctx = make_multi_level_named_ctx()
        res = await cmd.execute(ctx, '#find', 'jakes')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn("Level 5, room 157: Jake's Stable", sent)


class TestTeleportNamedDestination(unittest.IsolatedAsyncioTestCase):

    async def test_lookup_destination_exact_case_insensitive(self):
        ctx = make_named_ctx(destinations={'Armory': (1, 37)})
        self.assertEqual(_lookup_destination(ctx, 'armory'), (1, 37))

    async def test_lookup_destination_no_match_returns_none(self):
        ctx = make_named_ctx(destinations={'Armory': (1, 37)})
        self.assertIsNone(_lookup_destination(ctx, 'dungeon'))

    async def test_teleport_by_saved_name(self):
        cmd = TeleportCommand()
        ctx = make_named_ctx(room=1, destinations={'armory': (1, 37)})
        res = await cmd.execute(ctx, 'armory')
        self.assertTrue(res.success)
        self.assertEqual(ctx.client.room, 37)

    async def test_saved_name_wins_over_substring_search(self):
        # A room named "armory hall" would otherwise substring-match
        # "armory" -- the saved destination must take priority.
        rooms = {1: MagicMock(), 37: MagicMock(), 2: MagicMock()}
        rooms[1].name, rooms[37].name, rooms[2].name = 'Room One', 'Room 37', 'Armory Hall'
        ctx = make_named_ctx(room=1, rooms=rooms, destinations={'armory': (1, 37)})
        cmd = TeleportCommand()
        res = await cmd.execute(ctx, 'armory')
        self.assertTrue(res.success)
        self.assertEqual(ctx.client.room, 37)  # saved dest, not room 2


class TestTeleportPermission(unittest.IsolatedAsyncioTestCase):

    async def test_non_privileged_denied(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False, is_dm=False)
        res = await cmd.execute(ctx, '37')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'permission_denied')

    async def test_non_privileged_no_room_change(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False, is_dm=False, room=1)
        await cmd.execute(ctx, '37')
        self.assertEqual(ctx.client.room, 1)

    async def test_admin_allowed(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=True)
        res = await cmd.execute(ctx, '37')
        self.assertTrue(res.success)

    async def test_admin_room_changed(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=True)
        await cmd.execute(ctx, '37')
        self.assertEqual(ctx.client.room, 37)

    async def test_dm_allowed(self):
        """Ryan's request: teleport should work for Dungeon Masters too,
        not just Administrators."""
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False, is_dm=True)
        res = await cmd.execute(ctx, '37')
        self.assertTrue(res.success)
        self.assertEqual(ctx.client.room, 37)


class TestTeleportArgs(unittest.IsolatedAsyncioTestCase):

    async def test_no_args_fails(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'missing_args')

    async def test_bad_room_number_fails(self):
        # Non-numeric input is treated as a name search, not a malformed
        # room number -- "abc" matches no room name, so this fails as
        # 'no_match', not a separate 'bad_args' code.
        cmd = TeleportCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx, 'abc')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'no_match')

    async def test_nonexistent_room_fails(self):
        cmd = TeleportCommand()
        ctx = make_ctx(rooms={1: object()})
        res = await cmd.execute(ctx, '99')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'bad_room')

    async def test_space_separated_variant(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        res = await cmd.execute(ctx, '#', '37')
        self.assertTrue(res.success)
        self.assertEqual(ctx.client.room, 37)


def make_multilevel_ctx(*, is_admin=True, current_level=1, current_room=1, levels=None):
    """Like make_ctx() but with real per-level rooms, for #<level> <room>
    teleport tests (make_ctx()'s get_room ignores level entirely)."""
    if levels is None:
        levels = {1: {1: object()}, 5: {18: object()}}

    player = MagicMock()
    player.name = 'TestPlayer'
    player.map_level = current_level
    player.query_flag = MagicMock(
        side_effect=lambda f: f == PlayerFlags.ADMIN and is_admin
    )

    server = MagicMock()
    server.game_map.levels = levels
    server.game_map.get_room = lambda level, room_no: levels.get(level, {}).get(room_no)
    server._show_room = AsyncMock()

    client = MagicMock()
    client.room = current_room

    ctx = MagicMock()
    ctx.player    = player
    ctx.server    = server
    ctx.client    = client
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


class TestTeleportWithLevel(unittest.IsolatedAsyncioTestCase):
    """'#<room>' alone stays on the current level; '#<level> <room>'
    (two numeric args) jumps to a specific level -- Ryan's request."""

    async def test_single_arg_stays_on_current_level(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1)
        res = await cmd.execute(ctx, '1')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.map_level, 1)
        self.assertEqual(ctx.client.room, 1)

    async def test_two_args_jumps_to_specified_level(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1)
        res = await cmd.execute(ctx, '5', '18')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.map_level, 5)
        self.assertEqual(ctx.client.room, 18)

    async def test_two_args_also_updates_client_map_level(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1)
        await cmd.execute(ctx, '5', '18')
        self.assertEqual(ctx.client.map_level, 5)

    async def test_two_args_room_not_on_that_level_fails(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1)
        res = await cmd.execute(ctx, '5', '99')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'bad_room')
        # No partial teleport on failure.
        self.assertEqual(ctx.player.map_level, 1)

    async def test_two_args_same_level_as_current_is_a_no_op_level_change(self):
        cmd = TeleportCommand()
        ctx = make_multilevel_ctx(current_level=1, levels={1: {1: object(), 2: object()}})
        res = await cmd.execute(ctx, '1', '2')
        self.assertTrue(res.success)
        self.assertEqual(ctx.player.map_level, 1)
        self.assertEqual(ctx.client.room, 2)


class TestTeleportFlashMessages(unittest.IsolatedAsyncioTestCase):

    async def test_disappear_sent_to_player(self):
        # Second person to the player who teleported -- room occupants get
        # the third-person version via ctx.send_room() instead.
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        sent = [str(c.args) for c in ctx.send.await_args_list]
        self.assertTrue(any('You disappear' in s for s in sent))

    async def test_appear_sent_to_player(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        sent = [str(c.args) for c in ctx.send.await_args_list]
        self.assertTrue(any('You appear' in s for s in sent))

    async def test_disappear_broadcast_to_origin_room(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        room_calls = [str(c.args) for c in ctx.send_room.await_args_list]
        self.assertTrue(any('disappears' in s for s in room_calls))

    async def test_appear_broadcast_to_dest_room(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        room_calls = [str(c.args) for c in ctx.send_room.await_args_list]
        self.assertTrue(any('appears' in s for s in room_calls))

    async def test_flash_messages_to_self_have_no_name(self):
        # The player's own copy is second-person ("You disappear/appear
        # ...") -- their name only shows up in the room broadcast.
        cmd = TeleportCommand()
        ctx = make_ctx()
        ctx.player.name = 'Railbender'
        await cmd.execute(ctx, '37')
        all_sends = [str(c.args) for c in ctx.send.await_args_list]
        self.assertFalse(any('Railbender' in s for s in all_sends))

    async def test_flash_messages_broadcast_include_player_name(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        ctx.player.name = 'Railbender'
        await cmd.execute(ctx, '37')
        room_calls = [str(c.args) for c in ctx.send_room.await_args_list]
        self.assertTrue(any('Railbender' in s for s in room_calls))

    async def test_send_room_excludes_self(self):
        cmd = TeleportCommand()
        ctx = make_ctx()
        await cmd.execute(ctx, '37')
        for c in ctx.send_room.await_args_list:
            self.assertTrue(c.kwargs.get('exclude_self'))

    async def test_no_flash_on_permission_denied(self):
        cmd = TeleportCommand()
        ctx = make_ctx(is_admin=False)
        await cmd.execute(ctx, '37')
        ctx.send_room.assert_not_awaited()


def make_monster_ctx(*, monster_flags=None, monster_number=99,
                      dead_monsters=None, charmed_monsters=None,
                      room_has_monster=True, monster_name='Grendel'):
    """Origin room 1 (with an optional monster on it) -> dest room 37,
    for testing _teleport()'s SPUR.MISC3.S cst.shop monster-reaction logic."""
    origin = MagicMock()
    origin.monster = monster_number if room_has_monster else 0
    dest = object()
    rooms = {1: origin, 37: dest}

    player = MagicMock()
    player.name = 'TestPlayer'
    player.query_flag = MagicMock(return_value=True)  # admin
    player.dead_monsters = dead_monsters or []
    player.charmed_monsters = charmed_monsters or []

    monster = {
        'number': monster_number,
        'name': monster_name,
        'flags': monster_flags or {},
    }

    server = MagicMock()
    server.game_map.rooms = rooms
    server.game_map.levels = {1: rooms}
    server.game_map.get_room = lambda level, room_no: rooms.get(room_no)
    server.monsters = [monster]
    server._show_room = AsyncMock()

    client = MagicMock()
    client.room = 1

    ctx = MagicMock()
    ctx.player    = player
    ctx.server    = server
    ctx.client    = client
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


class TestRoomMonster(unittest.IsolatedAsyncioTestCase):
    """_room_monster() -- the "live monster in this room" lookup that
    gates teleport's SPUR.MISC3.S cst.shop reaction logic."""

    async def test_no_room_number_returns_none(self):
        ctx = make_monster_ctx()
        self.assertIsNone(_room_monster(ctx, 1, None))

    async def test_no_monster_in_room_returns_none(self):
        ctx = make_monster_ctx(room_has_monster=False)
        self.assertIsNone(_room_monster(ctx, 1, 1))

    async def test_live_monster_returned(self):
        ctx = make_monster_ctx(monster_number=99)
        monster = _room_monster(ctx, 1, 1)
        self.assertIsNotNone(monster)
        self.assertEqual(monster['number'], 99)

    async def test_dead_monster_returns_none(self):
        ctx = make_monster_ctx(monster_number=99, dead_monsters=[99])
        self.assertIsNone(_room_monster(ctx, 1, 1))

    async def test_charmed_monster_returns_none(self):
        ctx = make_monster_ctx(monster_number=99, charmed_monsters=[99])
        self.assertIsNone(_room_monster(ctx, 1, 1))


class TestTeleportMonsterReaction(unittest.IsolatedAsyncioTestCase):
    """_teleport()'s SPUR.MISC3.S cst.shop reaction: a live monster left
    behind reacts to the teleport instead of a plain flash of light."""

    async def test_tough_monster_blocks_teleport(self):
        cmd = TeleportCommand()
        ctx = make_monster_ctx(monster_flags={'tough': True}, monster_name='Grendel')
        res = await cmd.execute(ctx, '37')
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'teleport_blocked')
        self.assertEqual(ctx.client.room, 1)  # no partial teleport
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn("Grendel casts a 'Freeze Adventurer' spell!", sent)

    async def test_tough_and_mechanical_does_not_block(self):
        # 'mechanical' overrides 'tough' -- gets the sensors reaction and
        # the teleport still succeeds (SPUR.MISC3.S: the ':' wy$ check
        # short-circuits the '.' FREEZE ADVENTURER branch).
        cmd = TeleportCommand()
        ctx = make_monster_ctx(monster_flags={'tough': True, 'mechanical': True},
                                monster_name='Sentrybot')
        res = await cmd.execute(ctx, '37')
        self.assertTrue(res.success)
        self.assertEqual(ctx.client.room, 37)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Sensors on Sentrybot goes nuts as you dematerialize!', sent)

    async def test_mechanical_monster_sensors_reaction(self):
        cmd = TeleportCommand()
        ctx = make_monster_ctx(monster_flags={'mechanical': True}, monster_name='Sentrybot')
        res = await cmd.execute(ctx, '37')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Sensors on Sentrybot goes nuts as you dematerialize!', sent)

    async def test_ordinary_monster_looks_puzzled(self):
        cmd = TeleportCommand()
        ctx = make_monster_ctx(monster_flags={}, monster_name='Grendel')
        res = await cmd.execute(ctx, '37')
        self.assertTrue(res.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('Grendel looks puzzled as you fade from view.', sent)

    async def test_no_monster_no_reaction_message(self):
        cmd = TeleportCommand()
        ctx = make_monster_ctx(room_has_monster=False)
        await cmd.execute(ctx, '37')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertNotIn('looks puzzled', sent)
        self.assertNotIn('Sensors on', sent)
        self.assertNotIn('Freeze Adventurer', sent)

    async def test_dead_monster_no_reaction(self):
        cmd = TeleportCommand()
        ctx = make_monster_ctx(monster_flags={'tough': True}, monster_number=99,
                                dead_monsters=[99])
        res = await cmd.execute(ctx, '37')
        self.assertTrue(res.success)
        self.assertEqual(ctx.client.room, 37)


if __name__ == '__main__':
    unittest.main()
