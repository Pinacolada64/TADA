"""tests/test_allies_guild.py

Unit tests for street/allies_guild.py (the Allies' Guild, ported from the skip
branch's SPUR.MISC8.S s.guild/s.disc/s.armor/s.wep/s.track/s.bod), plus its
hardcoded level/room/direction interception in commands/movement.py (mirrors
SPUR.MAIN.S: "if cl=4 if cr=42 if di=3 ...").

Coverage:
  - no owned allies -> greets and exits immediately
  - each training type applies its flag and charges the right cost
  - already-trained is free (no prompt/charge)
  - MOUNT allies are refused armor and tracking training
  - body building increments level, adds strength, costs scale by level
  - body building caps at level 8
  - insufficient gold blocks training (no flag applied)
  - declining the confirmation prompt blocks training (no flag applied)
  - movement hook: level 4, room 42, moving east -> triggers the guild;
    wrong level/room/direction -> falls through to normal movement

Run with:
    python -m pytest tests/test_allies_guild.py -v
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sys, types

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from bar.ally_data import Ally, AllyFlags, AllyStatus
from street.allies_guild import (
    main as guild_main,
    _train_armor, _train_discipline, _train_combat, _train_tracking, _train_body,
    _MAX_BODY_BUILD_LEVEL, _BODY_BUILD_STR_BONUS, _BODY_BUILD_BASE_COST,
    _COST_DISCIPLINE, _COST_ARMOR, _COST_COMBAT, _COST_TRACKING,
)
from commands.movement import MoveCommand


def _make_ally(name='BARDA', flags=None) -> Ally:
    a = Ally(name=name, gender='f', strength=10, to_hit=5, flags=flags or [])
    a.status = AllyStatus.SERVANT
    return a


class _FakePlayer:
    def __init__(self, gold=10_000, allies=None, name='Rulan'):
        self.name = name
        self.party = list(allies or [])
        self.unsaved_changes = False
        self._gold = gold

    def subtract_silver(self, kind, amount) -> bool:
        if self._gold < amount:
            return False
        self._gold -= amount
        return True


class _FakeClient:
    def __init__(self):
        self.room = 42
        self.virtual_location = None


class _FakeServer:
    def __init__(self):
        self.clients = {}


class _FakeCtx:
    def __init__(self, player):
        self.player = player
        self.client = _FakeClient()
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


class TestAllyGuildTraining(unittest.IsolatedAsyncioTestCase):
    """Note: setUp/tearDown redirect net_common.run_server_dir to a temp
    dir for the duration of each test -- _train_flag() calls the real
    net_common.append_battle_log(), and without this every run here was writing
    "Rulan had BARDA trained..." lines straight into the live
    run/server/battle.log (same pattern test_dwarf.py's on_killed tests
    and test_ally_starvation.py already isolate against)."""

    def setUp(self):
        import net_common
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_run_server_dir = net_common.run_server_dir
        net_common.run_server_dir = self._tmp.name

    def tearDown(self):
        import net_common
        net_common.run_server_dir = self._orig_run_server_dir
        self._tmp.cleanup()


    async def test_discipline_applies_elite_flag_and_charges_gold(self):
        ally = _make_ally()
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        await _train_discipline(ctx, ally)
        self.assertIn(AllyFlags.ELITE, ally.flags)
        self.assertEqual(player._gold, 5000 - _COST_DISCIPLINE)

    async def test_combat_training_applies_flag(self):
        ally = _make_ally()
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        await _train_combat(ctx, ally)
        self.assertIn(AllyFlags.COMBAT_TRAINED, ally.flags)
        self.assertEqual(player._gold, 5000 - _COST_COMBAT)

    async def test_armor_applies_flag(self):
        ally = _make_ally()
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        await _train_armor(ctx, ally)
        self.assertIn(AllyFlags.ARMORED, ally.flags)
        self.assertEqual(player._gold, 5000 - _COST_ARMOR)

    async def test_tracking_applies_flag(self):
        ally = _make_ally()
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        await _train_tracking(ctx, ally)
        self.assertIn(AllyFlags.TRACKING, ally.flags)
        self.assertEqual(player._gold, 5000 - _COST_TRACKING)

    async def test_already_trained_is_free(self):
        ally = _make_ally(flags=[AllyFlags.ELITE])
        player = _FakePlayer(gold=100, allies=[ally])
        ctx = _FakeCtx(player)
        await _train_discipline(ctx, ally)   # no answers queued -- must not prompt
        self.assertEqual(player._gold, 100)
        self.assertIn('already IS', ctx.sent())

    async def test_armor_refused_for_mount(self):
        ally = _make_ally(flags=[AllyFlags.MOUNT])
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        await _train_armor(ctx, ally)
        self.assertNotIn(AllyFlags.ARMORED, ally.flags)
        self.assertEqual(player._gold, 5000)
        self.assertIn('will not fit', ctx.sent())

    async def test_tracking_refused_for_mount(self):
        ally = _make_ally(flags=[AllyFlags.MOUNT])
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        await _train_tracking(ctx, ally)
        self.assertNotIn(AllyFlags.TRACKING, ally.flags)
        self.assertIn('would not make a good tracker', ctx.sent())

    async def test_declining_prompt_blocks_training(self):
        ally = _make_ally()
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        ctx.set_answers(['N'])
        await _train_discipline(ctx, ally)
        self.assertNotIn(AllyFlags.ELITE, ally.flags)
        self.assertEqual(player._gold, 5000)

    async def test_insufficient_gold_blocks_training(self):
        ally = _make_ally()
        player = _FakePlayer(gold=10, allies=[ally])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        await _train_discipline(ctx, ally)
        self.assertNotIn(AllyFlags.ELITE, ally.flags)
        self.assertEqual(player._gold, 10)
        self.assertIn('not have enough gold', ctx.sent())

    async def test_body_build_increments_level_and_strength(self):
        ally = _make_ally()
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        starting_strength = ally.strength
        await _train_body(ctx, ally)
        self.assertEqual(ally.body_build, 1)
        self.assertEqual(ally.strength, starting_strength + _BODY_BUILD_STR_BONUS)
        self.assertEqual(player._gold, 5000 - _BODY_BUILD_BASE_COST)

    async def test_body_build_cost_scales_with_level(self):
        ally = _make_ally()
        ally.body_build = 3
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        ctx.set_answers(['Y'])
        await _train_body(ctx, ally)
        self.assertEqual(ally.body_build, 4)
        self.assertEqual(player._gold, 5000 - (4 * _BODY_BUILD_BASE_COST))

    async def test_body_build_caps_at_max_level(self):
        ally = _make_ally()
        ally.body_build = _MAX_BODY_BUILD_LEVEL
        player = _FakePlayer(gold=5000, allies=[ally])
        ctx = _FakeCtx(player)
        await _train_body(ctx, ally)   # no answers queued -- must not prompt
        self.assertEqual(ally.body_build, _MAX_BODY_BUILD_LEVEL)
        self.assertEqual(player._gold, 5000)
        self.assertIn('as large as possible', ctx.sent())


class TestAllyGuildMain(unittest.IsolatedAsyncioTestCase):

    async def test_no_allies_greets_and_exits(self):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        await guild_main(ctx)
        self.assertIn('do not have any Allies', ctx.sent())

    async def test_menu_cancel_exits_cleanly(self):
        ally = _make_ally()
        player = _FakePlayer(allies=[ally])
        ctx = _FakeCtx(player)
        ctx.set_answers([''])   # blank input at the main menu -> leave
        await guild_main(ctx)
        self.assertIn("ALLIES' GUILD", ctx.sent())


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


class TestAllyGuildMovementHook(unittest.IsolatedAsyncioTestCase):

    async def test_level4_room42_east_triggers_guild(self):
        ctx = _make_movement_ctx(map_level=4, room=42)
        with patch('street.allies_guild.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'e')
        mock_main.assert_awaited_once_with(ctx)
        ctx.server._move.assert_not_awaited()

    async def test_wrong_level_falls_through(self):
        ctx = _make_movement_ctx(map_level=1, room=42)
        with patch('street.allies_guild.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'e')
        mock_main.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'e')

    async def test_wrong_room_falls_through(self):
        ctx = _make_movement_ctx(map_level=4, room=1)
        with patch('street.allies_guild.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'e')
        mock_main.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'e')

    async def test_wrong_direction_falls_through(self):
        ctx = _make_movement_ctx(map_level=4, room=42)
        with patch('street.allies_guild.main', new=AsyncMock()) as mock_main:
            await MoveCommand().execute(ctx, 'n')
        mock_main.assert_not_awaited()
        ctx.server._move.assert_awaited_once_with(ctx, 'n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
