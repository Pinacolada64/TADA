"""tests/combat/test_lurk.py — LURK command port, combat/lurk.py
(SPUR.COMBAT.S:82-96, 247-262, 324-341, p.attack/lurk.a/m.a1): requires a
living ally, costs Honor, and either fires over the ally's head (loaded
ammo weapon, not LIGHT-named) or skips the player's swing entirely and
lurks behind the allies (melee weapon, empty ammo weapon, or a
LIGHT-named weapon like LIGHT SABRE). While lurking, the monster's
counter-attack is forced onto a living ally instead of the player.

Coverage:
  - lurk.has_living_ally(): counts party allies with hp>0 and non-DEAD/
    UNCONSCIOUS status; empty/absent party or all-dead/unconscious party
    both count as no allies
  - lurk.resolve_swing(): Honor cost formula (base 2, +1 Assassin, +1
    hp>20, -1 hp<10, -1 more hp<5, -1 if not firing); Honor floor (SPUR
    "if vk>p2" -- no deduction if Honor <= cost); fire-over-the-head vs
    lurk-behind-allies message and return value for: melee weapon,
    loaded ammo weapon, empty ammo weapon, LIGHT-named weapon
  - lurk.try_redirect_to_ally(): picks a random living ally to take the
    monster's hit instead of the player, applies the same damage to the
    ally's hit_points, and kills the ally if it drops to 0; no-op when
    the swing missed, dealt no damage, or no living ally remains
  - player_attacks(is_lurking=True) still applies the -2 to-hit/damage
    penalty and disables the "ease of use helps" fast path (already
    stubbed in combat/resolution.py; sanity-checked here for the LURK
    entry point specifically)
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from bar.ally_data import Ally, AllyStatus
from base_classes import PlayerClass, PlayerStat
from combat import lurk
from combat.engine import CombatSession
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

    async def send_room(self, msg, **kwargs):
        pass

    def sent(self) -> str:
        return '\n'.join(self._sent)


# ---------------------------------------------------------------------------
# lurk.has_living_ally()
# ---------------------------------------------------------------------------

class TestHasLivingAlly(unittest.TestCase):
    def test_no_party_has_no_ally(self):
        self.assertFalse(lurk.has_living_ally(_FakePlayer()))

    def test_empty_party_has_no_ally(self):
        self.assertFalse(lurk.has_living_ally(_FakePlayer(allies=[])))

    def test_living_servant_counts(self):
        player = _FakePlayer(allies=[_make_ally()])
        self.assertTrue(lurk.has_living_ally(player))

    def test_dead_ally_does_not_count(self):
        player = _FakePlayer(allies=[_make_ally(status=AllyStatus.DEAD, hit_points=0)])
        self.assertFalse(lurk.has_living_ally(player))

    def test_unconscious_ally_does_not_count(self):
        player = _FakePlayer(allies=[_make_ally(status=AllyStatus.UNCONSCIOUS)])
        self.assertFalse(lurk.has_living_ally(player))

    def test_zero_hp_servant_does_not_count(self):
        player = _FakePlayer(allies=[_make_ally(hit_points=0)])
        self.assertFalse(lurk.has_living_ally(player))

    def test_one_living_among_several_dead_counts(self):
        player = _FakePlayer(allies=[
            _make_ally(name='Fell', status=AllyStatus.DEAD, hit_points=0),
            _make_ally(name='Grok', hit_points=5),
        ])
        self.assertTrue(lurk.has_living_ally(player))


# ---------------------------------------------------------------------------
# lurk.resolve_swing()
# ---------------------------------------------------------------------------

class TestLurkResolve(unittest.IsolatedAsyncioTestCase):
    async def test_melee_weapon_lurks_behind_allies_no_fire(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.BASH_SLASH, name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=15)
        ctx = _FakeCtx(player)

        fires = await lurk.resolve_swing(ctx)

        self.assertFalse(fires)
        self.assertIn('You lurk behind your allies.', ctx.sent())

    async def test_loaded_ammo_weapon_fires_over_head(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.PROJECTILE, name='CROSSBOW')
        player = _FakePlayer(weapon=weapon, ammo_rounds=5, hit_points=15)
        ctx = _FakeCtx(player)

        fires = await lurk.resolve_swing(ctx)

        self.assertTrue(fires)
        self.assertIn("You fire over your ally's head..", ctx.sent())

    async def test_empty_ammo_weapon_lurks_behind_allies(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.PROJECTILE, name='CROSSBOW')
        player = _FakePlayer(weapon=weapon, ammo_rounds=0, hit_points=15)
        ctx = _FakeCtx(player)

        fires = await lurk.resolve_swing(ctx)

        self.assertFalse(fires)
        self.assertIn('You lurk behind your allies.', ctx.sent())

    async def test_light_named_weapon_never_fires_even_with_ammo(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.ENERGY, name='LIGHT SABRE')
        player = _FakePlayer(weapon=weapon, ammo_rounds=5, hit_points=15)
        ctx = _FakeCtx(player)

        fires = await lurk.resolve_swing(ctx)

        self.assertFalse(fires)
        self.assertIn('You lurk behind your allies.', ctx.sent())

    async def test_base_honor_cost_is_two(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=15, honor=1000)
        ctx = _FakeCtx(player)

        await lurk.resolve_swing(ctx)

        self.assertEqual(player.honor, 998)

    async def test_assassin_pays_three_honor(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=15, honor=1000,
                              char_class=PlayerClass.ASSASSIN)
        ctx = _FakeCtx(player)

        await lurk.resolve_swing(ctx)

        self.assertEqual(player.honor, 997)

    async def test_high_hp_costs_extra_honor(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=25, honor=1000)
        ctx = _FakeCtx(player)

        await lurk.resolve_swing(ctx)

        self.assertEqual(player.honor, 997)  # base 2 + 1 for hp>20

    async def test_low_hp_reduces_honor_cost(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=8, honor=1000)
        ctx = _FakeCtx(player)

        await lurk.resolve_swing(ctx)

        self.assertEqual(player.honor, 999)  # base 2 - 1 for hp<10

    async def test_very_low_hp_reduces_honor_cost_further(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=3, honor=1000)
        ctx = _FakeCtx(player)

        await lurk.resolve_swing(ctx)

        self.assertEqual(player.honor, 1000)  # base 2 -1 -1, floored at 0

    async def test_not_firing_costs_one_extra_honor(self):
        weapon = _FakeWeapon(weapon_class=WeaponClass.PROJECTILE, name='CROSSBOW')
        player = _FakePlayer(weapon=weapon, ammo_rounds=0, hit_points=15, honor=1000)
        ctx = _FakeCtx(player)

        await lurk.resolve_swing(ctx)

        self.assertEqual(player.honor, 999)  # base 2 - 1 for the not-firing penalty

    async def test_honor_at_or_below_cost_is_not_deducted(self):
        weapon = _FakeWeapon(name='LONG SWORD')
        player = _FakePlayer(weapon=weapon, hit_points=15, honor=2)
        ctx = _FakeCtx(player)

        await lurk.resolve_swing(ctx)

        self.assertEqual(player.honor, 2)  # SPUR: "if vk>p2" -- 2 is not > 2


# ---------------------------------------------------------------------------
# lurk.try_redirect_to_ally()
# ---------------------------------------------------------------------------

class _FakeMonsterHit:
    def __init__(self, hit=True, damage=5):
        self.hit = hit
        self.damage = damage


class TestTryRedirectToAlly(unittest.IsolatedAsyncioTestCase):
    async def test_no_op_on_a_miss(self):
        player = _FakePlayer(allies=[_make_ally(hit_points=10)])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        redirected = await lurk.try_redirect_to_ally(session, ctx, _FakeMonsterHit(hit=False, damage=5))

        self.assertFalse(redirected)

    async def test_no_op_on_zero_damage(self):
        player = _FakePlayer(allies=[_make_ally(hit_points=10)])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        redirected = await lurk.try_redirect_to_ally(session, ctx, _FakeMonsterHit(hit=True, damage=0))

        self.assertFalse(redirected)

    async def test_no_op_without_a_living_ally(self):
        player = _FakePlayer(allies=[])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        redirected = await lurk.try_redirect_to_ally(session, ctx, _FakeMonsterHit(hit=True, damage=5))

        self.assertFalse(redirected)

    async def test_redirect_damages_the_ally_instead_of_the_player(self):
        ally = _make_ally(hit_points=10)
        player = _FakePlayer(allies=[ally], hit_points=15)
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        redirected = await lurk.try_redirect_to_ally(session, ctx, _FakeMonsterHit(hit=True, damage=6))

        self.assertTrue(redirected)
        self.assertEqual(ally.hit_points, 4)
        self.assertEqual(player.hit_points, 15)  # player takes no damage
        self.assertIn(f'strikes {ally.name} instead!', ctx.sent())

    async def test_redirect_kills_the_ally_at_zero_hp(self):
        ally = _make_ally(hit_points=4)
        player = _FakePlayer(allies=[ally])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        await lurk.try_redirect_to_ally(session, ctx, _FakeMonsterHit(hit=True, damage=6))

        self.assertEqual(ally.hit_points, 0)
        self.assertEqual(ally.status, AllyStatus.DEAD)
        self.assertIn(f'{ally.name} is dead.', ctx.sent())

    async def test_dead_ally_never_targeted_only_the_living_one_is(self):
        dead = _make_ally(name='Fell', status=AllyStatus.DEAD, hit_points=0)
        alive = _make_ally(name='Grok', hit_points=10)
        player = _FakePlayer(allies=[dead, alive])
        ctx = _FakeCtx(player)
        session = CombatSession({'name': 'GOBLIN'}, room_no=1)

        await lurk.try_redirect_to_ally(session, ctx, _FakeMonsterHit(hit=True, damage=3))

        self.assertEqual(dead.hit_points, 0)
        self.assertEqual(alive.hit_points, 7)


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
