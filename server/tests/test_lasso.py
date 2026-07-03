"""tests/test_lasso.py

Unit tests for CombatSession.lasso (SPUR.USE.S "lasso" subroutine) and the
LassoCommand wiring, plus the Saddle/Horse Armor equip branch added to
commands/use.py (SPUR.USE.S "eq.horse") and Jake's Stable's Train Horse.

Coverage:
  - non-horse monster -> "You practice with the lasso", not captured
  - horse monster -> captured: new MOUNT ally added to party, strength =
    monster strength + 5, hit_points 0 (SPUR: h1=0, unlike purchased allies)
  - full party (3 allies) blocks capture
  - already having a mount blocks capture
  - horse name validation: length and forbidden characters
  - cancelling the name prompt aborts without creating an ally
  - use.py: Saddle/Horse Armor equip sets the right flag, refuses without a
    mount, refuses a duplicate, consumes the item
  - jakes.py: Train Horse requires mount+saddle+armor, charges gold, sets
    AllyFlags.ELITE, refuses if already trained
  - movement hook: level 5, room 157, moving east -> Jake's Stable; wrong
    level/room/direction -> falls through to normal movement

Run with:
    python -m pytest tests/test_lasso.py -v
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sys, types

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from bar.ally_data import Ally, AllyFlags, AllyStatus
from combat.engine import CombatSession
from commands.lasso import LassoCommand
from commands.use import UseCommand
from commands.movement import MoveCommand
from bar.jakes import _train_horse


def _make_ally(name='BARDA', flags=None) -> Ally:
    a = Ally(name=name, gender='f', strength=10, to_hit=5, flags=flags or [])
    a.status = AllyStatus.SERVANT
    return a


def _make_mount(name='SILVER', flags=None) -> Ally:
    flags = [AllyFlags.MOUNT] + (flags or [])
    a = Ally(name=name, gender='m', strength=20, to_hit=0, flags=flags)
    a.status = AllyStatus.SERVANT
    return a


class _FakePlayer:
    def __init__(self, gold=10_000, allies=None, name='Rulan'):
        self.name = name
        self.party = list(allies or [])
        self.unsaved_changes = False
        self.inventory = MagicMock()
        self.inventory.entries = MagicMock(return_value=[])
        self._gold = gold

    def get_silver(self, kind):
        return self._gold

    def subtract_silver(self, kind, amount) -> bool:
        if self._gold < amount:
            return False
        self._gold -= amount
        return True


class _FakeClient:
    def __init__(self, room=1):
        self.room = room
        self.virtual_location = None


class _FakeServer:
    def __init__(self):
        self.clients = {}
        self.active_combats = {}


class _FakeCtx:
    def __init__(self, player, room=1):
        self.player = player
        self.client = _FakeClient(room=room)
        self.server = _FakeServer()
        self._sent: list[str] = []
        self._answers = iter([])

    def set_answers(self, answers):
        self._answers = iter(answers)

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def prompt(self, *a, **kw):
        return next(self._answers, None)

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@patch('combat.engine.CombatSession._append_capture_log')
class TestLassoCapture(unittest.IsolatedAsyncioTestCase):

    async def test_non_horse_monster_not_captured(self, _mock_log):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)
        captured = await session.lasso(ctx)
        self.assertFalse(captured)
        self.assertIn('practice with the lasso', ctx.sent())
        self.assertEqual(len(player.party), 0)

    async def test_horse_monster_captured(self, _mock_log):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        ctx.set_answers(['STARDUST'])
        session = CombatSession({'name': 'WILD HORSE', 'strength': 15}, room_no=1)
        captured = await session.lasso(ctx)
        self.assertTrue(captured)
        self.assertEqual(len(player.party), 1)
        mount = player.party[0]
        self.assertEqual(mount.name, 'STARDUST')
        self.assertIn(AllyFlags.MOUNT, mount.flags)
        self.assertEqual(mount.strength, 20)   # 15 + 5
        self.assertEqual(mount.hit_points, 0)
        self.assertTrue(session._done.is_set())

    async def test_full_party_blocks_capture(self, _mock_log):
        allies = [_make_ally('A'), _make_ally('B'), _make_ally('C')]
        player = _FakePlayer(allies=allies)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'WILD HORSE', 'strength': 15}, room_no=1)
        captured = await session.lasso(ctx)
        self.assertFalse(captured)
        self.assertIn('Only 3 allies allowed', ctx.sent())
        self.assertEqual(len(player.party), 3)

    async def test_existing_mount_blocks_capture(self, _mock_log):
        player = _FakePlayer(allies=[_make_mount()])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'WILD HORSE', 'strength': 15}, room_no=1)
        captured = await session.lasso(ctx)
        self.assertFalse(captured)
        self.assertIn('Only 1 mount per customer', ctx.sent())
        self.assertEqual(len(player.party), 1)

    async def test_name_too_short_reprompts(self, _mock_log):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        ctx.set_answers(['AB', 'LONGENOUGH'])
        session = CombatSession({'name': 'WILD HORSE', 'strength': 15}, room_no=1)
        captured = await session.lasso(ctx)
        self.assertTrue(captured)
        self.assertEqual(player.party[0].name, 'LONGENOUGH')

    async def test_name_with_forbidden_char_reprompts(self, _mock_log):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        ctx.set_answers(['BAD!NAME', 'GOODNAME'])
        session = CombatSession({'name': 'WILD HORSE', 'strength': 15}, room_no=1)
        captured = await session.lasso(ctx)
        self.assertTrue(captured)
        self.assertEqual(player.party[0].name, 'GOODNAME')

    async def test_cancel_name_prompt_aborts(self, _mock_log):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        ctx.set_answers([''])
        session = CombatSession({'name': 'WILD HORSE', 'strength': 15}, room_no=1)
        captured = await session.lasso(ctx)
        self.assertFalse(captured)
        self.assertEqual(len(player.party), 0)
        self.assertFalse(session._done.is_set())


class TestLassoCommand(unittest.IsolatedAsyncioTestCase):

    async def test_no_combat_fails(self):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        result = await LassoCommand().execute(ctx)
        self.assertFalse(result.success)

    async def test_not_participant_fails(self):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'WILD HORSE', 'strength': 15}, room_no=1)
        ctx.server.active_combats[1] = session
        result = await LassoCommand().execute(ctx)
        self.assertFalse(result.success)

    async def test_participant_captures_horse(self):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        ctx.set_answers(['STARDUST'])
        session = CombatSession({'name': 'WILD HORSE', 'strength': 15}, room_no=1)
        session.attackers.append(ctx)
        ctx.server.active_combats[1] = session
        with patch.object(CombatSession, '_append_capture_log'):
            result = await LassoCommand().execute(ctx)
        self.assertTrue(result.success)
        self.assertEqual(len(player.party), 1)


class TestEquipMount(unittest.IsolatedAsyncioTestCase):

    def _saddle_item(self):
        from items import Item, ItemCategory
        return Item(id_number=162, name='saddle', category=ItemCategory.ITEM)

    def _armor_item(self):
        from items import Item, ItemCategory
        return Item(id_number=163, name='horse armour', category=ItemCategory.ITEM)

    def _entry(self, item):
        e = MagicMock()
        e.item = item
        return e

    async def test_saddle_requires_mount(self):
        player = _FakePlayer(allies=[])
        item = self._saddle_item()
        player.inventory.entries = MagicMock(return_value=[self._entry(item)])
        ctx = _FakeCtx(player)
        ctx.set_answers(['1'])
        await UseCommand().execute(ctx)
        self.assertIn('Need a mount first', ctx.sent())

    async def test_saddle_equips_mount(self):
        mount = _make_mount()
        player = _FakePlayer(allies=[mount])
        item = self._saddle_item()
        player.inventory.entries = MagicMock(return_value=[self._entry(item)])
        ctx = _FakeCtx(player)
        ctx.set_answers(['1'])
        await UseCommand().execute(ctx)
        self.assertIn(AllyFlags.SADDLED, mount.flags)
        self.assertIn('You put the Saddle on the horse', ctx.sent())
        player.inventory.remove.assert_called_once_with(item)

    async def test_horse_armor_equips_mount(self):
        mount = _make_mount()
        player = _FakePlayer(allies=[mount])
        item = self._armor_item()
        player.inventory.entries = MagicMock(return_value=[self._entry(item)])
        ctx = _FakeCtx(player)
        ctx.set_answers(['1'])
        await UseCommand().execute(ctx)
        self.assertIn(AllyFlags.ARMORED, mount.flags)
        self.assertIn('You put the Horse Armor on the horse', ctx.sent())

    async def test_duplicate_equip_refused(self):
        mount = _make_mount(flags=[AllyFlags.SADDLED])
        player = _FakePlayer(allies=[mount])
        item = self._saddle_item()
        player.inventory.entries = MagicMock(return_value=[self._entry(item)])
        ctx = _FakeCtx(player)
        ctx.set_answers(['1'])
        await UseCommand().execute(ctx)
        self.assertIn('Horse already has one', ctx.sent())
        player.inventory.remove.assert_not_called()


class TestTrainHorse(unittest.IsolatedAsyncioTestCase):

    async def test_no_mount_refused(self):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        await _train_horse(ctx)
        self.assertIn("don't have a mount", ctx.sent())

    async def test_no_saddle_refused(self):
        mount = _make_mount(flags=[AllyFlags.ARMORED])
        player = _FakePlayer(allies=[mount])
        ctx = _FakeCtx(player)
        await _train_horse(ctx)
        self.assertIn('must have a saddle first', ctx.sent())

    async def test_no_armor_refused(self):
        mount = _make_mount(flags=[AllyFlags.SADDLED])
        player = _FakePlayer(allies=[mount])
        ctx = _FakeCtx(player)
        await _train_horse(ctx)
        self.assertIn('must have armor first', ctx.sent())

    async def test_already_trained_refused(self):
        mount = _make_mount(flags=[AllyFlags.SADDLED, AllyFlags.ARMORED, AllyFlags.ELITE])
        player = _FakePlayer(allies=[mount], gold=5000)
        ctx = _FakeCtx(player)
        await _train_horse(ctx)
        self.assertIn('already IS trained', ctx.sent())
        self.assertEqual(player._gold, 5000)

    async def test_successful_training_charges_gold_and_sets_elite(self):
        mount = _make_mount(flags=[AllyFlags.SADDLED, AllyFlags.ARMORED])
        player = _FakePlayer(allies=[mount], gold=5000)
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        await _train_horse(ctx)
        self.assertIn(AllyFlags.ELITE, mount.flags)
        self.assertEqual(player._gold, 3000)

    async def test_insufficient_gold_refused(self):
        mount = _make_mount(flags=[AllyFlags.SADDLED, AllyFlags.ARMORED])
        player = _FakePlayer(allies=[mount], gold=100)
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        await _train_horse(ctx)
        self.assertNotIn(AllyFlags.ELITE, mount.flags)
        self.assertIn('not have enough gold', ctx.sent())


def _make_movement_ctx(map_level=1, room=1):
    ctx = MagicMock()
    ctx.player = MagicMock()
    ctx.player.map_level = map_level
    ctx.client = MagicMock()
    ctx.client.room = room
    ctx.server = MagicMock()
    ctx.server.game_map = MagicMock()
    ctx.server.game_map.rooms = {}
    ctx.server._move = AsyncMock()
    ctx.server._show_room = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


class TestJakesStableMovementHook(unittest.IsolatedAsyncioTestCase):

    async def test_level5_room157_east_triggers_stable(self):
        ctx = _make_movement_ctx(map_level=5, room=157)
        with patch('bar.jakes.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'e')
        mock_main.assert_awaited_once_with(ctx)
        ctx.server._move.assert_not_awaited()

    async def test_wrong_level_falls_through(self):
        ctx = _make_movement_ctx(map_level=1, room=157)
        with patch('bar.jakes.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'e')
        mock_main.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'e')

    async def test_wrong_room_falls_through(self):
        ctx = _make_movement_ctx(map_level=5, room=1)
        with patch('bar.jakes.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'e')
        mock_main.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'e')

    async def test_wrong_direction_falls_through(self):
        ctx = _make_movement_ctx(map_level=5, room=157)
        with patch('bar.jakes.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'n')
        mock_main.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
