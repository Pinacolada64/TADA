"""tests/test_charge.py

Unit tests for Phase 2/3 of the MOUNT/DISMOUNT/CHARGE plan (see
MECHANICS.md "Horses"): the CHARGE combat mechanic, ported from the skip
branch's SPUR.COMBAT.S (m.attack / p.attack / unmount / lurk.a), which the
master branch's SPUR.COMBAT.S doesn't have at all.

Coverage:
  - player_attacks(): CHARGE gives +2 hit threshold and doubles damage
    (both the "ease of use" fast path and the normal hit path)
  - player_attacks(): miss-over-the-top -- mounted + melee weapon can
    whiff clean against an agile monster, independent of the normal roll
  - player_attacks(): miss-over-the-top does not apply to ranged weapons,
    or when not mounted
  - _roll_charge_first_strike(): eligibility roll direction for
    projectile vs. melee weapons
  - CombatSession._charge_unseat_check(): high-stat roll retains the
    mount; low roll + no saddle throws the player and deals fall damage
    (can kill); a Saddle gives a second save roll
  - CombatSession._try_redirect_to_mount(): agile monster can redirect a
    hit from the player onto the mount ally (narrative-only, no mount HP
    is deducted -- see docstring in engine.py)

Run with:
    python -m pytest tests/test_charge.py -v
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
from base_classes import PlayerClass, PlayerRace, PlayerStat
from combat.engine import CombatSession, _roll_charge_first_strike
from combat.resolution import player_attacks
from flags import PlayerFlags
from item_system import ItemType, WeaponClass


class _FakeWeapon:
    def __init__(self, weapon_class=WeaponClass.BASH_SLASH, stability=50, to_hit=50, name='Sword'):
        self.weapon_class = weapon_class
        self.stability = stability
        self.to_hit = to_hit
        self.name = name
        self.number = 1
        self.id_number = 1


def _make_mount(name='SILVER', saddled=False) -> Ally:
    flags = [AllyFlags.MOUNT]
    if saddled:
        flags.append(AllyFlags.SADDLED)
    a = Ally(name=name, gender='m', strength=20, to_hit=0, flags=flags)
    a.status = AllyStatus.SERVANT
    return a


class _FakePlayer:
    def __init__(self, *, mounted=False, allies=None, hit_points=30, stats=None,
                 char_class=None, char_race=None, xp_level=1):
        self.name = 'Rulan'
        self.party = list(allies or [])
        self.unsaved_changes = False
        self.hit_points = hit_points
        self.stats = stats or {PlayerStat.STR: 10, PlayerStat.CON: 10, PlayerStat.INT: 10,
                                PlayerStat.EGY: 10, PlayerStat.DEX: 10}
        self.char_class = char_class
        self.char_race = char_race
        self.xp_level = xp_level
        self.readied_weapon = None
        self._flags = {PlayerFlags.MOUNTED: mounted}

    def query_flag(self, flag):
        return bool(self._flags.get(flag, False))

    def set_flag(self, flag, verbose=False):
        self._flags[flag] = True
        return True, None

    def clear_flag(self, flag, verbose=False):
        self._flags[flag] = False
        return False, None


class _FakeClient:
    room = 1
    virtual_location = None


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


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# player_attacks(): CHARGE bonus and miss-over-the-top
# ---------------------------------------------------------------------------

class TestChargeDamageBonus(unittest.TestCase):
    def test_charge_doubles_damage_on_ease_helped_path(self):
        player = _FakePlayer()
        weapon = _FakeWeapon()
        monster = {'name': 'GOBLIN', 'to_hit': 4, 'strength': 20}
        # a=9 (>ws/10+2=7) -> ease_helped path. Fix both randint (hit roll)
        # and uniform (the damage-roll formula in _calc_player_damage) so
        # damage is fully deterministic and comparable between calls.
        with patch('combat.resolution.random.randint', return_value=9), \
             patch('combat.resolution.random.uniform', return_value=4.0):
            plain = player_attacks(player, weapon, monster, is_charge=False)
        with patch('combat.resolution.random.randint', return_value=9), \
             patch('combat.resolution.random.uniform', return_value=4.0):
            charged = player_attacks(player, weapon, monster, is_charge=True)
        self.assertTrue(plain.hit)
        self.assertTrue(charged.hit)
        self.assertTrue(charged.is_charge)
        self.assertGreater(plain.damage, 0)
        self.assertEqual(charged.damage, plain.damage * 2)

    def test_charge_doubles_damage_on_normal_hit_path(self):
        player = _FakePlayer()
        weapon = _FakeWeapon(stability=50)
        monster = {'name': 'GOBLIN', 'to_hit': 4, 'strength': 20}
        # a=2: not > ws/10+2=7 -> falls to normal roll; then a=2 again <= p2 -> hit
        with patch('combat.resolution.random.randint', return_value=2), \
             patch('combat.resolution.random.uniform', return_value=4.0):
            plain = player_attacks(player, weapon, monster, is_charge=False)
        with patch('combat.resolution.random.randint', return_value=2), \
             patch('combat.resolution.random.uniform', return_value=4.0):
            charged = player_attacks(player, weapon, monster, is_charge=True)
        self.assertTrue(plain.hit)
        self.assertTrue(charged.hit)
        self.assertGreater(plain.damage, 0)
        self.assertEqual(charged.damage, plain.damage * 2)

    def test_charge_raises_hit_threshold_by_two(self):
        from combat.resolution import hit_threshold
        player = _FakePlayer()
        # High stability (ws=9) keeps the "ease of use" fast-path (a>ws+2=11)
        # unreachable by a d10 roll, forcing the normal miss-check path.
        weapon = _FakeWeapon(stability=90)
        monster = {'name': 'GOBLIN', 'to_hit': 4, 'strength': 20}
        p2 = hit_threshold(weapon.weapon_class.value, monster['to_hit'], 0, 1)
        # Roll exceeds plain p2 (a miss) but not p2+2 (charge saves the hit)
        roll = p2 + 1
        assume_charge_threshold_higher = (p2 + 2) >= roll
        self.assertTrue(assume_charge_threshold_higher, 'test roll setup invalid')
        with patch('combat.resolution.random.randint', return_value=roll):
            plain = player_attacks(player, weapon, monster, is_charge=False)
        with patch('combat.resolution.random.randint', return_value=roll):
            charged = player_attacks(player, weapon, monster, is_charge=True)
        self.assertFalse(plain.hit)
        self.assertTrue(charged.hit)


class TestMissOverTheTop(unittest.TestCase):
    def test_mounted_melee_can_whiff_over_small_monster(self):
        player = _FakePlayer()
        weapon = _FakeWeapon(weapon_class=WeaponClass.BASH_SLASH)
        monster = {'name': 'GOBLIN', 'to_hit': 9, 'strength': 20}  # high agility
        with patch('combat.resolution.random.randint', return_value=1):
            result = player_attacks(player, weapon, monster, is_mounted=True)
        self.assertTrue(result.miss_over_top)
        self.assertFalse(result.hit)

    def test_not_mounted_never_misses_over_the_top(self):
        player = _FakePlayer()
        weapon = _FakeWeapon(weapon_class=WeaponClass.BASH_SLASH)
        monster = {'name': 'GOBLIN', 'to_hit': 9, 'strength': 20}
        with patch('combat.resolution.random.randint', return_value=1):
            result = player_attacks(player, weapon, monster, is_mounted=False)
        self.assertFalse(result.miss_over_top)

    def test_ranged_weapon_exempt_from_miss_over_the_top(self):
        player = _FakePlayer()
        weapon = _FakeWeapon(weapon_class=WeaponClass.PROJECTILE)
        monster = {'name': 'GOBLIN', 'to_hit': 9, 'strength': 20}
        with patch('combat.resolution.random.randint', return_value=1):
            result = player_attacks(player, weapon, monster, is_mounted=True)
        self.assertFalse(result.miss_over_top)


# ---------------------------------------------------------------------------
# _roll_charge_first_strike()
# ---------------------------------------------------------------------------

class TestChargeFirstStrikeRoll(unittest.TestCase):
    def test_melee_weapon_gets_plus_four(self):
        player = _FakePlayer(stats={PlayerStat.DEX: 100})
        player.readied_weapon = _FakeWeapon(weapon_class=WeaponClass.BASH_SLASH)
        monster = {'to_hit': 1}
        with patch('combat.engine.random.randint', return_value=1):
            eligible = _roll_charge_first_strike(player, monster)
        # roll(1) + 4 = 5; 5 + (1*4) = 9 < 100 -> eligible
        self.assertTrue(eligible)

    def test_projectile_weapon_gets_minus_four_penalty(self):
        player = _FakePlayer(stats={PlayerStat.DEX: 10})
        player.readied_weapon = _FakeWeapon(weapon_class=WeaponClass.PROJECTILE)
        monster = {'to_hit': 4}
        with patch('combat.engine.random.randint', return_value=1):
            eligible = _roll_charge_first_strike(player, monster)
        # roll(1) - 4 clamped to 1; 1 + (4*4) = 17, not < 10 -> not eligible
        self.assertFalse(eligible)


# ---------------------------------------------------------------------------
# CombatSession._charge_unseat_check()
# ---------------------------------------------------------------------------

class TestChargeUnseatCheck(unittest.IsolatedAsyncioTestCase):
    async def test_high_stat_roll_retains_mount(self):
        player = _FakePlayer(mounted=True, hit_points=50,
                              stats={PlayerStat.STR: 18, PlayerStat.CON: 18, PlayerStat.INT: 18,
                                     PlayerStat.EGY: 18, PlayerStat.DEX: 18},
                              char_class=PlayerClass.KNIGHT, xp_level=10)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)
        with patch('combat.engine.random.randint', return_value=100):
            thrown = await session._charge_unseat_check(ctx)
        self.assertFalse(thrown)
        self.assertTrue(player.query_flag(PlayerFlags.MOUNTED))
        self.assertIn('retain your mount', ctx.sent())

    async def test_low_roll_without_saddle_throws_player(self):
        player = _FakePlayer(mounted=True, hit_points=50,
                              stats={PlayerStat.STR: 1, PlayerStat.CON: 1, PlayerStat.INT: 1,
                                     PlayerStat.EGY: 1, PlayerStat.DEX: 1},
                              xp_level=1)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)
        with patch('combat.engine.random.randint', return_value=1):
            thrown = await session._charge_unseat_check(ctx)
        self.assertFalse(thrown)  # low fall damage shouldn't kill from 50 hp
        self.assertFalse(player.query_flag(PlayerFlags.MOUNTED))
        self.assertIn('knocks you from your mount', ctx.sent())

    async def test_fall_can_kill_at_low_hp(self):
        player = _FakePlayer(mounted=True, hit_points=1,
                              stats={PlayerStat.STR: 1, PlayerStat.CON: 1, PlayerStat.INT: 1,
                                     PlayerStat.EGY: 1, PlayerStat.DEX: 1},
                              xp_level=1)
        ctx = _FakeCtx(player)
        ctx.server.active_combats = {}
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)
        with patch('combat.engine.random.randint', return_value=1):
            thrown = await session._charge_unseat_check(ctx)
        self.assertTrue(thrown)
        self.assertLessEqual(player.hit_points, 0)

    async def test_saddle_gives_second_save_roll(self):
        player = _FakePlayer(mounted=True, hit_points=50, allies=[_make_mount(saddled=True)],
                              stats={PlayerStat.STR: 1, PlayerStat.CON: 1, PlayerStat.INT: 1,
                                     PlayerStat.EGY: 1, PlayerStat.DEX: 1},
                              xp_level=1)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)
        # First roll (the unseat score roll) = 1 (fails); second roll (saddle save) = 100 (saves)
        with patch('combat.engine.random.randint', side_effect=[1, 100]):
            thrown = await session._charge_unseat_check(ctx)
        self.assertFalse(thrown)
        self.assertTrue(player.query_flag(PlayerFlags.MOUNTED))
        self.assertIn('saddle saves you', ctx.sent())

    async def test_noop_when_not_mounted(self):
        player = _FakePlayer(mounted=False)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)
        thrown = await session._charge_unseat_check(ctx)
        self.assertFalse(thrown)
        self.assertEqual(ctx.sent(), '')


# ---------------------------------------------------------------------------
# CombatSession._try_redirect_to_mount()
# ---------------------------------------------------------------------------

class TestRedirectToMount(unittest.IsolatedAsyncioTestCase):
    async def test_redirect_succeeds_against_agile_monster(self):
        player = _FakePlayer(mounted=True, allies=[_make_mount(name='SILVER')])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'to_hit': 9}, room_no=1)
        with patch('combat.engine.random.randint', return_value=1):
            redirected = await session._try_redirect_to_mount(ctx)
        self.assertTrue(redirected)
        self.assertIn('strikes SILVER instead', ctx.sent())

    async def test_no_redirect_without_mount_ally(self):
        player = _FakePlayer(mounted=True, allies=[])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'to_hit': 9}, room_no=1)
        with patch('combat.engine.random.randint', return_value=1):
            redirected = await session._try_redirect_to_mount(ctx)
        self.assertFalse(redirected)

    async def test_no_redirect_when_not_mounted(self):
        player = _FakePlayer(mounted=False, allies=[_make_mount(name='SILVER')])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'to_hit': 9}, room_no=1)
        with patch('combat.engine.random.randint', return_value=1):
            redirected = await session._try_redirect_to_mount(ctx)
        self.assertFalse(redirected)


if __name__ == '__main__':
    unittest.main()
