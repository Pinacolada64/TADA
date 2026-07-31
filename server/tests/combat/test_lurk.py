"""tests/combat/test_lurk.py — LURK command port (SPUR.COMBAT.S:82-96,
p.attack): requires a living ally, costs Honor, and either fires over the
ally's head (loaded ammo weapon, not LIGHT-named) or skips the player's
swing entirely and lurks behind the allies (melee weapon, empty ammo
weapon, or a LIGHT-named weapon like LIGHT SABRE).

Player-side mechanics only this pass -- redirecting the monster's counter
-attack onto an ally (SPUR.COMBAT.S:247-253, lurk.a) is a separate,
not-yet-ported piece; see MECHANICS.md.

Coverage:
  - _has_living_ally(): counts party allies with hp>0 and non-DEAD/
    UNCONSCIOUS status; empty/absent party or all-dead/unconscious party
    both count as no allies
  - CombatSession._lurk_resolve(): Honor cost formula (base 2, +1
    Assassin, +1 hp>20, -1 hp<10, -1 more hp<5, -1 if not firing);
    Honor floor (SPUR "if vk>p2" -- no deduction if Honor <= cost);
    fire-over-the-head vs lurk-behind-allies message and return value
    for: melee weapon, loaded ammo weapon, empty ammo weapon, LIGHT
    -named weapon
  - player_attacks(is_lurking=True) still applies the -2 to-hit/damage
    penalty and disables the "ease of use helps" fast path (already
    stubbed in combat/resolution.py; sanity-checked here for the LURK
    entry point specifically)
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from bar.ally_data import Ally, AllyFlags, AllyStatus
from base_classes import PlayerClass, PlayerStat
from combat.engine import CombatSession, _has_living_ally
from item_system import WeaponClass


class _FakeWeapon:
    def __init__(self, weapon_class=WeaponClass.BASH_SLASH, stability=50,
                 to_hit=50, name='Sword'):
        self.weapon_class = weapon_class
        self.stability = stability
        self.to_hit = to_hit
        self.name = name
        self.number = 1
        self.id_number = 1
        self.sound_effect = None


def _make_ally(name='Grok', status=AllyStatus.SERVANT, hit_points=10):
    a = Ally(name=name, gender='m', strength=10, to_hit=0, flags=[])
    a.status = status
    a.hit_points = hit_points
    return a


class _FakePlayer:
    def __init__(self, *, allies=None, hit_points=15, honor=1000,
                 char_class=None, weapon=None, ammo_rounds=0):
        self.name = 'Rulan'
        self.party = list(allies or [])
        self.hit_points = hit_points
        self.honor = honor
        self.char_class = char_class
        self.readied_weapon = weapon
        self.ammo_rounds = ammo_rounds
        self.stats = {PlayerStat.STR: 10, PlayerStat.CON: 10, PlayerStat.INT: 10,
                      PlayerStat.EGY: 10, PlayerStat.DEX: 10}


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

    def sent(self) -> str:
        return '\n'.join(self._sent)


def _run(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# _has_living_ally()
# ---------------------------------------------------------------------------

class TestHasLivingAlly(unittest.TestCase):
    def test_no_party_has_no_ally(self):
        self.assertFalse(_has_living_ally(_FakePlayer()))

    def test_empty_party_has_no_ally(self):
        self.assertFalse(_has_living_ally(_FakePlayer(allies=[])))

    def test_living_servant_counts(self):
        player = _FakePlayer(allies=[_make_ally()])
        self.assertTrue(_has_living_ally(player))

    def test_dead_ally_does_not_count(self):
        player = _FakePlayer(allies=[_make_ally(status=AllyStatus.DEAD, hit_points=0)])
        self.assertFalse(_has_living_ally(player))

    def test_unconscious_ally_does_not_count(self):
        player = _FakePlayer(allies=[_make_ally(status=AllyStatus.UNCONSCIOUS)])
        self.assertFalse(_has_living_ally(player))

    def test_zero_hp_servant_does_not_count(self):
        player = _FakePlayer(allies=[_make_ally(hit_points=0)])
        self.assertFalse(_has_living_ally(player))

    def test_one_living_among_several_dead_counts(self):
        player = _FakePlayer(allies=[
            _make_ally(name='Fell', status=AllyStatus.DEAD, hit_points=0),
            _make_ally(name='Grok', hit_points=5),
        ])
        self.assertTrue(_has_living_ally(player))


# ---------------------------------------------------------------------------
# CombatSession._lurk_resolve()
# ---------------------------------------------------------------------------

class TestLurkResolve(unittest.IsolatedAsyncioTestCase):
    async def test_melee_weapon_lurks_behind_allies_no_fire(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.BASH_SLASH, name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=15)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)

        fires = await session._lurk_resolve(ctx)

        self.assertFalse(fires)
        self.assertIn('You lurk behind your allies.', ctx.sent())

    async def test_loaded_ammo_weapon_fires_over_head(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.PROJECTILE, name='CROSSBOW')
        player = _FakePlayer(weapon=weapon, ammo_rounds=5, hit_points=15)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)

        fires = await session._lurk_resolve(ctx)

        self.assertTrue(fires)
        self.assertIn("You fire over your ally's head..", ctx.sent())

    async def test_empty_ammo_weapon_lurks_behind_allies(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.PROJECTILE, name='CROSSBOW')
        player = _FakePlayer(weapon=weapon, ammo_rounds=0, hit_points=15)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)

        fires = await session._lurk_resolve(ctx)

        self.assertFalse(fires)
        self.assertIn('You lurk behind your allies.', ctx.sent())

    async def test_light_named_weapon_never_fires_even_with_ammo(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.ENERGY, name='LIGHT SABRE')
        player = _FakePlayer(weapon=weapon, ammo_rounds=5, hit_points=15)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN', 'strength': 10}, room_no=1)

        fires = await session._lurk_resolve(ctx)

        self.assertFalse(fires)
        self.assertIn('You lurk behind your allies.', ctx.sent())

    async def test_base_honor_cost_is_two(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=15, honor=1000)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        await session._lurk_resolve(ctx)

        self.assertEqual(player.honor, 998)

    async def test_assassin_pays_three_honor(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=15, honor=1000,
                              char_class=PlayerClass.ASSASSIN)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        await session._lurk_resolve(ctx)

        self.assertEqual(player.honor, 997)

    async def test_high_hp_costs_extra_honor(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=25, honor=1000)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        await session._lurk_resolve(ctx)

        self.assertEqual(player.honor, 997)  # base 2 + 1 for hp>20

    async def test_low_hp_reduces_honor_cost(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=8, honor=1000)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        await session._lurk_resolve(ctx)

        self.assertEqual(player.honor, 999)  # base 2 - 1 for hp<10

    async def test_very_low_hp_reduces_honor_cost_further(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=3, honor=1000)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        await session._lurk_resolve(ctx)

        self.assertEqual(player.honor, 1000)  # base 2 -1 -1, floored at 0

    async def test_not_firing_costs_one_extra_honor(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.PROJECTILE, name='CROSSBOW')
        player = _FakePlayer(weapon=weapon, ammo_rounds=0, hit_points=15, honor=1000)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        await session._lurk_resolve(ctx)

        self.assertEqual(player.honor, 999)  # base 2 - 1 for the not-firing penalty

    async def test_honor_at_or_below_cost_is_not_deducted(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=15, honor=2)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        await session._lurk_resolve(ctx)

        self.assertEqual(player.honor, 2)  # SPUR: "if vk>p2" -- 2 is not > 2


# ---------------------------------------------------------------------------
# player_attacks(is_lurking=True) -- sanity check the LURK entry point
# reuses the already-stubbed to-hit/damage penalty.
# ---------------------------------------------------------------------------

class TestLurkAttackPenalty(unittest.TestCase):
    def test_lurking_disables_ease_of_use_fast_path(self):
        from combat.resolution import player_attacks
        weapon = _FakeWeapon(weapon_class=WeaponClass.BASH_SLASH, stability=90, to_hit=90)
        monster = {'name': 'GOBLIN', 'to_hit': 4, 'strength': 20}
        with patch('random.randint', return_value=10):
            result = player_attacks(_FakePlayer(), weapon, monster, is_lurking=True)
        self.assertFalse(result.ease_helped)


if __name__ == '__main__':
    unittest.main()
