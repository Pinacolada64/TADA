"""tests/commands/test_get_statue.py

Covers commands/get.py's port of SPUR.MISC.S's STATUE handling
(get.b: instr("STATUE",i$) / instr("#",wy$)):

  - A petrified player's statue (statues.py's add_statue(), set by
    combat/engine.py's _player_petrified()) shows up in the room's
    "You see: ..." listing and can be targeted by name ('get statue').
  - GETting it always fails with "THE STATUE IS MUCH TOO HEAVY!" --
    never added to inventory, never removed from the room (it's
    permanent, unlike every other GET special case in this file).
  - 'look statue' / 'examine statue' / 'read statue' all show the same
    plaque flavor text naming the petrified victim and the monster
    responsible -- see tests/commands/test_look_examine.py's
    TestExamineStatue for the lower-level _examine_item() unit tests;
    this file covers the full LookCommand/ReadCommand round trip.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from base_classes import PlayerStat
from commands.get import GetCommand, _room_available_items
from commands.look import LookCommand
from commands.read import ReadCommand
from inventory import Inventory
from player import Player
import statues


def _player() -> Player:
    p = Player(name='Rulan')
    p.inventory = Inventory(capacity=10)
    p.picked_up_items = []
    p.stats[PlayerStat.INT] = 10   # comfortably above ReadCommand's _MIN_INTELLIGENCE
    return p


class _FakeCtx:
    def __init__(self, player, server):
        self.player = player
        self.server = server
        self.client = MagicMock()
        self.client.room = 1
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def send_room(self, *args, **kwargs):
        pass

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _server_with_room():
    server = MagicMock()
    server.items      = []
    server.weapons    = []
    server.rations    = []
    server.room_items = {}
    room = MagicMock()
    room.item = 0
    room.weapon = 0
    room.food = 0
    server.game_map.get_room.return_value = room
    return server


class _IsolatedStatuesFileTest(unittest.TestCase):
    """Points statues.ROOM_STATUES_FILE at a throwaway tempdir for the
    duration of each test, so tests never touch the real
    run/server/room_statues.json."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='tada-get-statue-test-')
        self._orig_path = statues.ROOM_STATUES_FILE
        statues.ROOM_STATUES_FILE = Path(self.tmpdir) / 'room_statues.json'

    def tearDown(self):
        import shutil
        statues.ROOM_STATUES_FILE = self._orig_path
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestStatueListedInRoom(_IsolatedStatuesFileTest):

    def test_statue_appears_when_present(self):
        statues.add_statue(1, 1, 'MEDUSA', 'Alice')
        ctx = _FakeCtx(_player(), _server_with_room())
        names = [name for name, _, _ in _room_available_items(ctx)]
        self.assertIn('a statue', names)

    def test_no_statue_when_absent(self):
        ctx = _FakeCtx(_player(), _server_with_room())
        names = [name for name, _, _ in _room_available_items(ctx)]
        self.assertNotIn('a statue', names)


class TestGetStatue(_IsolatedStatuesFileTest, unittest.IsolatedAsyncioTestCase):

    async def test_get_statue_by_name_is_too_heavy(self):
        statues.add_statue(1, 1, 'MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_room())

        await GetCommand().execute(ctx, 'statue')

        self.assertIn('THE STATUE IS MUCH TOO HEAVY!', ctx._flat())

    async def test_statue_never_added_to_inventory(self):
        statues.add_statue(1, 1, 'MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_room())

        await GetCommand().execute(ctx, 'statue')

        self.assertEqual(p.inventory.entries(), [])

    async def test_statue_still_present_after_get_attempt(self):
        """Unlike every other GET special case in this file, a statue is
        never removed -- it's permanent (SPUR's wy$ flag isn't cleared by
        a failed GET)."""
        statues.add_statue(1, 1, 'MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_room())

        await GetCommand().execute(ctx, 'statue')

        names = [name for name, _, _ in _room_available_items(ctx)]
        self.assertIn('a statue', names)


class TestLookStatue(_IsolatedStatuesFileTest, unittest.IsolatedAsyncioTestCase):

    async def test_look_statue_shows_plaque_text(self):
        statues.add_statue(1, 1, 'MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_room())

        await LookCommand().execute(ctx, 'statue')

        self.assertIn(
            'You inspect the statue of Alice. At the base is a small '
            'brass plaque which reads, "Artist: MEDUSA."',
            ctx._flat(),
        )


class TestReadStatue(_IsolatedStatuesFileTest, unittest.IsolatedAsyncioTestCase):
    """READ isn't normally room-aware (it only searches carried books), so
    a statue -- never pickable -- needs its own early check to reach the
    same plaque text 'look statue' shows."""

    async def test_read_statue_shows_plaque_text(self):
        statues.add_statue(1, 1, 'MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_room())

        await ReadCommand().execute(ctx, 'statue')

        self.assertIn(
            'You inspect the statue of Alice. At the base is a small '
            'brass plaque which reads, "Artist: MEDUSA."',
            ctx._flat(),
        )

    async def test_read_statue_absent_falls_through_to_no_books(self):
        p = _player()
        ctx = _FakeCtx(p, _server_with_room())

        await ReadCommand().execute(ctx, 'statue')

        self.assertIn('You have no books!', ctx._flat())

    async def test_read_statue_respects_intelligence_gate(self):
        statues.add_statue(1, 1, 'MEDUSA', 'Alice')
        p = _player()
        p.stats[PlayerStat.INT] = 3
        ctx = _FakeCtx(p, _server_with_room())

        await ReadCommand().execute(ctx, 'statue')

        self.assertIn('Not smart enough to read!', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
