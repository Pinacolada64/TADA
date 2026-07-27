"""tests/combat/test_birthday_immunity.py

Unit tests for combat/resolution.py's monster_attacks() birthday
immunity (New in TADA, Ryan's request -- not a SPUR mechanic): a player
is immune to monster attacks on their own birthday, checked first,
ahead of even turn-to-stone. Sysop-gated by the same
config.birthday_greeting_enabled toggle that controls the rest of the
birthday event (logon_events/birthday.py). Also covers combat/engine.py's
_narrate_monster_swing() special-casing the birthday_gift result flag
with its own flavor line instead of the generic "misses you".
"""
from __future__ import annotations

import asyncio
import datetime
import unittest
from unittest.mock import AsyncMock, MagicMock

import config as config_module
from combat.engine import CombatSession
from combat.resolution import MonsterAttackResult, monster_attacks


def run(coro):
    return asyncio.run(coro)


class _FakePlayer:
    def __init__(self, birthday=None):
        self.name = 'Rulan'
        self.birthday = birthday


class _FakeConfig:
    """Stands in for config.config -- just the one attribute
    monster_attacks() actually reads. Swapping the whole module-level
    singleton (rather than mutating the real ServerConfig instance,
    which would round-trip through server_config.json on disk) keeps
    this test from touching real server config at all."""
    def __init__(self, birthday_greeting_enabled=True):
        self.birthday_greeting_enabled = birthday_greeting_enabled


class TestBirthdayImmunity(unittest.TestCase):
    def setUp(self):
        # combat/resolution.py does `from config import config` *inside*
        # monster_attacks() -- re-resolved from config's module namespace
        # on every call, so swapping config_module.config here is enough;
        # no need to touch ServerConfig's own singleton/disk file.
        self._orig_config = config_module.config
        self.addCleanup(setattr, config_module, 'config', self._orig_config)
        config_module.config = _FakeConfig(birthday_greeting_enabled=True)

    def _today_birthday_player(self):
        today = datetime.date.today()
        return _FakePlayer(birthday=datetime.datetime(1990, today.month, today.day))

    def test_birthday_player_is_immune(self):
        player = self._today_birthday_player()
        monster = {'name': 'GOBLIN', 'to_hit': 10, 'strength': 10, 'flags': {}}
        for _ in range(20):  # to_hit=10 would otherwise always hit
            result = monster_attacks(monster, player)
            self.assertFalse(result.hit)
            self.assertEqual(result.damage, 0)
            self.assertTrue(result.birthday_gift)

    def test_immunity_bypasses_turn_to_stone(self):
        player = self._today_birthday_player()
        monster = {'name': 'MEDUSA', 'to_hit': 4, 'strength': 10,
                   'flags': {'petrify': True}}
        for _ in range(20):
            result = monster_attacks(monster, player)
            self.assertTrue(result.birthday_gift)
            self.assertFalse(result.turn_to_stone_attempted)
            self.assertFalse(result.turned_to_stone)

    def test_non_birthday_player_is_not_immune(self):
        not_today = datetime.date.today() + datetime.timedelta(days=100)
        player = _FakePlayer(birthday=datetime.datetime(1990, not_today.month, not_today.day))
        monster = {'name': 'GOBLIN', 'to_hit': 10, 'strength': 10, 'flags': {}}
        results = [monster_attacks(monster, player) for _ in range(20)]
        self.assertTrue(any(r.hit for r in results))
        self.assertFalse(any(r.birthday_gift for r in results))

    def test_no_birthday_on_file_is_not_immune(self):
        player = _FakePlayer(birthday=None)
        monster = {'name': 'GOBLIN', 'to_hit': 10, 'strength': 10, 'flags': {}}
        results = [monster_attacks(monster, player) for _ in range(20)]
        self.assertFalse(any(r.birthday_gift for r in results))

    def test_config_toggle_disables_immunity(self):
        config_module.config = _FakeConfig(birthday_greeting_enabled=False)
        player = self._today_birthday_player()
        monster = {'name': 'GOBLIN', 'to_hit': 10, 'strength': 10, 'flags': {}}
        results = [monster_attacks(monster, player) for _ in range(20)]
        self.assertFalse(any(r.birthday_gift for r in results))
        self.assertTrue(any(r.hit for r in results))


class TestBirthdayGiftNarration(unittest.TestCase):
    """combat/engine.py's _narrate_monster_swing() special-cases
    birthday_gift results with their own line instead of the generic
    "misses you", per Ryan's exact requested wording."""

    def _ctx(self, player_name='Rulan'):
        ctx = MagicMock()
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()
        ctx.player = MagicMock()
        ctx.player.name = player_name
        return ctx

    def test_sends_the_little_birdie_line(self):
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)
        ctx = self._ctx()
        result = MonsterAttackResult(hit=False, damage=0, birthday_gift=True)
        run(session._narrate_monster_swing(ctx, result))
        sent = ctx.send.await_args.args[0]
        self.assertIn('little birdie', sent)
        self.assertIn("it's your birthday today", sent)
        self.assertIn('giving you the day off', sent)

    def test_does_not_send_the_generic_miss_line(self):
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)
        ctx = self._ctx()
        result = MonsterAttackResult(hit=False, damage=0, birthday_gift=True)
        run(session._narrate_monster_swing(ctx, result))
        self.assertNotIn('misses you', ctx.send.await_args.args[0])

    def test_broadcasts_to_the_room(self):
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)
        ctx = self._ctx(player_name='Rulan')
        result = MonsterAttackResult(hit=False, damage=0, birthday_gift=True)
        run(session._narrate_monster_swing(ctx, result))
        ctx.send_room.assert_awaited_once()
        args, kwargs = ctx.send_room.await_args
        self.assertIn('Rulan', args[0])
        self.assertTrue(kwargs.get('exclude_self'))

    def test_ordinary_miss_is_unaffected(self):
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)
        ctx = self._ctx()
        result = MonsterAttackResult(hit=False, damage=0, birthday_gift=False)
        run(session._narrate_monster_swing(ctx, result))
        self.assertIn('misses you', ctx.send.await_args.args[0])


if __name__ == '__main__':
    unittest.main()
