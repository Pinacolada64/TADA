"""tests/test_shield_proficiency.py

Unit tests for shield-block proficiency -- a new mechanic (not part of
original SPUR) added alongside the starting-equipment feature: every
successful shield block builds player.shield_proficiency, a dict keyed by
str(active_shield_id) mirroring weapon_experience's shape/cap exactly, which
then feeds a small bonus into the block-threshold roll (see
combat/resolution.py's shield_exp_bonus()).
"""
from __future__ import annotations

import types
import unittest

from combat.engine import CombatSession
from combat.resolution import shield_exp_bonus


class TestShieldExpBonus(unittest.TestCase):
    def test_green_tier_no_bonus(self):
        self.assertEqual(shield_exp_bonus(0), 0)
        self.assertEqual(shield_exp_bonus(39), 0)

    def test_veteran_tier_plus_one(self):
        self.assertEqual(shield_exp_bonus(40), 1)
        self.assertEqual(shield_exp_bonus(98), 1)

    def test_elite_tier_plus_two(self):
        self.assertEqual(shield_exp_bonus(99), 2)


class _FakePlayer:
    def __init__(self, active_shield_id=4):
        self.name = 'Rulan'
        self.hit_points = 30
        self.unsaved_changes = False
        self.shield = 50
        self.armor = 0
        self.experience = 100
        self.active_shield_id = active_shield_id
        self.shield_proficiency = {}

    def gain_shield_proficiency(self, shield_id_number) -> int:
        """Mirrors the real Player.gain_shield_proficiency (player.py)."""
        if shield_id_number is None:
            return 0
        key = str(shield_id_number)
        current = int(self.shield_proficiency.get(key, 0))
        if current < 99:
            self.shield_proficiency[key] = current + 1
            self.unsaved_changes = True
        return int(self.shield_proficiency.get(key, current))


class _FakeResult:
    hit = True
    damage = 3
    fire_damage = 0
    shield_blocked = 5
    shield_degraded = 2
    shield_destroyed = False
    armor_blocked = 0
    armor_degraded = 0
    armor_destroyed = False
    experience_drained = 0
    dex_lost = False
    strength_lost = False


class TestApplyMonsterDamageIncrementsProficiency(unittest.TestCase):
    def test_successful_block_increments_proficiency_for_active_shield(self):
        player = _FakePlayer(active_shield_id=4)
        ctx = types.SimpleNamespace(player=player)
        session = CombatSession.__new__(CombatSession)
        session._apply_monster_damage(ctx, _FakeResult())
        self.assertEqual(player.shield_proficiency, {'4': 1})

    def test_no_block_leaves_proficiency_unchanged(self):
        player = _FakePlayer(active_shield_id=4)
        ctx = types.SimpleNamespace(player=player)
        result = _FakeResult()
        result.shield_blocked = 0
        session = CombatSession.__new__(CombatSession)
        session._apply_monster_damage(ctx, result)
        self.assertEqual(player.shield_proficiency, {})

    def test_no_active_shield_id_is_a_noop(self):
        player = _FakePlayer(active_shield_id=None)
        ctx = types.SimpleNamespace(player=player)
        session = CombatSession.__new__(CombatSession)
        session._apply_monster_damage(ctx, _FakeResult())
        self.assertEqual(player.shield_proficiency, {})

    def test_different_shields_track_separately(self):
        player = _FakePlayer(active_shield_id=4)
        ctx = types.SimpleNamespace(player=player)
        session = CombatSession.__new__(CombatSession)
        session._apply_monster_damage(ctx, _FakeResult())
        player.active_shield_id = 114
        session._apply_monster_damage(ctx, _FakeResult())
        self.assertEqual(player.shield_proficiency, {'4': 1, '114': 1})


class TestGainShieldProficiencyCap(unittest.TestCase):
    def test_caps_at_99(self):
        player = _FakePlayer(active_shield_id=4)
        player.shield_proficiency = {'4': 99}
        self.assertEqual(player.gain_shield_proficiency(4), 99)

    def test_none_id_returns_zero(self):
        player = _FakePlayer(active_shield_id=None)
        self.assertEqual(player.gain_shield_proficiency(None), 0)


if __name__ == '__main__':
    unittest.main()
