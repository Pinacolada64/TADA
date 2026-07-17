"""tests/test_turn_to_stone.py

Unit tests for the turn-to-stone mechanic (SPUR.COMBAT.S "medusa" section)
and the statue mechanism it feeds into -- a single memorial-file-backed
system spanning SPUR.MISC6.S's `statue` subroutine (writes it) and
SPUR.MAIN.S/SPUR.MISC.S/SPUR.MISC3.S's `statue` subroutine (reads just
its first line, wherever the monster is present -- not a separate
per-room object):

  - combat.resolution.monster_attacks(): a petrify monster has a
    20% chance per attack to attempt petrification, 10% chance to succeed
    once attempted; either way this replaces the normal hit/damage roll
    entirely for that round.
  - combat.engine._record_statue(): per-monster memorial file, one victim
    name appended per line, "THE " prefix stripped from the filename.
  - combat.engine.first_statue_victim(): reads just the first line of
    that same file -- SPUR's "There is a statue of {name} here!", shown
    wherever the monster is present (see commands/get.py,
    commands/look.py, commands/read.py, simple_server.py).
  - CombatSession._player_petrified(): death flow on a successful
    petrification -- distinct flavor text from a normal kill, records the
    statue, zeroes hit_points.
  - CombatSession._monster_dies(): a petrify monster's own death
    gets an extra "turns to stone" flavor line.

Run with:
    python -m pytest tests/test_turn_to_stone.py -v
"""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sys, types

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from combat.engine import CombatSession, _record_statue
from combat.resolution import monster_attacks


class _FakeInventory:
    def __init__(self, item_ids=None):
        self._item_ids = set(item_ids or [])

    def find(self, *, item_id=None, **kwargs):
        return ['present'] if item_id in self._item_ids else []


class _FakePlayer:
    def __init__(self, hit_points=30, item_ids=None):
        self.name = 'Rulan'
        self.hit_points = hit_points
        self.unsaved_changes = False
        self.stats = {}
        self.shield = 0
        self.armor = 0
        self.inventory = _FakeInventory(item_ids)


class _FakeClient:
    room = 1


class _FakeServer:
    def __init__(self):
        self.clients = {}
        self.active_combats = {}


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self.client = _FakeClient()
        self.server = _FakeServer()
        self._sent: list[str] = []

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        pass

    def sent(self) -> str:
        return '\n'.join(self._sent)


# ---------------------------------------------------------------------------
# monster_attacks(): turn-to-stone roll
# ---------------------------------------------------------------------------

class TestTurnToStoneRoll(unittest.TestCase):
    def test_no_attempt_without_the_flag(self):
        monster = {'name': 'GOBLIN', 'to_hit': 4, 'strength': 10, 'flags': {}}
        with patch('combat.resolution.random.randint', return_value=1):
            result = monster_attacks(monster, _FakePlayer())
        self.assertFalse(result.turn_to_stone_attempted)

    def test_attempt_and_success(self):
        monster = {'name': 'MEDUSA', 'to_hit': 4, 'strength': 10,
                   'flags': {'petrify': True}}
        with patch('combat.resolution.random.randint', side_effect=[2, 1]):
            result = monster_attacks(monster, _FakePlayer())
        self.assertTrue(result.turn_to_stone_attempted)
        self.assertTrue(result.turned_to_stone)
        self.assertFalse(result.hit)
        self.assertEqual(result.damage, 0)

    def test_attempt_and_fail(self):
        monster = {'name': 'MEDUSA', 'to_hit': 4, 'strength': 10,
                   'flags': {'petrify': True}}
        with patch('combat.resolution.random.randint', side_effect=[2, 5]):
            result = monster_attacks(monster, _FakePlayer())
        self.assertTrue(result.turn_to_stone_attempted)
        self.assertFalse(result.turned_to_stone)

    def test_flagged_monster_can_still_attack_normally(self):
        # roll(1,10) > 2 -> no petrification attempt this round at all
        monster = {'name': 'MEDUSA', 'to_hit': 4, 'strength': 10,
                   'flags': {'petrify': True}}
        with patch('combat.resolution.random.randint', return_value=9):
            result = monster_attacks(monster, _FakePlayer())
        self.assertFalse(result.turn_to_stone_attempted)
        self.assertFalse(result.turned_to_stone)

    def test_stone_blocked_prevents_any_attempt(self):
        # Crystal Pendant has permanently blocked this monster's ability --
        # no attempt roll should even happen, regardless of dice.
        monster = {'name': 'MEDUSA', 'to_hit': 4, 'strength': 10,
                   'flags': {'petrify': True}}
        with patch('combat.resolution.random.randint', return_value=1):
            result = monster_attacks(monster, _FakePlayer(), stone_blocked=True)
        self.assertFalse(result.turn_to_stone_attempted)


# ---------------------------------------------------------------------------
# _record_statue(): memorial file
# ---------------------------------------------------------------------------

class TestRecordStatue(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='tada-statue-test-')
        import net_common
        self._orig = getattr(net_common, 'run_server_dir', None)
        net_common.run_server_dir = self.tmpdir

    def tearDown(self):
        import net_common, shutil
        net_common.run_server_dir = self._orig
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_strips_leading_the(self):
        _record_statue('THE MEDUSA', 'Rulan')
        path = os.path.join(self.tmpdir, 'statues', 'MEDUSA.txt')
        self.assertTrue(os.path.exists(path))
        self.assertEqual(open(path).read().strip(), 'Rulan')

    def test_appends_multiple_victims(self):
        _record_statue('MEDUSA', 'Rulan')
        _record_statue('MEDUSA', 'Bilbo')
        path = os.path.join(self.tmpdir, 'statues', 'MEDUSA.txt')
        self.assertEqual(open(path).read().splitlines(), ['Rulan', 'Bilbo'])

    def test_sanitizes_unsafe_filename_characters(self):
        _record_statue('THE GUARD ==[]', 'Rulan')
        path = os.path.join(self.tmpdir, 'statues', 'GUARD.txt')
        self.assertTrue(os.path.exists(path))

    def test_does_not_raise_on_io_error(self):
        import net_common
        net_common.run_server_dir = '/nonexistent-path-hopefully/subdir'
        try:
            _record_statue('MEDUSA', 'Rulan')  # should log and swallow, not raise
        except Exception as e:
            self.fail(f'_record_statue raised unexpectedly: {e}')


# ---------------------------------------------------------------------------
# CombatSession._player_petrified()
# ---------------------------------------------------------------------------

class TestPlayerPetrified(unittest.IsolatedAsyncioTestCase):
    async def test_petrified_flow(self):
        self.tmpdir = tempfile.mkdtemp(prefix='tada-statue-test-')
        import net_common
        orig = getattr(net_common, 'run_server_dir', None)
        net_common.run_server_dir = self.tmpdir
        try:
            player = _FakePlayer(hit_points=20)
            ctx = _FakeCtx(player)
            session = CombatSession({'name': 'MEDUSA', 'strength': 10}, room_no=1)

            await session._player_petrified(ctx)

            self.assertEqual(player.hit_points, 0)
            self.assertTrue(session._done.is_set())
            self.assertIn('TURNED TO STONE', ctx.sent())
            self.assertIn('Carving your statue', ctx.sent())

            path = os.path.join(self.tmpdir, 'statues', 'MEDUSA.txt')
            self.assertEqual(open(path).read().strip(), 'Rulan')
        finally:
            import shutil
            net_common.run_server_dir = orig
            shutil.rmtree(self.tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# combat.engine.first_statue_victim()
# ---------------------------------------------------------------------------

class TestFirstStatueVictim(unittest.TestCase):
    """SPUR.MAIN.S's `statue` subroutine: reads just the *first* line of a
    monster's own memorial file (the same one _record_statue() writes) --
    not a separate room-object system. Shown wherever that monster is
    present, alive or dead, regardless of which room it's actually in."""

    def setUp(self):
        from combat.engine import first_statue_victim
        self.first_statue_victim = first_statue_victim
        self.tmpdir = tempfile.mkdtemp(prefix='tada-first-victim-test-')
        import net_common
        self._orig = getattr(net_common, 'run_server_dir', None)
        net_common.run_server_dir = self.tmpdir

    def tearDown(self):
        import net_common, shutil
        net_common.run_server_dir = self._orig
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_no_memorial_file_returns_none(self):
        self.assertIsNone(self.first_statue_victim('MEDUSA'))

    def test_returns_first_line_only(self):
        _record_statue('MEDUSA', 'Rulan')
        _record_statue('MEDUSA', 'Bilbo')
        self.assertEqual(self.first_statue_victim('MEDUSA'), 'Rulan')

    def test_strips_leading_the(self):
        _record_statue('MEDUSA', 'Rulan')
        self.assertEqual(self.first_statue_victim('THE MEDUSA'), 'Rulan')

    def test_does_not_raise_on_io_error(self):
        import net_common
        net_common.run_server_dir = '/nonexistent-path-hopefully/subdir'
        try:
            result = self.first_statue_victim('MEDUSA')
        except Exception as e:
            self.fail(f'first_statue_victim raised unexpectedly: {e}')
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# CombatSession._check_crystal_pendant()
# ---------------------------------------------------------------------------

class TestCrystalPendant(unittest.IsolatedAsyncioTestCase):
    async def test_no_check_without_the_monster_flag(self):
        player = _FakePlayer(item_ids=[82])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'flags': {}}, room_no=1)
        await session._check_crystal_pendant(ctx)
        self.assertFalse(session._turn_to_stone_blocked)
        self.assertEqual(ctx.sent(), '')

    async def test_no_check_without_the_pendant(self):
        player = _FakePlayer(item_ids=[])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'MEDUSA', 'flags': {'petrify': True}}, room_no=1)
        with patch('combat.engine.random.randint', return_value=1):
            await session._check_crystal_pendant(ctx)
        self.assertFalse(session._turn_to_stone_blocked)
        self.assertEqual(ctx.sent(), '')

    async def test_pendant_blocks_on_success_roll(self):
        player = _FakePlayer(item_ids=[82])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'MEDUSA', 'flags': {'petrify': True}}, room_no=1)
        with patch('combat.engine.random.randint', return_value=1):  # != 5 -> blocks
            await session._check_crystal_pendant(ctx)
        self.assertTrue(session._turn_to_stone_blocked)
        self.assertIn('CRYSTAL PENDANT flashes', ctx.sent())

    async def test_monster_counters_on_five_roll(self):
        player = _FakePlayer(item_ids=[82])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'MEDUSA', 'flags': {'petrify': True}}, room_no=1)
        with patch('combat.engine.random.randint', return_value=5):  # countered
            await session._check_crystal_pendant(ctx)
        self.assertFalse(session._turn_to_stone_blocked)
        self.assertIn('ANTI-CRYSTAL PENDANT', ctx.sent())

    async def test_blocked_state_feeds_into_monster_attacks(self):
        # End-to-end: pendant blocks once, then no petrification attempt for
        # the rest of the encounter regardless of dice.
        player = _FakePlayer(item_ids=[82])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'MEDUSA', 'to_hit': 4, 'strength': 10,
                                 'flags': {'petrify': True}}, room_no=1)
        with patch('combat.engine.random.randint', return_value=1):
            await session._check_crystal_pendant(ctx)
        self.assertTrue(session._turn_to_stone_blocked)

        with patch('combat.resolution.random.randint', return_value=1):
            result = monster_attacks(session.monster, player,
                                     stone_blocked=session._turn_to_stone_blocked)
        self.assertFalse(result.turn_to_stone_attempted)


# ---------------------------------------------------------------------------
# CombatSession._monster_dies(): statue flavor for petrify monsters
# ---------------------------------------------------------------------------

class TestMonsterTurnsToStoneOnDeath(unittest.IsolatedAsyncioTestCase):
    async def test_flavor_line_for_petrify_monster(self):
        player = _FakePlayer()
        ctx = _FakeCtx(player)
        session = CombatSession(
            {'name': 'MEDUSA', 'strength': 0, 'flags': {'petrify': True}},
            room_no=1,
        )
        with patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch('combat.engine._record_kill'), \
             patch('combat.engine._give_silver'), \
             patch('combat.rewards.gold_from_monster', return_value=0):
            await session._monster_dies(ctx)
        self.assertIn('turns to stone', ctx.sent().lower())

    async def test_no_flavor_line_for_ordinary_monster(self):
        player = _FakePlayer()
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 0, 'flags': {}}, room_no=1)
        with patch.object(session, '_recover_ammo', new=AsyncMock()), \
             patch('combat.engine._record_kill'), \
             patch('combat.engine._give_silver'), \
             patch('combat.rewards.gold_from_monster', return_value=0):
            await session._monster_dies(ctx)
        self.assertNotIn('turns to stone', ctx.sent().lower())


if __name__ == '__main__':
    unittest.main()
