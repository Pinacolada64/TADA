"""tests/commands/test_get_statue.py

Covers commands/get.py's port of SPUR's STATUE handling (SPUR.MISC.S
get.b: instr("STATUE",i$) / instr("#",wy$); SPUR.MAIN.S's `statue`
subroutine, which is what actually decides a statue is present -- reading
just the first line of the relevant monster's own memorial file, shown
wherever that monster is present in a room, alive or dead):

  - A room whose monster has the 'petrify' flag and has petrified at
    least one player before shows up as "a statue" in GET's listing and
    can be targeted by name ('get statue').
  - GETting it always fails with "THE STATUE IS MUCH TOO HEAVY!" --
    never added to inventory, never removed from the room (it's
    permanent, unlike every other GET special case in this file).
  - 'examine statue' / 'read statue' both show the same plaque flavor
    text naming the petrified victim and the monster responsible --
    'look statue' just gives the generic plain description now (the
    flavor text moved from commands/look.py to commands/examine.py,
    Ryan's request) -- see tests/commands/test_examine.py's
    TestExamineStatue for the lower-level _examine_item() unit tests;
    this file covers the full ExamineCommand/ReadCommand round trip.
"""
from __future__ import annotations

import tempfile
import unittest
from unittest.mock import MagicMock

from base_classes import PlayerStat
from combat.engine import _record_statue
from commands.get import GetCommand, _room_available_items
from commands.examine import ExamineCommand
from commands.read import ReadCommand
from inventory import Inventory
from player import Player


_MEDUSA = {'number': 99, 'name': 'MEDUSA', 'flags': {'petrify': True}}


def _player() -> Player:
    p = Player(name='Rulan')
    p.inventory = Inventory(capacity=10)
    p.picked_up_items = []
    p.charmed_monsters = []
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


def _server_with_medusa():
    server = MagicMock()
    server.items      = []
    server.weapons    = []
    server.rations    = []
    server.room_items = {}
    server.monsters   = [_MEDUSA]
    room = MagicMock()
    room.item = 0
    room.weapon = 0
    room.food = 0
    room.monster = _MEDUSA['number']
    server.game_map.get_room.return_value = room
    return server


class _IsolatedMemorialFileTest(unittest.TestCase):
    """Points net_common.run_server_dir at a throwaway tempdir so
    combat.engine._record_statue()/first_statue_victim() never touch the
    real run/server/statues/ directory."""

    def setUp(self):
        import net_common
        self.tmpdir = tempfile.mkdtemp(prefix='tada-get-statue-test-')
        self._orig_run_dir = getattr(net_common, 'run_server_dir', None)
        net_common.run_server_dir = self.tmpdir

    def tearDown(self):
        import net_common, shutil
        net_common.run_server_dir = self._orig_run_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestStatueListedInRoom(_IsolatedMemorialFileTest):

    def test_statue_appears_when_monster_has_a_victim(self):
        _record_statue('MEDUSA', 'Alice')
        ctx = _FakeCtx(_player(), _server_with_medusa())
        names = [name for name, _, _ in _room_available_items(ctx)]
        self.assertIn('a statue', names)

    def test_no_statue_when_monster_has_no_victims_yet(self):
        ctx = _FakeCtx(_player(), _server_with_medusa())
        names = [name for name, _, _ in _room_available_items(ctx)]
        self.assertNotIn('a statue', names)

    def test_no_statue_when_monster_lacks_petrify_flag(self):
        _record_statue('GOBLIN', 'Alice')
        server = _server_with_medusa()
        server.monsters = [{'number': 99, 'name': 'GOBLIN', 'flags': {}}]
        ctx = _FakeCtx(_player(), server)
        names = [name for name, _, _ in _room_available_items(ctx)]
        self.assertNotIn('a statue', names)

    def test_no_statue_when_charmed_away(self):
        _record_statue('MEDUSA', 'Alice')
        player = _player()
        player.charmed_monsters = [_MEDUSA['number']]
        ctx = _FakeCtx(player, _server_with_medusa())
        names = [name for name, _, _ in _room_available_items(ctx)]
        self.assertNotIn('a statue', names)


class TestGetStatue(_IsolatedMemorialFileTest, unittest.IsolatedAsyncioTestCase):

    async def test_get_statue_by_name_is_too_heavy(self):
        _record_statue('MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_medusa())

        await GetCommand().execute(ctx, 'statue')

        self.assertIn('THE STATUE IS MUCH TOO HEAVY!', ctx._flat())

    async def test_statue_never_added_to_inventory(self):
        _record_statue('MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_medusa())

        await GetCommand().execute(ctx, 'statue')

        self.assertEqual(p.inventory.entries(), [])

    async def test_statue_still_present_after_get_attempt(self):
        """Unlike every other GET special case in this file, a statue is
        never removed -- it's permanent."""
        _record_statue('MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_medusa())

        await GetCommand().execute(ctx, 'statue')

        names = [name for name, _, _ in _room_available_items(ctx)]
        self.assertIn('a statue', names)


class TestExamineStatueCommand(_IsolatedMemorialFileTest, unittest.IsolatedAsyncioTestCase):

    async def test_examine_statue_shows_plaque_text(self):
        _record_statue('MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_medusa())

        await ExamineCommand().execute(ctx, 'statue')

        self.assertIn(
            'You inspect the statue of Alice. At the base is a small '
            'brass plaque which reads, "Artist: MEDUSA."',
            ctx._flat(),
        )

    async def test_examine_statue_shows_oldest_victim_only(self):
        _record_statue('MEDUSA', 'Alice')
        _record_statue('MEDUSA', 'Bilbo')
        p = _player()
        ctx = _FakeCtx(p, _server_with_medusa())

        await ExamineCommand().execute(ctx, 'statue')

        self.assertIn('statue of Alice', ctx._flat())
        self.assertNotIn('statue of Bilbo', ctx._flat())


class TestReadStatue(_IsolatedMemorialFileTest, unittest.IsolatedAsyncioTestCase):
    """READ isn't normally room-aware (it only searches carried books), so
    a statue -- never pickable -- needs its own early check to reach the
    same plaque text 'look statue' shows."""

    async def test_read_statue_shows_plaque_text(self):
        _record_statue('MEDUSA', 'Alice')
        p = _player()
        ctx = _FakeCtx(p, _server_with_medusa())

        await ReadCommand().execute(ctx, 'statue')

        self.assertIn(
            'You inspect the statue of Alice. At the base is a small '
            'brass plaque which reads, "Artist: MEDUSA."',
            ctx._flat(),
        )

    async def test_read_statue_absent_falls_through_to_no_books(self):
        p = _player()
        ctx = _FakeCtx(p, _server_with_medusa())

        await ReadCommand().execute(ctx, 'statue')

        self.assertIn('You have no books!', ctx._flat())

    async def test_read_statue_respects_intelligence_gate(self):
        _record_statue('MEDUSA', 'Alice')
        p = _player()
        p.stats[PlayerStat.INT] = 3
        ctx = _FakeCtx(p, _server_with_medusa())

        await ReadCommand().execute(ctx, 'statue')

        self.assertIn('Not smart enough to read!', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
