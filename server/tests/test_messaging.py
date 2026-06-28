"""tests/test_messaging.py

Tests for:
  - commands/messaging.py     (parse_targets, expand_groups, find_online)
  - command_settings.py       (CommandSettings.groups serialization)
  - commands/groups.py        (GroupsCommand)
  - commands/whisper.py       (WhisperCommand)
  - commands/page.py          (PageCommand)

Run with:
    python -m pytest tests/test_messaging.py -v
"""
from __future__ import annotations

import asyncio
import unittest

from command_settings import CommandSettings
from commands.messaging import (
    parse_targets, expand_groups, find_online,
    online_player_names, is_online, player_exists,
)
from commands.groups import GroupsCommand
from commands.whisper import WhisperCommand
from commands.page import PageCommand


# ---------------------------------------------------------------------------
# Fake infrastructure
# ---------------------------------------------------------------------------

class _FakePlayer:
    def __init__(self, name: str):
        self.name            = name
        self.command_settings = CommandSettings()
        self.unsaved_changes  = False


class _FakeClient:
    def __init__(self, room=1):
        self.room = room
        self.ctx  = None   # set after _FakeCtx is created


class _FakeServer:
    def __init__(self):
        self.clients: dict[str, _FakeClient] = {}


class _FakeCtx:
    def __init__(self, name: str, room: int, client: _FakeClient,
                 server: _FakeServer):
        self.player = _FakePlayer(name)
        self.client = client
        self.server = server
        self._sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self._sent.extend(a)
            else:
                self._sent.append(a)

    def sent_text(self) -> str:
        """Joined text of everything sent to this ctx."""
        return '\n'.join(str(s) for s in self._sent)


def _make_server() -> _FakeServer:
    return _FakeServer()


def _add_player(server: _FakeServer, name: str, room: int = 1) -> _FakeCtx:
    """Create a client+ctx for a player and register it with the server."""
    client      = _FakeClient(room=room)
    ctx         = _FakeCtx(name, room, client, server)
    client.ctx  = ctx
    server.clients[name.lower()] = client
    return ctx


def _setup_sender(name: str = 'Rulan', room: int = 1) -> tuple[_FakeCtx, _FakeServer]:
    server = _make_server()
    ctx    = _add_player(server, name, room)
    return ctx, server


# ---------------------------------------------------------------------------
# parse_targets
# ---------------------------------------------------------------------------

class TestParseTargets(unittest.TestCase):

    def test_single_name(self):
        self.assertEqual(parse_targets('Alice'), ['Alice'])

    def test_comma_separated(self):
        self.assertEqual(parse_targets('Alice,Bob'), ['Alice', 'Bob'])

    def test_comma_with_spaces(self):
        self.assertEqual(parse_targets('Alice, Bob'), ['Alice', 'Bob'])

    def test_space_separated(self):
        self.assertEqual(parse_targets('Alice Bob'), ['Alice', 'Bob'])

    def test_quoted_name_with_space(self):
        self.assertEqual(parse_targets('"Dark Lord"'), ['Dark Lord'])

    def test_quoted_and_plain(self):
        self.assertEqual(parse_targets('"Dark Lord",Alice'), ['Dark Lord', 'Alice'])

    def test_group_token(self):
        self.assertEqual(parse_targets('#friends'), ['#friends'])

    def test_group_with_plain(self):
        self.assertEqual(parse_targets('#friends,Alice'), ['#friends', 'Alice'])

    def test_empty_string(self):
        self.assertEqual(parse_targets(''), [])

    def test_only_whitespace(self):
        self.assertEqual(parse_targets('   '), [])

    def test_unmatched_quote_fallback(self):
        # shlex fails on unmatched quotes; falls back to plain split
        result = parse_targets("Alice Bob")
        self.assertIn('Alice', result)
        self.assertIn('Bob', result)


# ---------------------------------------------------------------------------
# expand_groups
# ---------------------------------------------------------------------------

class TestExpandGroups(unittest.TestCase):

    def _player_with_groups(self, groups: dict) -> _FakePlayer:
        p = _FakePlayer('Tester')
        p.command_settings.groups = groups
        return p

    def test_plain_name_passthrough(self):
        p = self._player_with_groups({})
        expanded, unknown = expand_groups(p, ['Alice'])
        self.assertEqual(expanded, ['Alice'])
        self.assertEqual(unknown, [])

    def test_group_expands(self):
        p = self._player_with_groups({'friends': ['Alice', 'Bob']})
        expanded, unknown = expand_groups(p, ['#friends'])
        self.assertEqual(expanded, ['Alice', 'Bob'])
        self.assertEqual(unknown, [])

    def test_unknown_group(self):
        p = self._player_with_groups({})
        expanded, unknown = expand_groups(p, ['#nobody'])
        self.assertEqual(expanded, [])
        self.assertEqual(unknown, ['#nobody'])

    def test_mixed_group_and_plain(self):
        p = self._player_with_groups({'party': ['Alice']})
        expanded, unknown = expand_groups(p, ['#party', 'Bob'])
        self.assertEqual(expanded, ['Alice', 'Bob'])
        self.assertEqual(unknown, [])

    def test_empty_group(self):
        p = self._player_with_groups({'empty': []})
        expanded, unknown = expand_groups(p, ['#empty'])
        self.assertEqual(expanded, [])
        self.assertEqual(unknown, [])

    def test_no_command_settings(self):
        p = _FakePlayer('X')
        p.command_settings = None
        expanded, unknown = expand_groups(p, ['#grp'])
        self.assertEqual(expanded, [])
        self.assertEqual(unknown, ['#grp'])


# ---------------------------------------------------------------------------
# find_online
# ---------------------------------------------------------------------------

class TestFindOnline(unittest.TestCase):

    def test_finds_player(self):
        ctx, server = _setup_sender()
        alice_ctx   = _add_player(server, 'Alice')
        found, not_found = find_online(ctx, ['Alice'])
        self.assertIn(alice_ctx, found)
        self.assertEqual(not_found, [])

    def test_not_found(self):
        ctx, server = _setup_sender()
        found, not_found = find_online(ctx, ['Ghost'])
        self.assertEqual(found, [])
        self.assertEqual(not_found, ['Ghost'])

    def test_excludes_self(self):
        ctx, server = _setup_sender('Rulan')
        found, not_found = find_online(ctx, ['Rulan'])
        self.assertEqual(found, [])
        self.assertIn('Rulan', not_found)

    def test_case_insensitive(self):
        ctx, server = _setup_sender()
        alice_ctx   = _add_player(server, 'Alice')
        found, _    = find_online(ctx, ['alice'])
        self.assertIn(alice_ctx, found)

    def test_deduplicates(self):
        ctx, server = _setup_sender()
        alice_ctx   = _add_player(server, 'Alice')
        found, _    = find_online(ctx, ['Alice', 'Alice'])
        self.assertEqual(found.count(alice_ctx), 1)

    def test_same_room_only_true(self):
        ctx, server  = _setup_sender(room=1)
        _add_player(server, 'Nearby', room=1)
        _add_player(server, 'Faraway', room=2)
        found, _     = find_online(ctx, ['Nearby', 'Faraway'], same_room_only=True)
        names = [f.player.name for f in found]
        self.assertIn('Nearby', names)
        self.assertNotIn('Faraway', names)

    def test_same_room_only_false(self):
        ctx, server = _setup_sender(room=1)
        _add_player(server, 'Faraway', room=2)
        found, _    = find_online(ctx, ['Faraway'], same_room_only=False)
        self.assertEqual(len(found), 1)


# ---------------------------------------------------------------------------
# online_player_names / is_online / player_exists
# ---------------------------------------------------------------------------

class TestOnlineHelpers(unittest.TestCase):

    def test_online_player_names(self):
        server = _make_server()
        _add_player(server, 'Alice')
        _add_player(server, 'Bob')
        names = online_player_names(server)
        self.assertIn('Alice', names)
        self.assertIn('Bob', names)

    def test_online_player_names_empty(self):
        server = _make_server()
        self.assertEqual(online_player_names(server), [])

    def test_is_online_true(self):
        server = _make_server()
        _add_player(server, 'Alice')
        self.assertTrue(is_online(server, 'Alice'))

    def test_is_online_case_insensitive(self):
        server = _make_server()
        _add_player(server, 'Alice')
        self.assertTrue(is_online(server, 'alice'))
        self.assertTrue(is_online(server, 'ALICE'))

    def test_is_online_false(self):
        server = _make_server()
        self.assertFalse(is_online(server, 'Ghost'))

    def test_player_exists_online(self):
        server = _make_server()
        _add_player(server, 'Alice')
        self.assertTrue(player_exists(server, 'Alice'))

    def test_player_exists_not_found(self):
        server = _make_server()
        self.assertFalse(player_exists(server, 'Completely_Unknown_Xyzzy'))


# ---------------------------------------------------------------------------
# CommandSettings — groups field
# ---------------------------------------------------------------------------

class TestCommandSettingsGroups(unittest.TestCase):

    def test_default_empty(self):
        cs = CommandSettings()
        self.assertEqual(cs.groups, {})

    def test_independent_defaults(self):
        # Two instances must not share the same dict
        a = CommandSettings()
        b = CommandSettings()
        a.groups['x'] = []
        self.assertNotIn('x', b.groups)

    def test_to_dict_includes_groups(self):
        cs = CommandSettings(groups={'pals': ['Alice']})
        d  = cs.to_dict()
        self.assertEqual(d['groups'], {'pals': ['Alice']})

    def test_from_dict_restores_groups(self):
        d  = {'whereat_hidden': False, 'groups': {'pals': ['Alice', 'Bob']}}
        cs = CommandSettings.from_dict(d)
        self.assertEqual(cs.groups, {'pals': ['Alice', 'Bob']})

    def test_from_dict_no_groups_key(self):
        cs = CommandSettings.from_dict({'whereat_hidden': True})
        self.assertEqual(cs.groups, {})

    def test_round_trip(self):
        original = CommandSettings(groups={'a': ['X', 'Y'], 'b': []})
        restored = CommandSettings.from_dict(original.to_dict())
        self.assertEqual(restored.groups, original.groups)


# ---------------------------------------------------------------------------
# GroupsCommand
# ---------------------------------------------------------------------------

class TestGroupsCommand(unittest.TestCase):

    def _run(self, ctx, *args):
        return asyncio.run(GroupsCommand().execute(ctx, *args))

    def _ctx(self, name='Rulan'):
        server = _make_server()
        return _add_player(server, name)

    # list
    def test_list_empty(self):
        ctx = self._ctx()
        self._run(ctx)
        self.assertIn('no groups', ctx.sent_text().lower())

    def test_list_shows_groups(self):
        ctx = self._ctx()
        ctx.player.command_settings.groups = {'pals': ['Alice', 'Bob']}
        self._run(ctx)
        self.assertIn('pals', ctx.sent_text())
        self.assertIn('Alice', ctx.sent_text())

    def test_list_single_group(self):
        ctx = self._ctx()
        ctx.player.command_settings.groups = {'pals': ['Alice']}
        self._run(ctx, 'pals')
        self.assertIn('Alice', ctx.sent_text())

    def test_list_unknown_group(self):
        ctx = self._ctx()
        self._run(ctx, 'ghost')
        self.assertIn('No group', ctx.sent_text())

    def test_list_empty_group(self):
        ctx = self._ctx()
        ctx.player.command_settings.groups = {'empty': []}
        self._run(ctx, 'empty')
        self.assertIn('empty', ctx.sent_text().lower())

    def _ctx_with_online(self, *names):
        """Return a sender ctx with named players available online."""
        server = _make_server()
        ctx = _add_player(server, 'Rulan')
        for name in names:
            _add_player(server, name)
        return ctx

    # add
    def test_add_creates_group(self):
        ctx = self._ctx_with_online('Alice')
        self._run(ctx, '#add', 'pals', 'Alice')
        self.assertIn('Alice', ctx.player.command_settings.groups.get('pals', []))
        self.assertTrue(ctx.player.unsaved_changes)

    def test_add_multiple_players(self):
        ctx = self._ctx_with_online('Alice', 'Bob', 'Carol')
        self._run(ctx, '#add', 'pals', 'Alice', 'Bob', 'Carol')
        members = ctx.player.command_settings.groups.get('pals', [])
        self.assertIn('Alice', members)
        self.assertIn('Bob', members)
        self.assertIn('Carol', members)
        self.assertTrue(ctx.player.unsaved_changes)

    def test_add_unknown_player_rejected(self):
        ctx = self._ctx()
        self._run(ctx, '#add', 'pals', 'Xyzzy_Unknown')
        self.assertIn('Unknown player', ctx.sent_text())
        self.assertNotIn('Xyzzy_Unknown',
                         ctx.player.command_settings.groups.get('pals', []))

    def test_add_mixed_known_unknown(self):
        ctx = self._ctx_with_online('Alice')
        self._run(ctx, '#add', 'pals', 'Alice', 'Xyzzy_Unknown')
        members = ctx.player.command_settings.groups.get('pals', [])
        self.assertIn('Alice', members)
        self.assertNotIn('Xyzzy_Unknown', members)
        self.assertIn('Unknown player', ctx.sent_text())
        self.assertIn('Alice', ctx.sent_text())

    def test_add_duplicate_noop(self):
        ctx = self._ctx_with_online('Alice')
        ctx.player.command_settings.groups = {'pals': ['Alice']}
        self._run(ctx, '#add', 'pals', 'Alice')
        self.assertEqual(ctx.player.command_settings.groups['pals'].count('Alice'), 1)
        self.assertIn('nobody new', ctx.sent_text().lower())

    def test_add_partial_duplicates(self):
        ctx = self._ctx_with_online('Alice', 'Bob')
        ctx.player.command_settings.groups = {'pals': ['Alice']}
        self._run(ctx, '#add', 'pals', 'Alice', 'Bob')
        members = ctx.player.command_settings.groups['pals']
        self.assertEqual(members.count('Alice'), 1)
        self.assertIn('Bob', members)
        self.assertIn('Bob', ctx.sent_text())

    def test_add_missing_args(self):
        ctx = self._ctx()
        self._run(ctx, '#add', 'pals')
        self.assertIn('Usage', ctx.sent_text())

    # remove
    def test_remove_player(self):
        ctx = self._ctx()
        ctx.player.command_settings.groups = {'pals': ['Alice', 'Bob']}
        self._run(ctx, '#remove', 'pals', 'Alice')
        self.assertNotIn('Alice', ctx.player.command_settings.groups['pals'])
        self.assertTrue(ctx.player.unsaved_changes)

    def test_remove_not_in_group(self):
        ctx = self._ctx()
        ctx.player.command_settings.groups = {'pals': ['Bob']}
        self._run(ctx, '#remove', 'pals', 'Alice')
        self.assertIn('not in group', ctx.sent_text())

    def test_remove_unknown_group(self):
        ctx = self._ctx()
        self._run(ctx, '#remove', 'ghost', 'Alice')
        self.assertIn('No group', ctx.sent_text())

    def test_remove_missing_args(self):
        ctx = self._ctx()
        self._run(ctx, '#remove', 'pals')
        self.assertIn('Usage', ctx.sent_text())

    # delete
    def test_delete_group(self):
        ctx = self._ctx()
        ctx.player.command_settings.groups = {'pals': ['Alice']}
        self._run(ctx, '#delete', 'pals')
        self.assertNotIn('pals', ctx.player.command_settings.groups)
        self.assertTrue(ctx.player.unsaved_changes)

    def test_delete_unknown_group(self):
        ctx = self._ctx()
        self._run(ctx, '#delete', 'ghost')
        self.assertIn('No group', ctx.sent_text())

    def test_delete_missing_arg(self):
        ctx = self._ctx()
        self._run(ctx, '#delete')
        self.assertIn('Usage', ctx.sent_text())

    # unknown switch
    def test_list_switch(self):
        ctx = self._ctx()
        ctx.player.command_settings.groups = {'pals': ['Alice']}
        self._run(ctx, '#list')
        self.assertIn('pals', ctx.sent_text())

    def test_list_switch_with_name(self):
        ctx = self._ctx()
        ctx.player.command_settings.groups = {'pals': ['Alice', 'Bob']}
        self._run(ctx, '#list', 'pals')
        self.assertIn('Alice', ctx.sent_text())
        self.assertIn('Bob', ctx.sent_text())

    def test_unknown_switch(self):
        ctx = self._ctx()
        self._run(ctx, '#frobnicate')
        self.assertIn('Unknown option', ctx.sent_text())


# ---------------------------------------------------------------------------
# WhisperCommand
# ---------------------------------------------------------------------------

class TestWhisperCommand(unittest.TestCase):

    def _run(self, ctx, *args):
        return asyncio.run(WhisperCommand().execute(ctx, *args))

    def test_no_args(self):
        ctx, _ = _setup_sender()
        result = self._run(ctx)
        self.assertFalse(result.success)
        self.assertIn('whom', ctx.sent_text().lower())

    def test_missing_equals(self):
        ctx, _ = _setup_sender()
        result = self._run(ctx, 'Alice', 'hello')
        self.assertFalse(result.success)
        self.assertIn('Usage', ctx.sent_text())

    def test_empty_message(self):
        ctx, _ = _setup_sender()
        result = self._run(ctx, 'Alice=')
        self.assertFalse(result.success)
        self.assertIn('what', ctx.sent_text().lower())

    def test_empty_target(self):
        ctx, _ = _setup_sender()
        result = self._run(ctx, '=hello')
        self.assertFalse(result.success)

    def test_self_whisper(self):
        ctx, _ = _setup_sender('Rulan')
        result = self._run(ctx, 'Rulan=hello')
        self.assertTrue(result.success)
        self.assertIn('mutter', ctx.sent_text().lower())

    def test_target_not_in_room(self):
        ctx, server = _setup_sender(room=1)
        _add_player(server, 'Alice', room=2)
        result = self._run(ctx, 'Alice=hello')
        self.assertIn('not here', ctx.sent_text())

    def test_target_offline(self):
        ctx, _ = _setup_sender()
        result = self._run(ctx, 'Ghost=hello')
        self.assertIn('not here', ctx.sent_text())

    def test_happy_path_single(self):
        ctx, server    = _setup_sender('Rulan', room=1)
        alice_ctx      = _add_player(server, 'Alice', room=1)
        self._run(ctx, 'Alice=Did you see that?')
        self.assertIn('whisper', ctx.sent_text().lower())
        self.assertIn('Did you see that?', ctx.sent_text())
        self.assertIn('Rulan', alice_ctx.sent_text())
        self.assertIn('Did you see that?', alice_ctx.sent_text())

    def test_happy_path_multi(self):
        ctx, server = _setup_sender('Rulan', room=1)
        alice_ctx   = _add_player(server, 'Alice', room=1)
        bob_ctx     = _add_player(server, 'Bob', room=1)
        self._run(ctx, 'Alice,Bob=Lets go')
        self.assertIn('Alice', ctx.sent_text())
        self.assertIn('Bob', ctx.sent_text())
        self.assertIn('Rulan', alice_ctx.sent_text())
        self.assertIn('Rulan', bob_ctx.sent_text())

    def test_group_expansion(self):
        ctx, server = _setup_sender('Rulan', room=1)
        alice_ctx   = _add_player(server, 'Alice', room=1)
        ctx.player.command_settings.groups = {'pals': ['Alice']}
        self._run(ctx, '#pals=Secret!')
        self.assertIn('Secret!', alice_ctx.sent_text())

    def test_unknown_group_reported(self):
        ctx, _ = _setup_sender()
        self._run(ctx, '#nobody=hello')
        self.assertIn('no group', ctx.sent_text().lower())

    def test_case_insensitive_target(self):
        ctx, server = _setup_sender('Rulan', room=1)
        alice_ctx   = _add_player(server, 'Alice', room=1)
        self._run(ctx, 'alice=hi')
        self.assertIn('Rulan', alice_ctx.sent_text())

    def test_only_faraway_targets(self):
        ctx, server = _setup_sender(room=1)
        _add_player(server, 'Alice', room=2)
        self._run(ctx, 'Alice=hello')
        self.assertIn('not here', ctx.sent_text())

    def test_mixed_room_targets(self):
        ctx, server = _setup_sender('Rulan', room=1)
        alice_ctx   = _add_player(server, 'Alice', room=1)
        _add_player(server, 'Bob', room=2)
        self._run(ctx, 'Alice,Bob=hi')
        # Alice gets the message, Bob is reported not here
        self.assertIn('Rulan', alice_ctx.sent_text())
        self.assertIn('not here', ctx.sent_text())


# ---------------------------------------------------------------------------
# PageCommand
# ---------------------------------------------------------------------------

class TestPageCommand(unittest.TestCase):

    def _run(self, ctx, *args):
        return asyncio.run(PageCommand().execute(ctx, *args))

    def test_no_args(self):
        ctx, _ = _setup_sender()
        result = self._run(ctx)
        self.assertFalse(result.success)
        self.assertIn('whom', ctx.sent_text().lower())

    def test_missing_equals(self):
        ctx, _ = _setup_sender()
        result = self._run(ctx, 'Alice', 'hello')
        self.assertFalse(result.success)
        self.assertIn('Usage', ctx.sent_text())

    def test_empty_message(self):
        ctx, _ = _setup_sender()
        result = self._run(ctx, 'Alice=')
        self.assertFalse(result.success)
        self.assertIn('what', ctx.sent_text().lower())

    def test_empty_target(self):
        ctx, _ = _setup_sender()
        result = self._run(ctx, '=hello')
        self.assertFalse(result.success)

    def test_self_page(self):
        ctx, _ = _setup_sender('Rulan')
        result = self._run(ctx, 'Rulan=hello')
        self.assertTrue(result.success)
        self.assertIn('cannot page yourself', ctx.sent_text().lower())

    def test_target_offline(self):
        ctx, _ = _setup_sender()
        self._run(ctx, 'Ghost=hello')
        self.assertIn('not online', ctx.sent_text())

    def test_happy_path_single(self):
        ctx, server = _setup_sender('Rulan', room=1)
        alice_ctx   = _add_player(server, 'Alice', room=2)  # different room — still works
        self._run(ctx, 'Alice=Are you there?')
        self.assertIn('page', ctx.sent_text().lower())
        self.assertIn('Are you there?', ctx.sent_text())
        self.assertIn('Rulan', alice_ctx.sent_text())
        self.assertIn('Are you there?', alice_ctx.sent_text())

    def test_crosses_rooms(self):
        ctx, server = _setup_sender('Rulan', room=1)
        alice_ctx   = _add_player(server, 'Alice', room=99)
        self._run(ctx, 'Alice=Long distance!')
        self.assertIn('Long distance!', alice_ctx.sent_text())

    def test_happy_path_multi(self):
        ctx, server = _setup_sender('Rulan', room=1)
        alice_ctx   = _add_player(server, 'Alice', room=1)
        bob_ctx     = _add_player(server, 'Bob', room=5)
        self._run(ctx, 'Alice,Bob=Party time')
        self.assertIn('Rulan', alice_ctx.sent_text())
        self.assertIn('Rulan', bob_ctx.sent_text())

    def test_group_expansion(self):
        ctx, server = _setup_sender('Rulan', room=1)
        alice_ctx   = _add_player(server, 'Alice', room=3)
        ctx.player.command_settings.groups = {'pals': ['Alice']}
        self._run(ctx, '#pals=Hello group')
        self.assertIn('Hello group', alice_ctx.sent_text())

    def test_unknown_group_reported(self):
        ctx, _ = _setup_sender()
        self._run(ctx, '#nobody=hello')
        self.assertIn('no group', ctx.sent_text().lower())

    def test_case_insensitive_target(self):
        ctx, server = _setup_sender('Rulan', room=1)
        alice_ctx   = _add_player(server, 'Alice', room=1)
        self._run(ctx, 'alice=hi')
        self.assertIn('Rulan', alice_ctx.sent_text())


if __name__ == '__main__':
    unittest.main()
