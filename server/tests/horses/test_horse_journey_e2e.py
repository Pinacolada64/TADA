"""tests/test_horse_journey_e2e.py

Full player journeys chaining the real command objects across the wild-horse
mount pipeline, rather than exercising each piece in isolation the way
test_lasso.py, test_class_taming.py, and test_wild_horse_placement.py do.

Journey 1 (non-Druid/Ranger): reach the wild horse's room, join the fight
that's already underway, LASSO it -- a too-short name reprompts, then a
valid name captures it -- confirm it lands in the party as a MOUNT ally,
then head to Jake's Stable, equip Saddle + Horse Armor, and Train Horse.

Journey 2 (Druid/Ranger): reach the wild horse's room and engage it as the
fight's own leader.  CombatSession._run_loop() checks the passive class-
affinity tame *before* it ever prompts for [A]ttack/[F]lee, so a lucky roll
ends the fight outright -- LASSO is never involved.  Then the same Jake's
Stable equip+train sequence.

Why journey 1 needs two contexts: CombatSession._run_loop() (the fight's
leader) owns the leader's connection with its own blocking ctx.prompt() for
the whole fight -- see simple_server.py Server._leave_combat_on_move()'s
docstring, "the leader's connection is occupied by CombatSession._run_loop()'s
own prompt for the fight's duration, so it can't normally reach _move()
mid-fight". The same is true of LASSO: the leader's own raw input is only
ever interpreted as attack/flee/charge, never dispatched to LassoCommand.
In real play LASSO is reachable by a *bystander* -- someone who typed
'attack' into an already-open fight, which returns after one swing instead
of blocking -- so this test keeps a second ("dummy") context alive in the
fight as its leader, exactly the role another party member/player would
play, while our real test subject joins, lassos, and leaves.

Run with:
    python -m pytest tests/test_horse_journey_e2e.py -v
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

nc_stub_needed = 'network_context' not in sys.modules
if nc_stub_needed:
    import types
    nc_stub = types.ModuleType('network_context')
    nc_stub.GameContext = object
    sys.modules.setdefault('network_context', nc_stub)

# test_wild_horse_placement.py notes that other test modules leave stubbed
# sys.modules['network_context']/['net_common'] behind that break simple_server's
# real import -- force a clean reimport of the real modules regardless of
# what ran before us.
for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server, _WILD_HORSE_ROOMS, _WILD_HORSE_MONSTER_NUMBER
from base_classes import Gender, PlayerClass
from bar.ally_data import AllyFlags
from commands.attack import AttackCommand
from party import Party
from commands.lasso import LassoCommand
from commands.movement import MoveCommand
from commands.use import UseCommand
from street.jakes import _train_horse


class _FakePlayer:
    def __init__(self, name, char_class=PlayerClass.FIGHTER, gender=Gender.MALE,
                 gold=10_000, allies=None):
        self.name = name
        self.char_class = char_class
        self.gender = gender
        # A real Party, not a bare list -- Party has no .append(), only
        # add_member()/add(); a plain list here would (and did) mask
        # combat/engine.py's mount-capture code calling the wrong API
        # against a real Player.
        self.party = Party(allies)
        self.map_level = 1
        self.hit_points = 30
        self.readied_weapon = None
        self.stats = {'Strength': 10}
        self.unsaved_changes = False
        self.inventory = MagicMock()
        self.inventory.entries = MagicMock(return_value=[])
        self.return_key = 'Enter'
        self._gold = gold

    def get_silver(self, kind):
        return self._gold

    def subtract_silver(self, kind, amount) -> bool:
        if self._gold < amount:
            return False
        self._gold -= amount
        return True

    def query_flag(self, flag) -> bool:
        return False


class _FakeClient:
    def __init__(self, room):
        self.room = room
        self.virtual_location = None


class _FakeCtx:
    def __init__(self, player, server, room, prompt_answers=None):
        self.player = player
        self.client = _FakeClient(room=room)
        self.server = server
        self._sent: list[str] = []
        self._answers = iter(prompt_answers or [])

    def set_answers(self, answers):
        self._answers = iter(answers)

    async def send(self, msg, **kwargs):
        if isinstance(msg, list):
            self._sent.extend(str(m) for m in msg)
        else:
            self._sent.append(str(msg))

    async def send_room(self, msg, **kwargs):
        pass

    async def prompt(self, *a, **kw):
        return next(self._answers, None)

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _horse_room(server) -> int:
    return next(n for n in _WILD_HORSE_ROOMS
                if server.game_map.rooms[n].monster == _WILD_HORSE_MONSTER_NUMBER)


def _entry(item):
    e = MagicMock()
    e.item = item
    return e


async def _equip_saddle_and_armor(ctx, player) -> None:
    from items import Item, ItemCategory
    saddle = Item(id_number=162, name='saddle', category=ItemCategory.ITEM)
    armor  = Item(id_number=163, name='horse armour', category=ItemCategory.ITEM)

    player.inventory.entries = MagicMock(return_value=[_entry(saddle)])
    ctx.set_answers(['1'])
    await UseCommand().execute(ctx)

    player.inventory.entries = MagicMock(return_value=[_entry(armor)])
    ctx.set_answers(['1'])
    await UseCommand().execute(ctx)


class TestNonDruidRangerLassoJourney(unittest.IsolatedAsyncioTestCase):

    @patch('combat.engine.CombatSession._append_capture_log')
    async def test_full_journey_lasso_capture_then_jakes_training(self, _log):
        server = Server('127.0.0.1', 0)
        horse_room = _horse_room(server)

        # A "dummy" party member already fighting the horse -- keeps the
        # CombatSession open (as its leader) while our real subject joins,
        # lassos, and leaves. See module docstring for why this is needed.
        dummy = _FakePlayer(name='Dummy', char_class=PlayerClass.FIGHTER)
        dummy_ctx = _FakeCtx(dummy, server=server, room=horse_room)

        async def _dummy_prompt(*a, **kw):
            await asyncio.sleep(0)
            return 'a'
        dummy_ctx.prompt = _dummy_prompt

        leader_task = asyncio.create_task(AttackCommand().execute(dummy_ctx))
        await asyncio.sleep(0)   # let the dummy become the fight's leader

        # Our subject: a Fighter (no passive taming) "walks" into the horse's
        # room (mocking movement rather than solving level-1's exit graph).
        rulan = _FakePlayer(name='Rulan', char_class=PlayerClass.FIGHTER)
        ctx = _FakeCtx(rulan, server=server, room=1)
        ctx.client.room = horse_room

        result = await AttackCommand().execute(ctx)   # joins as a bystander
        self.assertTrue(result.success)
        session = server.active_combats[horse_room]
        self.assertIn(ctx, session.attackers)

        # Name validation: too short reprompts, then a valid name captures it.
        ctx.set_answers(['AB', 'STARDUST'])
        result = await LassoCommand().execute(ctx)
        self.assertTrue(result.success)
        self.assertIn('Name must be 4-12 characters.', ctx.sent())
        self.assertEqual(len(rulan.party), 1)

        mount = rulan.party[0]
        self.assertEqual(mount.name, 'STARDUST')
        self.assertIn(AllyFlags.MOUNT, mount.flags)

        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.wait_for(leader_task, timeout=1)

        # Off to Jake's Stable: level 5, room 157, move east.
        ctx.player.map_level = 5
        ctx.client.room = 157
        ctx.server._show_room = AsyncMock()
        with patch('street.jakes.main', new=AsyncMock()) as jakes_main:
            await MoveCommand().execute(ctx, 'e')
        jakes_main.assert_awaited_once_with(ctx)

        # Buy (simulated) and equip a Saddle + Horse Armor, then train.
        await _equip_saddle_and_armor(ctx, rulan)
        self.assertIn(AllyFlags.SADDLED, mount.flags)
        self.assertIn(AllyFlags.ARMORED, mount.flags)

        ctx.set_answers(['Y'])
        gold_before = rulan._gold
        await _train_horse(ctx)
        self.assertIn(AllyFlags.ELITE, mount.flags)
        self.assertLess(rulan._gold, gold_before)


class TestDruidRangerPassiveTameJourney(unittest.IsolatedAsyncioTestCase):

    @patch('combat.engine.CombatSession._append_capture_log')
    async def test_full_journey_passive_tame_then_jakes_training(self, _log):
        server = Server('127.0.0.1', 0)
        horse_room = _horse_room(server)

        # A Druid "walks" into the horse's room and attacks -- as the fight's
        # own leader this time, since the passive tame check runs inside
        # CombatSession._run_loop() itself, before any [A]ttack/[F]lee
        # prompt, so no second context is needed here.
        rulan = _FakePlayer(name='Rulan', char_class=PlayerClass.DRUID, gender=Gender.FEMALE)
        ctx = _FakeCtx(rulan, server=server, room=1)
        ctx.client.room = horse_room
        ctx.set_answers(['MOONBEAM'])   # horse's name, prompted by _finalize_mount_capture

        with patch('combat.engine.random.randint', return_value=1):   # 1 <= 15 -> success
            result = await AttackCommand().execute(ctx)

        self.assertTrue(result.success)
        self.assertIn('as its mistress!', ctx.sent())
        self.assertEqual(len(rulan.party), 1)
        mount = rulan.party[0]
        self.assertIn(AllyFlags.MOUNT, mount.flags)
        self.assertNotIn(horse_room, server.active_combats)   # fight cleaned up

        # Off to Jake's Stable.
        ctx.player.map_level = 5
        ctx.client.room = 157
        ctx.server._show_room = AsyncMock()
        with patch('street.jakes.main', new=AsyncMock()) as jakes_main:
            await MoveCommand().execute(ctx, 'e')
        jakes_main.assert_awaited_once_with(ctx)

        await _equip_saddle_and_armor(ctx, rulan)
        self.assertIn(AllyFlags.SADDLED, mount.flags)
        self.assertIn(AllyFlags.ARMORED, mount.flags)

        ctx.set_answers(['Y'])
        gold_before = rulan._gold
        await _train_horse(ctx)
        self.assertIn(AllyFlags.ELITE, mount.flags)
        self.assertLess(rulan._gold, gold_before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
