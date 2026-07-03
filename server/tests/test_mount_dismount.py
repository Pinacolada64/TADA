"""tests/test_mount_dismount.py

Unit tests for Phase 1 of the MOUNT/DISMOUNT/CHARGE plan (see MECHANICS.md
"Horses"): commands/mount.py, commands/dismount.py, and the auto-dismount
hook wired into commands/movement.py.

Coverage:
  - MOUNT requires a MOUNT-flagged ally; refuses without one
  - MOUNT refuses if already mounted
  - MOUNT refuses in a water room
  - MOUNT succeeds and sets PlayerFlags.MOUNTED
  - DISMOUNT clears the flag; no-ops if not mounted
  - auto-dismount: mount ally gone (dead/removed) -> cleared with a message
  - auto-dismount: moving into a water room -> cleared with a message
  - not mounted -> auto-dismount check is a no-op

Run with:
    python -m pytest tests/test_mount_dismount.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from bar.ally_data import Ally, AllyFlags, AllyStatus
from base_classes import Map, Room
from commands.dismount import DismountCommand
from commands.mount import MountCommand
from commands.movement import _auto_dismount_if_needed
from flags import PlayerFlags
from player import Player


def _make_mount(name='SILVER') -> Ally:
    a = Ally(name=name, gender='m', strength=20, to_hit=0, flags=[AllyFlags.MOUNT])
    a.status = AllyStatus.SERVANT
    return a


def make_player(*, with_mount: bool = True) -> Player:
    p = Player(name='Tester')
    if with_mount:
        p.party.members.append(_make_mount())
    return p


def make_map(room_flags: list | None = None) -> Map:
    m = Map()
    room = Room(number=1, name='Test Room', desc='A room.', flags=room_flags or [])
    m.levels[1] = {1: room}
    m.rooms = m.levels[1]
    return m


def make_ctx(player, *, room_flags: list | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.player = player
    ctx.client.room = 1
    ctx.server.game_map = make_map(room_flags)
    ctx.send = AsyncMock()
    return ctx


def _sent(ctx) -> str:
    parts = []
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


class TestMountCommand(unittest.IsolatedAsyncioTestCase):
    async def test_refuses_without_mount_ally(self):
        player = make_player(with_mount=False)
        ctx = make_ctx(player)
        res = await MountCommand().execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'no_mount')
        self.assertFalse(player.query_flag(PlayerFlags.MOUNTED))

    async def test_mounts_successfully(self):
        player = make_player()
        ctx = make_ctx(player)
        res = await MountCommand().execute(ctx)
        self.assertTrue(res.success)
        self.assertTrue(player.query_flag(PlayerFlags.MOUNTED))
        self.assertIn('climb onto', _sent(ctx).lower())

    async def test_refuses_if_already_mounted(self):
        player = make_player()
        player.set_flag(PlayerFlags.MOUNTED)
        ctx = make_ctx(player)
        res = await MountCommand().execute(ctx)
        self.assertTrue(res.success)
        self.assertIn('already mounted', _sent(ctx).lower())

    async def test_refuses_in_water_room(self):
        player = make_player()
        ctx = make_ctx(player, room_flags=['water'])
        res = await MountCommand().execute(ctx)
        self.assertFalse(res.success)
        self.assertEqual(res.error, 'water_room')
        self.assertFalse(player.query_flag(PlayerFlags.MOUNTED))


class TestDismountCommand(unittest.IsolatedAsyncioTestCase):
    async def test_dismounts_when_mounted(self):
        player = make_player()
        player.set_flag(PlayerFlags.MOUNTED)
        ctx = make_ctx(player)
        res = await DismountCommand().execute(ctx)
        self.assertTrue(res.success)
        self.assertFalse(player.query_flag(PlayerFlags.MOUNTED))

    async def test_noop_when_not_mounted(self):
        player = make_player()
        ctx = make_ctx(player)
        res = await DismountCommand().execute(ctx)
        self.assertTrue(res.success)
        self.assertIn('not mounted', _sent(ctx).lower())


class TestAutoDismount(unittest.IsolatedAsyncioTestCase):
    async def test_noop_when_not_mounted(self):
        player = make_player()
        ctx = make_ctx(player)
        await _auto_dismount_if_needed(ctx)
        self.assertFalse(player.query_flag(PlayerFlags.MOUNTED))
        self.assertEqual(_sent(ctx), '')

    async def test_dismounts_when_mount_ally_gone(self):
        player = make_player()
        player.set_flag(PlayerFlags.MOUNTED)
        player.party.members.clear()  # mount ally removed (freed/died and left party)
        ctx = make_ctx(player)
        await _auto_dismount_if_needed(ctx)
        self.assertFalse(player.query_flag(PlayerFlags.MOUNTED))
        self.assertIn('horse is gone', _sent(ctx).lower())

    async def test_dismounts_when_mount_ally_dead_but_still_in_party(self):
        player = make_player()
        player.party[0].status = AllyStatus.DEAD
        player.set_flag(PlayerFlags.MOUNTED)
        ctx = make_ctx(player)
        await _auto_dismount_if_needed(ctx)
        self.assertFalse(player.query_flag(PlayerFlags.MOUNTED))

    async def test_dismounts_entering_water_room(self):
        player = make_player()
        player.set_flag(PlayerFlags.MOUNTED)
        ctx = make_ctx(player, room_flags=['water_with_rocks'])
        await _auto_dismount_if_needed(ctx)
        self.assertFalse(player.query_flag(PlayerFlags.MOUNTED))
        self.assertIn('balks at the water', _sent(ctx).lower())

    async def test_stays_mounted_on_dry_room_with_healthy_mount(self):
        player = make_player()
        player.set_flag(PlayerFlags.MOUNTED)
        ctx = make_ctx(player)
        await _auto_dismount_if_needed(ctx)
        self.assertTrue(player.query_flag(PlayerFlags.MOUNTED))
        self.assertEqual(_sent(ctx), '')


if __name__ == '__main__':
    unittest.main()
