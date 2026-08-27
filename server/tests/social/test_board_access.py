"""tests/social/test_board_access.py

Unit tests for board/access.py -- player_can_access() and
is_board_admin(). Phase 3 of the sig-editor plan: these are the pure
functions everything else (pick_board(), post/reply/delete gating)
will be wired through, so they're tested in isolation first.
"""
from __future__ import annotations

import unittest

from base_classes import Guild
from board.access import is_board_admin, player_can_access
from flags import PlayerFlags


class _FakePlayer:
    def __init__(self, name='alexa', guild=Guild.CIVILIAN, admin=False, dm=False):
        self.name = name
        self.guild = guild
        self._admin = admin
        self._dm = dm

    def query_flag(self, flag):
        if flag == PlayerFlags.ADMIN:
            return self._admin
        if flag == PlayerFlags.DUNGEON_MASTER:
            return self._dm
        return False


class TestPlayerCanAccess(unittest.TestCase):
    def test_any_allows_everyone(self):
        player = _FakePlayer()
        self.assertTrue(player_can_access(player, {'access': {'type': 'any'}}))

    def test_missing_access_key_defaults_to_any(self):
        # meta dicts predating Phase 2's access-gate UI, or a board
        # that's simply never had its gate touched.
        self.assertTrue(player_can_access(_FakePlayer(), {}))

    def test_guild_match(self):
        player = _FakePlayer(guild=Guild.FIST)
        meta = {'access': {'type': 'guild', 'value': Guild.FIST.value}}
        self.assertTrue(player_can_access(player, meta))

    def test_guild_mismatch(self):
        player = _FakePlayer(guild=Guild.CIVILIAN)
        meta = {'access': {'type': 'guild', 'value': Guild.FIST.value}}
        self.assertFalse(player_can_access(player, meta))

    def test_guild_unknown_value_fails_closed(self):
        player = _FakePlayer(guild=Guild.FIST)
        meta = {'access': {'type': 'guild', 'value': 'Not A Real Guild'}}
        self.assertFalse(player_can_access(player, meta))

    def test_flag_match(self):
        player = _FakePlayer(dm=True)
        meta = {'access': {'type': 'flag', 'value': 'DUNGEON_MASTER'}}
        self.assertTrue(player_can_access(player, meta))

    def test_flag_mismatch(self):
        player = _FakePlayer(dm=False)
        meta = {'access': {'type': 'flag', 'value': 'DUNGEON_MASTER'}}
        self.assertFalse(player_can_access(player, meta))

    def test_flag_unknown_name_fails_closed(self):
        player = _FakePlayer()
        meta = {'access': {'type': 'flag', 'value': 'NOT_A_REAL_FLAG'}}
        self.assertFalse(player_can_access(player, meta))

    def test_any_of_matches_on_either_branch(self):
        meta = {'access': {'type': 'any_of', 'values': [
            {'type': 'guild', 'value': Guild.SWORD.value},
            {'type': 'flag', 'value': 'DUNGEON_MASTER'},
        ]}}
        self.assertTrue(player_can_access(_FakePlayer(guild=Guild.SWORD), meta))
        self.assertTrue(player_can_access(_FakePlayer(dm=True), meta))
        self.assertFalse(player_can_access(_FakePlayer(guild=Guild.CLAW), meta))

    def test_any_of_empty_values_denies(self):
        meta = {'access': {'type': 'any_of', 'values': []}}
        self.assertFalse(player_can_access(_FakePlayer(), meta))

    def test_unknown_gate_type_fails_closed(self):
        meta = {'access': {'type': 'quest_flag', 'value': 'whatever'}}
        self.assertFalse(player_can_access(_FakePlayer(), meta))

    def test_global_admin_bypasses_every_gate(self):
        player = _FakePlayer(admin=True, guild=Guild.CIVILIAN)
        for access in (
            {'type': 'guild', 'value': Guild.FIST.value},
            {'type': 'flag', 'value': 'DUNGEON_MASTER'},
            {'type': 'any_of', 'values': []},
        ):
            self.assertTrue(player_can_access(player, {'access': access}))

    def test_global_dungeon_master_bypasses_every_gate(self):
        player = _FakePlayer(dm=True, guild=Guild.CIVILIAN)
        meta = {'access': {'type': 'guild', 'value': Guild.FIST.value}}
        self.assertTrue(player_can_access(player, meta))


class TestIsBoardAdmin(unittest.TestCase):
    def test_named_local_admin(self):
        player = _FakePlayer(name='alexa')
        self.assertTrue(is_board_admin(player, {'admins': ['alexa']}))

    def test_not_a_local_admin(self):
        player = _FakePlayer(name='bob')
        self.assertFalse(is_board_admin(player, {'admins': ['alexa']}))

    def test_global_admin_is_always_board_admin(self):
        player = _FakePlayer(name='bob', admin=True)
        self.assertTrue(is_board_admin(player, {'admins': []}))

    def test_missing_admins_key_defaults_to_no_local_admins(self):
        player = _FakePlayer(name='bob')
        self.assertFalse(is_board_admin(player, {}))


if __name__ == '__main__':
    unittest.main()
