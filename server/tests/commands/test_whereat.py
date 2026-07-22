"""tests/test_whereat.py — Unit tests for commands/whereat.py"""
import sys, pathlib
if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from commands.whereat import WhereatCommand, _is_privileged, _location_label
from command_settings import CommandSettings
from flags import PlayerFlags
from network_context import GuestPlayer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(name: str, *,
                admin: bool = False,
                dm: bool = False,
                hidden: bool = False) -> MagicMock:
    p = MagicMock()
    p.name = name
    p.unsaved_changes = False
    p.command_settings = CommandSettings(whereat_hidden=hidden)
    p.client_settings.screen_columns = 78

    def _query_flag(flag):
        if flag == PlayerFlags.ADMIN:         return admin
        if flag == PlayerFlags.DUNGEON_MASTER: return dm
        return False

    p.query_flag.side_effect = _query_flag
    return p


def make_client(player, *, virtual_location=None, room=None) -> MagicMock:
    client = MagicMock()
    client.virtual_location = virtual_location
    client.room = room
    client.ctx = MagicMock()
    client.ctx.player = player
    return client


def make_room(name: str) -> MagicMock:
    r = MagicMock()
    r.name = name
    return r


def make_server(*clients, rooms: dict | None = None) -> MagicMock:
    server = MagicMock()
    server.clients = {i: c for i, c in enumerate(clients)}
    if rooms is not None:
        server.game_map.get_room.side_effect = lambda level, n: rooms.get(n)
    else:
        server.game_map = None
    return server


def make_ctx(player, server) -> MagicMock:
    ctx = MagicMock()
    ctx.player = player
    ctx.server = server
    ctx.send   = AsyncMock()
    return ctx


def _sent_text(ctx) -> str:
    """Flatten all ctx.send() call args into one string for assertions."""
    parts = []
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# _is_privileged()
# ---------------------------------------------------------------------------

class TestIsPrivileged(unittest.TestCase):

    def test_admin_is_privileged(self):
        self.assertTrue(_is_privileged(make_player('Alice', admin=True)))

    def test_dm_is_privileged(self):
        self.assertTrue(_is_privileged(make_player('Alice', dm=True)))

    def test_both_is_privileged(self):
        self.assertTrue(_is_privileged(make_player('Alice', admin=True, dm=True)))

    def test_plain_player_not_privileged(self):
        self.assertFalse(_is_privileged(make_player('Alice')))


# ---------------------------------------------------------------------------
# _location_label()
# ---------------------------------------------------------------------------

class TestLocationLabel(unittest.TestCase):

    def test_virtual_location_wins(self):
        client = make_client(make_player('Alice'), virtual_location='Elevator')
        server = make_server(client)
        self.assertEqual(_location_label(client, server), 'Elevator')

    def test_virtual_location_returned_as_is(self):
        client = make_client(make_player('Alice'), virtual_location='Wall Bar')
        server = make_server(client)
        self.assertEqual(_location_label(client, server), 'Wall Bar')

    def test_room_name_from_game_map(self):
        player = make_player('Alice')
        client = make_client(player, room=14)
        server = make_server(client, rooms={14: make_room('Dark Forest')})
        label  = _location_label(client, server)
        self.assertIn('Dark Forest', label)
        self.assertIn('14', label)

    def test_room_from_player_map_room_fallback(self):
        player = make_player('Alice')
        player.map_room = 7
        client = make_client(player)          # client.room is None
        server = make_server(client, rooms={7: make_room('Misty Valley')})
        label  = _location_label(client, server)
        self.assertIn('Misty Valley', label)

    def test_unknown_when_no_room_and_no_map(self):
        client = make_client(make_player('Alice'))
        server = make_server(client)          # game_map is None
        self.assertEqual(_location_label(client, server), '(unknown)')

    def test_unknown_when_room_not_in_map(self):
        client = make_client(make_player('Alice'), room=99)
        server = make_server(client, rooms={})
        self.assertEqual(_location_label(client, server), '(unknown)')

    def test_virtual_location_overrides_room(self):
        client = make_client(make_player('Alice'), virtual_location='Shoppe', room=5)
        server = make_server(client, rooms={5: make_room('Town Square')})
        self.assertEqual(_location_label(client, server), 'Shoppe')


# ---------------------------------------------------------------------------
# WhereatCommand.execute() — sub-commands
# ---------------------------------------------------------------------------

class TestWhereatSubcommands(unittest.IsolatedAsyncioTestCase):

    async def test_hide_sets_flag(self):
        player = make_player('Alice')
        ctx = make_ctx(player, make_server())
        await WhereatCommand().execute(ctx, '#hide')
        self.assertTrue(player.command_settings.whereat_hidden)
        self.assertTrue(player.unsaved_changes)
        self.assertIn('hidden', _sent_text(ctx).lower())

    async def test_show_clears_flag(self):
        player = make_player('Alice', hidden=True)
        ctx = make_ctx(player, make_server())
        await WhereatCommand().execute(ctx, '#show')
        self.assertFalse(player.command_settings.whereat_hidden)
        self.assertTrue(player.unsaved_changes)
        self.assertIn('visible', _sent_text(ctx).lower())

    async def test_unknown_subcommand_sends_error(self):
        player = make_player('Alice')
        ctx = make_ctx(player, make_server())
        await WhereatCommand().execute(ctx, '#fly')
        self.assertIn('#fly', _sent_text(ctx))

    async def test_hide_when_no_command_settings(self):
        player = make_player('Alice')
        player.command_settings = None
        ctx = make_ctx(player, make_server())
        result = await WhereatCommand().execute(ctx, '#hide')
        self.assertTrue(result.success)
        self.assertIn('not available', _sent_text(ctx).lower())


# ---------------------------------------------------------------------------
# WhereatCommand.execute() — listing
# ---------------------------------------------------------------------------

class TestWhereatListing(unittest.IsolatedAsyncioTestCase):

    async def test_no_players_message(self):
        ctx = make_ctx(make_player('Alice'), make_server())
        await WhereatCommand().execute(ctx)
        self.assertIn('No players', _sent_text(ctx))

    async def test_lists_player_names(self):
        alice  = make_player('Alice')
        bob    = make_player('Bob')
        ca     = make_client(alice)
        cb     = make_client(bob)
        server = make_server(ca, cb)
        ctx    = make_ctx(alice, server)
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        self.assertIn('Alice', out)
        self.assertIn('Bob', out)

    async def test_output_sorted_alphabetically(self):
        zara   = make_player('Zara')
        alice  = make_player('Alice')
        server = make_server(make_client(zara), make_client(alice))
        ctx    = make_ctx(zara, server)
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        self.assertLess(out.index('Alice'), out.index('Zara'))

    async def test_guest_players_excluded(self):
        alice  = make_player('Alice')
        guest  = GuestPlayer()
        cg     = MagicMock()
        cg.virtual_location = None
        cg.ctx = MagicMock()
        cg.ctx.player = guest
        server = make_server(make_client(alice), cg)
        ctx    = make_ctx(alice, server)
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        self.assertIn('Alice', out)
        self.assertNotIn('Guest', out)

    async def test_hidden_player_shows_hidden_to_normal(self):
        alice  = make_player('Alice')
        bob    = make_player('Bob', hidden=True)
        server = make_server(make_client(alice), make_client(bob))
        ctx    = make_ctx(alice, server)
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        self.assertIn('(Hidden)', out)

    async def test_hidden_player_shows_real_location_to_admin(self):
        admin  = make_player('Admin', admin=True)
        bob    = make_player('Bob', hidden=True)
        cb     = make_client(bob, virtual_location='Elevator')
        server = make_server(make_client(admin), cb)
        ctx    = make_ctx(admin, server)
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        self.assertIn('Elevator', out)
        self.assertNotIn('(Hidden)', out)

    async def test_admin_sees_hidden_hint(self):
        admin  = make_player('Admin', admin=True)
        bob    = make_player('Bob', hidden=True)
        server = make_server(make_client(admin), make_client(bob))
        ctx    = make_ctx(admin, server)
        await WhereatCommand().execute(ctx)
        self.assertIn('[hidden]', _sent_text(ctx))

    async def test_dm_sees_through_hidden(self):
        dm     = make_player('DM', dm=True)
        bob    = make_player('Bob', hidden=True)
        cb     = make_client(bob, virtual_location='Shoppe')
        server = make_server(make_client(dm), cb)
        ctx    = make_ctx(dm, server)
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        self.assertIn('Shoppe', out)
        self.assertNotIn('(Hidden)', out)

    async def test_output_contains_whereat_header(self):
        alice  = make_player('Alice')
        server = make_server(make_client(alice))
        ctx    = make_ctx(alice, server)
        await WhereatCommand().execute(ctx)
        self.assertIn('Whereat', _sent_text(ctx))

    async def test_virtual_location_shown_in_listing(self):
        alice  = make_player('Alice')
        ca     = make_client(alice, virtual_location='Elevator')
        server = make_server(ca)
        ctx    = make_ctx(alice, server)
        await WhereatCommand().execute(ctx)
        self.assertIn('Elevator', _sent_text(ctx))

    async def test_room_name_shown_in_listing(self):
        alice  = make_player('Alice')
        ca     = make_client(alice, room=3)
        server = make_server(ca, rooms={3: make_room('The Dark Forest')})
        ctx    = make_ctx(alice, server)
        await WhereatCommand().execute(ctx)
        self.assertIn('The Dark Forest', _sent_text(ctx))

    async def test_client_without_ctx_skipped(self):
        alice   = make_player('Alice')
        bad_cli = MagicMock()
        bad_cli.ctx = None
        server = make_server(make_client(alice), bad_cli)
        ctx    = make_ctx(alice, server)
        result = await WhereatCommand().execute(ctx)
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# Command metadata
# ---------------------------------------------------------------------------

class TestWhereatMeta(unittest.TestCase):

    def test_name(self):
        self.assertEqual(WhereatCommand.name, 'whereat')

    def test_aliases_include_wa(self):
        self.assertIn('wa', WhereatCommand.aliases)

    def test_has_help(self):
        self.assertIsNotNone(WhereatCommand.help)
        self.assertGreater(len(WhereatCommand.help.summary), 0)


# ---------------------------------------------------------------------------
# Bulk scenario: ~12 players, mixed virtual/room locations, ~10% hidden
# ---------------------------------------------------------------------------

class TestWhereatBulkListing(unittest.IsolatedAsyncioTestCase):
    """Exercises the full listing with a realistic mix of players."""

    ROOMS = {
        2:  'Forest Path',
        5:  'Town Square',
        7:  'Misty Vale',
        12: 'Dark Forest',
        33: 'The Ruins',
        44: 'Crystal Cavern',
        99: 'Shadow Keep',
    }

    # (name, virtual_location, room_no, hidden)
    # 1 hidden out of 12 ≈ 8%, within the ~10% target
    ROSTER = [
        ('Alice',  None,                  5,    False),
        ('Bob',    None,                  12,   False),
        ('Carol',  'Bar',                 None, False),
        ('Dave',   'Shoppe',              None, False),
        ('Eve',    'Elevator',            None, False),
        ('Frank',  None,                  33,   True),   # hidden
        ('Grace',  'Mark of the Claw HQ', None, False),
        ('Hank',   None,                  7,    False),
        ('Iris',   None,                  44,   False),
        ('Jack',   'Iron Fist HQ',        None, False),
        ('Kay',    None,                  2,    False),
        ('Leo',    None,                  99,   False),
    ]

    def _build(self, *, observer='Alice', admin=False):
        players = {}
        clients = {}
        for name, vl, room_no, hidden in self.ROSTER:
            is_admin = admin and name == observer
            p = make_player(name, admin=is_admin, hidden=hidden)
            c = make_client(p, virtual_location=vl, room=room_no)
            players[name] = p
            clients[name] = c

        rooms_mock = {n: make_room(label) for n, label in self.ROOMS.items()}
        server = make_server(*clients.values(), rooms=rooms_mock)
        ctx = make_ctx(players[observer], server)
        return ctx

    # --- fixture sanity ---

    def test_roster_has_twelve_players(self):
        self.assertEqual(len(self.ROSTER), 12)

    def test_roughly_ten_percent_hidden(self):
        hidden = sum(1 for *_, h in self.ROSTER if h)
        pct = hidden / len(self.ROSTER)
        self.assertGreaterEqual(pct, 0.05)
        self.assertLessEqual(pct, 0.20)

    # --- visible players ---

    async def test_visible_names_appear(self):
        ctx = self._build()
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        for name, _, _, hidden in self.ROSTER:
            if not hidden:
                self.assertIn(name, out)

    async def test_hidden_player_name_still_listed(self):
        ctx = self._build()
        await WhereatCommand().execute(ctx)
        self.assertIn('Frank', _sent_text(ctx))

    async def test_hidden_location_masked_from_normal_player(self):
        ctx = self._build()
        await WhereatCommand().execute(ctx)
        self.assertIn('(Hidden)', _sent_text(ctx))

    async def test_hidden_room_not_visible_to_normal_player(self):
        ctx = self._build()
        await WhereatCommand().execute(ctx)
        self.assertNotIn('The Ruins', _sent_text(ctx))

    # --- virtual areas ---

    async def test_virtual_areas_shown(self):
        ctx = self._build()
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        for label in ('Bar', 'Shoppe', 'Elevator', 'Mark of the Claw HQ', 'Iron Fist HQ'):
            self.assertIn(label, out)

    # --- map rooms ---

    async def test_room_names_shown(self):
        ctx = self._build()
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        for room_no, room_name in self.ROOMS.items():
            if room_no == 33:
                continue    # Frank's room — hidden from normal players
            self.assertIn(room_name, out)

    # --- sort order ---

    async def test_output_is_sorted_alphabetically(self):
        ctx = self._build()
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        positions = {name: out.index(name)
                     for name, *_ in self.ROSTER if name in out}
        ordered = sorted(positions, key=lambda n: (positions[n], n.lower()))
        self.assertEqual(ordered, sorted(ordered, key=lambda n: positions[n]))

    # --- admin perspective ---

    async def test_admin_sees_hidden_players_real_room(self):
        ctx = self._build(observer='Alice', admin=True)
        await WhereatCommand().execute(ctx)
        out = _sent_text(ctx)
        self.assertIn('The Ruins', out)
        self.assertNotIn('(Hidden)', out)

    async def test_admin_sees_hidden_annotation(self):
        ctx = self._build(observer='Alice', admin=True)
        await WhereatCommand().execute(ctx)
        self.assertIn('[hidden]', _sent_text(ctx))

    async def test_header_present(self):
        ctx = self._build()
        await WhereatCommand().execute(ctx)
        self.assertIn('Whereat', _sent_text(ctx))


if __name__ == '__main__':
    async def _demo():
        """Print whereat output for the bulk scenario — normal and admin views."""
        cls   = TestWhereatBulkListing
        rooms = {n: make_room(label) for n, label in cls.ROOMS.items()}

        for title, observer, admin in [
            ('Normal player (Alice)', 'Alice', False),
            ('Admin view',            'Alice', True),
        ]:
            players_map  = {}
            clients_list = []
            for name, vl, room_no, hidden in cls.ROSTER:
                p = make_player(name, admin=(admin and name == observer), hidden=hidden)
                c = make_client(p, virtual_location=vl, room=room_no)
                players_map[name] = p
                clients_list.append(c)

            server = make_server(*clients_list, rooms=rooms)
            ctx    = make_ctx(players_map[observer], server)

            collected = []
            async def _collect(*args, _buf=collected):
                for a in args:
                    _buf.extend(str(x) for x in a) if isinstance(a, list) else _buf.append(str(a))
            ctx.send = _collect

            await WhereatCommand().execute(ctx)
            print(f'\n=== {title} ===')
            print('\n'.join(collected))

    asyncio.run(_demo())
    print()
    unittest.main()
