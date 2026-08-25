"""tests/combat/test_lurk_command.py — LurkCommand.execute() (commands/lurk.py)
and CombatSession.join(is_lurking=True) (combat/engine.py), the standalone
'lurk'/'lurk <name>' command SPUR types at the top-level prompt the same
way as 'ATT' (SPUR.MAIN.S:87).

Coverage:
  - LurkCommand mirrors AttackCommand's join/continue-fight dispatch (see
    tests/combat/test_attack_command.py), but is gated up front on having
    a living ally, and joins with is_lurking=True
  - CombatSession.join(is_lurking=True): refuses without a living ally
    ("No allies — no LURK!"), doesn't consume a swing/announce a join on
    refusal; a melee/empty-ammo/LIGHT-named weapon skips the bystander's
    swing entirely (still costs Honor via combat/lurk.py's resolve_swing,
    no damage applied to the monster); a loaded ammo weapon still fires
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bar.ally_data import Ally, AllyStatus
from combat.engine import CombatSession
from combat.resolution import AttackResult
from commands.lurk import LurkCommand
from item_system import WeaponClass


def _make_ally(name='Grok', hit_points=10):
    a = Ally(name=name, gender='m', strength=10, to_hit=0, flags=[])
    a.status = AllyStatus.SERVANT
    a.hit_points = hit_points
    return a


class _FakeSession:
    def __init__(self, monster_name='TROLL'):
        self.monster = {'name': monster_name}
        self.attackers = []
        self._done = asyncio.Event()
        self.join = AsyncMock(side_effect=self._join)

    async def _join(self, ctx, is_lurking=False):
        if ctx not in self.attackers:
            self.attackers.append(ctx)


def _make_ctx(session=None, room_no=1, hit_points=30, allies=None):
    player = MagicMock()
    player.hit_points = hit_points
    player.party = list(allies if allies is not None else [_make_ally()])

    server = MagicMock()
    server.active_combats = {room_no: session} if session else {}

    client = MagicMock()
    client.room = room_no

    ctx = MagicMock()
    ctx.player = player
    ctx.server = server
    ctx.client = client
    ctx.send = AsyncMock()
    return ctx


# ---------------------------------------------------------------------------
# LurkCommand.execute()
# ---------------------------------------------------------------------------

class TestLurkJoinsExistingFight(unittest.IsolatedAsyncioTestCase):
    async def test_bystander_lurk_joins_with_lurking_flag(self):
        session = _FakeSession()
        ctx = _make_ctx(session=session)
        cmd = LurkCommand()
        res = await cmd.execute(ctx)
        self.assertTrue(res.success)
        session.join.assert_awaited_once_with(ctx, is_lurking=True)

    async def test_already_joined_bystander_lurks_again_not_blocked(self):
        session = _FakeSession()
        ctx = _make_ctx(session=session)
        cmd = LurkCommand()

        await cmd.execute(ctx)
        await cmd.execute(ctx)

        self.assertEqual(session.join.await_count, 2)

    async def test_dead_player_cannot_lurk(self):
        session = _FakeSession()
        ctx = _make_ctx(session=session, hit_points=-1)
        cmd = LurkCommand()
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        session.join.assert_not_awaited()

    async def test_no_living_ally_refused_before_joining(self):
        session = _FakeSession()
        ctx = _make_ctx(session=session, allies=[])
        cmd = LurkCommand()
        res = await cmd.execute(ctx)
        self.assertFalse(res.success)
        session.join.assert_not_awaited()
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('no lurk', sent.lower())

    async def test_name_mismatch_rejected_even_when_already_joined(self):
        session = _FakeSession(monster_name='TROLL')
        ctx = _make_ctx(session=session)
        cmd = LurkCommand()

        await cmd.execute(ctx)
        res = await cmd.execute(ctx, 'goblin')

        self.assertFalse(res.success)
        self.assertEqual(session.join.await_count, 1)


# ---------------------------------------------------------------------------
# CombatSession.join(is_lurking=True)
# ---------------------------------------------------------------------------

class _FakeWeapon:
    def __init__(self, weapon_class=WeaponClass.BASH_SLASH, name='Sword'):
        self.weapon_class = weapon_class
        self.stability = 50
        self.to_hit = 50
        self.name = name
        self.number = 1
        self.id_number = 1
        self.sound_effect = None


class _FakePlayer:
    def __init__(self, *, allies=None, hit_points=15, honor=1000, weapon=None, ammo_rounds=0):
        self.name = 'Rulan'
        self.party = list(allies or [])
        self.hit_points = hit_points
        self.honor = honor
        self.char_class = None
        self.readied_weapon = weapon
        self.ammo_rounds = ammo_rounds
        self.unsaved_changes = False
        from base_classes import PlayerStat
        self.stats = {PlayerStat.STR: 10, PlayerStat.CON: 10, PlayerStat.INT: 10,
                      PlayerStat.EGY: 10, PlayerStat.DEX: 10}

    def query_flag(self, flag):
        return False

    def adjust_honor(self, adjustment):
        if adjustment == 0:
            return None
        self.honor += adjustment
        self.unsaved_changes = True
        phrase = 'less' if adjustment < 0 else 'more'
        return self.honor, f'(You feel {phrase} honorable) ({adjustment:+d})'


class _FakeClient:
    room = 1


class _FakeServer:
    def __init__(self):
        self.clients = {}
        self.active_combats = {}
        self.weapons = []


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


class TestSessionJoinLurking(unittest.IsolatedAsyncioTestCase):
    async def test_refused_without_a_living_ally(self):
        player = _FakePlayer(allies=[], weapon=_FakeWeapon())
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 20}, room_no=1)

        await session.join(ctx, is_lurking=True)

        self.assertNotIn(ctx, session.attackers)
        self.assertIn('No allies — no LURK!', ctx.sent())

    async def test_melee_swing_skipped_no_damage_to_monster(self):
        ally = _make_ally()
        player = _FakePlayer(allies=[ally], weapon=_FakeWeapon(name='LONG SWORD'))
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 20}, room_no=1)

        await session.join(ctx, is_lurking=True)

        self.assertEqual(session.monster['strength'], 20)
        self.assertIn('You lurk behind your allies.', ctx.sent())

    async def test_loaded_ammo_weapon_still_swings(self):
        ally = _make_ally()
        weapon = _FakeWeapon(weapon_class=WeaponClass.PROJECTILE, name='CROSSBOW')
        player = _FakePlayer(allies=[ally], weapon=weapon, ammo_rounds=5)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 20}, room_no=1)

        with patch.object(
            session, '_swing',
            return_value=AttackResult(hit=True, damage=3, weapon_name='CROSSBOW'),
        ) as mock_swing:
            await session.join(ctx, is_lurking=True)

        mock_swing.assert_called_once_with(ctx, is_lurking=True)
        self.assertEqual(session.monster['strength'], 17)
        self.assertIn("You fire over your ally's head..", ctx.sent())


if __name__ == '__main__':
    unittest.main()
