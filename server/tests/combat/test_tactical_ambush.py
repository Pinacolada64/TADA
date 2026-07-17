"""tests/combat/test_tactical_ambush.py

Unit tests for CombatSession._check_tactical_ambush()/_ally_deserts(),
ported from SPUR.MISC4.S's "tactical"/"desert" subroutines: once per
encounter, before the first exchange, an ambush falls on a random
deployment slot (POINT 50% / FLANK 20% / REAR 30%, ORDER's positions --
commands/order.py). Whoever's posted there shouts a warning and rolls to
hold; an empty slot leaves the player themself at risk. Either way,
"caught off guard" sets CombatSession._ambush_first_strike, consumed by
_run_loop() as a bonus monster attack on its first swing this fight
(SPUR.COMBAT.S:31 "Surprise attack..").

Coverage:
  - friendly encounter (race/alignment affinity) -> skipped entirely
  - monster already in player.monsters_killed -> skipped (SPUR's xm$
    equivalent)
  - occupied slot, servant holds (roll <= hp) -> shout only, no ambush
  - occupied slot, ELITE servant fails the roll -> "TOO CLEVER", immune,
    stays in the party
  - occupied slot, non-ELITE servant fails the roll -> "WAS CAUGHT OFF
    GUARD", player._ambush_first_strike set; 1-in-10 chance actually
    deserts (removed from party, AllyStatus.FREE), else just rattled
  - empty slot -> flavor narration, then the player's own risk roll
    (vs Intelligence + xp_level, plus a flat 10%)
  - _ally_deserts() room-flavor text: ordinary room / water room /
    level 6+ water-as-vacuum room
  - _run_loop() end-to-end: _ambush_first_strike triggers exactly one
    bonus "Surprise attack.." monster swing on the very first exchange

Run with:
    python -m pytest tests/combat/test_tactical_ambush.py -v
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from bar.ally_data import Ally, AllyFlags, AllyPosition, AllyStatus
from combat.engine import CombatSession
from party import Party


def _make_ally(name='ALFRED', hp=10, position=AllyPosition.EMPTY,
               flags=None, status=AllyStatus.SERVANT):
    ally = Ally(name, 'm', 10, 5, flags or [])
    ally.status = status
    ally.hit_points = hp
    ally.position = position
    return ally


class _FakePlayer:
    def __init__(self, allies=None, race='Human', monsters_killed=None,
                 map_level=1, intelligence=10, xp_level=1):
        self.name = 'Rulan'
        self.char_race = race
        self.party = Party(allies or [])
        self.monsters_killed = monsters_killed or []
        self.map_level = map_level
        self.stats = {'Intelligence': intelligence}
        self.xp_level = xp_level
        self.unsaved_changes = False


class _FakeRoom:
    def __init__(self, flags=None):
        self.flags = flags or []


class _FakeGameMap:
    def __init__(self, room=None):
        self._room = room

    def get_room(self, level, room_no):
        return self._room


class _FakeClient:
    room = 1


class _FakeServer:
    def __init__(self, game_map=None):
        self.game_map = game_map
        self.clients = {}


class _FakeCtx:
    def __init__(self, player, game_map=None):
        self.player = player
        self.client = _FakeClient()
        self.server = _FakeServer(game_map)
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


def _monster(evil=False, good=False, number=99):
    flags = {}
    if evil:
        flags['evil'] = True
    if good:
        flags['good'] = True
    return {'name': 'TROLL', 'flags': flags, 'number': number}


class TestTacticalAmbushGates(unittest.IsolatedAsyncioTestCase):
    async def test_friendly_encounter_is_skipped(self):
        player = _FakePlayer(race='Ogre')
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(evil=True), room_no=1)

        await session._check_tactical_ambush(ctx)

        self.assertEqual(ctx.sent(), '')
        self.assertFalse(session._ambush_first_strike)

    async def test_already_killed_monster_is_skipped(self):
        player = _FakePlayer(monsters_killed=[99])
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(number=99), room_no=1)

        await session._check_tactical_ambush(ctx)

        self.assertEqual(ctx.sent(), '')
        self.assertFalse(session._ambush_first_strike)


class TestTacticalAmbushOccupiedSlot(unittest.IsolatedAsyncioTestCase):
    async def test_servant_holds_the_line(self):
        ally = _make_ally(hp=20, position=AllyPosition.POINT)
        player = _FakePlayer(allies=[ally])
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(), room_no=1)

        with patch('combat.engine.random.choice', return_value=1), \
             patch('combat.engine.random.randint', return_value=0):  # roll = -9, <= hp
            await session._check_tactical_ambush(ctx)

        self.assertIn("ALFRED shouts 'To the front!'", ctx.sent())
        self.assertNotIn('caught off guard', ctx.sent())
        self.assertFalse(session._ambush_first_strike)
        self.assertIs(player.party.members[0], ally)  # still in the party

    async def test_elite_servant_is_too_clever_to_be_caught(self):
        ally = _make_ally(hp=1, position=AllyPosition.POINT, flags=[AllyFlags.ELITE])
        player = _FakePlayer(allies=[ally])
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(), room_no=1)

        with patch('combat.engine.random.choice', return_value=1), \
             patch('combat.engine.random.randint', return_value=298):  # roll = 20, > hp
            await session._check_tactical_ambush(ctx)

        self.assertIn('ALFRED is too clever to be caught off guard.', ctx.sent())
        self.assertFalse(session._ambush_first_strike)
        self.assertIs(player.party.members[0], ally)

    async def test_non_elite_servant_caught_off_guard_but_holds_on(self):
        ally = _make_ally(hp=1, position=AllyPosition.POINT)
        player = _FakePlayer(allies=[ally])
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(), room_no=1)

        with patch('combat.engine.random.choice', return_value=1), \
             patch('combat.engine.random.randint', side_effect=[298, 3]):  # roll>hp, desert roll != 5
            await session._check_tactical_ambush(ctx)

        self.assertIn('ALFRED was caught off guard!', ctx.sent())
        self.assertTrue(session._ambush_first_strike)
        self.assertIs(player.party.members[0], ally)  # didn't actually flee
        self.assertEqual(ally.status, AllyStatus.SERVANT)

    async def test_non_elite_servant_caught_off_guard_and_deserts(self):
        ally = _make_ally(hp=1, position=AllyPosition.POINT)
        player = _FakePlayer(allies=[ally])
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(), room_no=1)

        with patch('combat.engine.random.choice', return_value=1), \
             patch('combat.engine.random.randint', side_effect=[298, 5]), \
             patch('bar.ally_data.load_allies', return_value=[]), \
             patch('bar.ally_data.save_ally_roster'):
            await session._check_tactical_ambush(ctx)

        self.assertIn('ALFRED was caught off guard!', ctx.sent())
        self.assertIn('runs away screaming!', ctx.sent())
        self.assertTrue(session._ambush_first_strike)
        self.assertNotIn(ally, player.party.members)
        self.assertEqual(ally.status, AllyStatus.FREE)
        self.assertTrue(player.unsaved_changes)

    async def test_dead_ally_in_the_slot_is_treated_as_empty(self):
        # hit_points <= 0 -- shouldn't shout or hold a position it can't defend.
        corpse = _make_ally(hp=0, position=AllyPosition.POINT)
        player = _FakePlayer(allies=[corpse], intelligence=99, xp_level=99)
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(), room_no=1)

        with patch('combat.engine.random.choice', return_value=1), \
             patch('combat.engine.random.randint', return_value=0):
            await session._check_tactical_ambush(ctx)

        self.assertNotIn('ALFRED', ctx.sent())
        self.assertIn('To the front!', ctx.sent())


class TestTacticalAmbushEmptySlot(unittest.IsolatedAsyncioTestCase):
    async def test_player_caught_off_guard_via_stat_roll(self):
        player = _FakePlayer(intelligence=1, xp_level=1)  # threshold = 2
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(), room_no=1)

        # slot=3 (REAR): roll = (298//10)-9 + 3*3 = 20+9 = 29 > 2 -> caught,
        # short-circuits before the flat-10% randint call.
        with patch('combat.engine.random.choice', return_value=3), \
             patch('combat.engine.random.randint', side_effect=[298]):
            await session._check_tactical_ambush(ctx)

        self.assertIn('To the rear!', ctx.sent())
        self.assertIn('You are caught off guard!', ctx.sent())
        self.assertTrue(session._ambush_first_strike)

    async def test_player_caught_off_guard_via_flat_ten_percent(self):
        player = _FakePlayer(intelligence=99, xp_level=99)
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(), room_no=1)

        with patch('combat.engine.random.choice', return_value=1), \
             patch('combat.engine.random.randint', side_effect=[0, 5]):
            await session._check_tactical_ambush(ctx)

        self.assertIn('You are caught off guard!', ctx.sent())
        self.assertTrue(session._ambush_first_strike)

    async def test_player_not_caught(self):
        player = _FakePlayer(intelligence=99, xp_level=99)
        ctx = _FakeCtx(player)
        session = CombatSession(_monster(), room_no=1)

        with patch('combat.engine.random.choice', return_value=1), \
             patch('combat.engine.random.randint', side_effect=[0, 3]):
            await session._check_tactical_ambush(ctx)

        self.assertIn('To the front!', ctx.sent())
        self.assertNotIn('caught off guard', ctx.sent())
        self.assertFalse(session._ambush_first_strike)


class TestAllyDesertsRoomFlavor(unittest.IsolatedAsyncioTestCase):
    async def _run(self, *, flags, map_level):
        ally = _make_ally()
        player = _FakePlayer(allies=[ally], map_level=map_level)
        room = _FakeRoom(flags=flags)
        ctx = _FakeCtx(player, game_map=_FakeGameMap(room))
        session = CombatSession(_monster(), room_no=1)

        with patch('bar.ally_data.load_allies', return_value=[]), \
             patch('bar.ally_data.save_ally_roster'):
            await session._ally_deserts(ctx, ally)
        return ctx

    async def test_ordinary_room(self):
        ctx = await self._run(flags=[], map_level=1)
        self.assertIn('runs away screaming!', ctx.sent())

    async def test_water_room_below_level_6(self):
        ctx = await self._run(flags=['water'], map_level=1)
        self.assertIn('jumps overboard and swims away!', ctx.sent())

    async def test_water_flagged_room_at_level_6_reads_as_vacuum(self):
        ctx = await self._run(flags=['water'], map_level=6)
        self.assertIn('fires retros, and flees!', ctx.sent())


class TestTacticalAmbushFeedsFirstStrike(unittest.IsolatedAsyncioTestCase):
    async def test_ambush_first_strike_grants_bonus_monster_attack(self):
        """End-to-end through _run_loop(): a preset _ambush_first_strike
        causes exactly one extra monster swing (with the Surprise attack..
        narration) on the fight's very first exchange, then never again."""
        monster = {'name': 'TROLL', 'hit_points': 999, 'to_hit': 10, 'strength': 1}
        session = CombatSession(monster, room_no=1)

        player = MagicMock()
        player.name = 'Rulan'
        player.hit_points = 999
        player.stats = {}
        player.readied_weapon = None
        player.unsaved_changes = False
        player.return_key = 'Enter'
        player.query_flag = lambda flag: False
        player.party = []          # no ally swings to worry about
        player.ammo_rounds = 0     # no missile first strike

        ctx = MagicMock()
        ctx.player = player
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()
        # Attack once, then exit on the next prompt so the loop only
        # drives a single exchange.
        ctx.prompt = AsyncMock(side_effect=['a', None])

        session._try_class_tame = AsyncMock(return_value=False)
        session._check_crystal_pendant = AsyncMock(return_value=None)

        async def fake_ambush_check(ctx):
            session._ambush_first_strike = True
        session._check_tactical_ambush = fake_ambush_check

        from combat.resolution import AttackResult, MonsterAttackResult

        with patch('combat.engine.monster_attacks') as mock_monster_attacks, \
             patch.object(session, '_swing') as mock_swing:
            mock_monster_attacks.return_value = MonsterAttackResult(hit=False, damage=0)
            mock_swing.return_value = AttackResult(hit=False, damage=0)
            await session._run_loop(ctx)

        sent = [str(c.args[0]) if c.args else '' for c in ctx.send.call_args_list]
        surprise_count = sum(1 for s in sent if 'Surprise attack' in s)
        self.assertEqual(surprise_count, 1)
        self.assertEqual(mock_monster_attacks.call_count, 2)  # normal swing + bonus
        self.assertFalse(session._ambush_first_strike)  # consumed


if __name__ == '__main__':
    unittest.main()
