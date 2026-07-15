"""tests/combat/test_meteor.py — encounters/meteor.py: the "meteor" /
"flying banshee" random encounter (SPUR.MISC6.S).
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import Map, Room


def _make_map(room_flags=None, level=1):
    m = Map()
    rooms = {
        1: Room(number=1, name='Room One', desc='', exits={}, monster=0,
                flags=room_flags or []),
        2: Room(number=2, name='Room Two', desc='', exits={}, monster=5),
    }
    m.levels[level] = rooms
    if level == 1:
        m.rooms = rooms
    return m


def _make_player(seen=False, hit_points=30, stats=None, experience=0,
                  active_shield_id=None, shield_proficiency=None, armor=0):
    player = MagicMock()
    player.name = 'Testerson'
    player.once_per_day = ['meteor_seen'] if seen else []
    player.hit_points = hit_points
    player.experience = experience
    player.active_shield_id = active_shield_id
    player.shield_proficiency = shield_proficiency or {}
    player.armor = armor
    player.stats = stats or {
        'Strength': 20, 'Constitution': 10, 'Intelligence': 20,
        'Energy': 20, 'Wisdom': 10, 'Dexterity': 20,
    }
    return player


def _make_ctx(room_no=1, player=None, game_map=None, map_level=1):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player = player or _make_player()
    ctx.player.map_level = map_level
    ctx.server.game_map = game_map or _make_map()
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


class TestGating(unittest.IsolatedAsyncioTestCase):
    async def test_no_op_if_already_seen(self):
        from encounters.meteor import try_encounter
        ctx = _make_ctx(player=_make_player(seen=True))
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_no_op_if_room_has_monster(self):
        from encounters.meteor import try_encounter
        ctx = _make_ctx(room_no=2)
        with patch('random.uniform', return_value=0.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_no_op_when_roll_fails(self):
        from encounters.meteor import try_encounter
        ctx = _make_ctx()
        with patch('random.uniform', return_value=99.0):
            await try_encounter(ctx)
        ctx.send.assert_not_awaited()

    async def test_marks_seen_on_trigger(self):
        from encounters.meteor import try_encounter
        ctx = _make_ctx()
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        self.assertIn('meteor_seen', ctx.player.once_per_day)


class TestThreatName(unittest.IsolatedAsyncioTestCase):
    def _sent_text(self, ctx):
        out = []
        for call in ctx.send.await_args_list:
            for a in call.args:
                if isinstance(a, list):
                    out.extend(str(x) for x in a)
                else:
                    out.append(str(a))
        return ' '.join(out)

    async def test_flying_banshee_on_dry_land(self):
        from encounters.meteor import try_encounter
        ctx = _make_ctx()
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        self.assertIn('FLYING BANSHEE', self._sent_text(ctx))

    async def test_flying_banshee_in_water_below_level_6(self):
        from encounters.meteor import try_encounter
        game_map = _make_map(room_flags=['water'])
        ctx = _make_ctx(game_map=game_map, map_level=1)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        self.assertIn('FLYING BANSHEE', self._sent_text(ctx))

    async def test_meteor_only_in_vacuum_room_on_level_6(self):
        from encounters.meteor import try_encounter
        game_map = _make_map(room_flags=['water'], level=6)
        ctx = _make_ctx(game_map=game_map, map_level=6)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        self.assertIn('METEOR', self._sent_text(ctx))
        self.assertNotIn('FLYING BANSHEE', self._sent_text(ctx))

    async def test_dry_room_on_level_6_is_still_banshee(self):
        from encounters.meteor import try_encounter
        game_map = _make_map(room_flags=[], level=6)
        ctx = _make_ctx(game_map=game_map, map_level=6)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        self.assertIn('FLYING BANSHEE', self._sent_text(ctx))


class TestDodgeOutcome(unittest.IsolatedAsyncioTestCase):
    async def test_low_roll_dodges_and_gains_xp(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=30, experience=100)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        self.assertEqual(player.experience, 150)
        self.assertEqual(player.hit_points, 30)

    async def test_high_roll_halves_hp(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=30, experience=100)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=95):
            await try_encounter(ctx)
        self.assertEqual(player.hit_points, 15)
        self.assertEqual(player.experience, 100)  # no XP on a hit

    async def test_critically_low_hp_always_dodges(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=2)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=100):  # worst possible roll
            await try_encounter(ctx)
        self.assertEqual(player.hit_points, 2)  # untouched -- mercy rule

    async def test_low_stats_worsen_odds(self):
        from encounters.meteor import try_encounter
        player = _make_player(
            hit_points=30,
            stats={'Strength': 5, 'Constitution': 10, 'Intelligence': 5,
                   'Energy': 5, 'Wisdom': 10, 'Dexterity': 5},
        )
        ctx = _make_ctx(player=player)
        # Roll of 75 would normally dodge (< 90), but +10+5+5+5=25 penalty
        # from all four low stats pushes it to 100, which fails.
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=75):
            await try_encounter(ctx)
        self.assertEqual(player.hit_points, 15)


class TestLazerShieldBlockChance(unittest.TestCase):
    def test_no_shield_readied_is_zero(self):
        from encounters.meteor import _lazer_shield_block_chance
        player = _make_player(active_shield_id=None)
        self.assertEqual(_lazer_shield_block_chance(player), 0)

    def test_wrong_shield_readied_is_zero(self):
        from encounters.meteor import _lazer_shield_block_chance
        player = _make_player(active_shield_id=4)  # small shield
        self.assertEqual(_lazer_shield_block_chance(player), 0)

    def test_green_tier(self):
        from encounters.meteor import _lazer_shield_block_chance
        player = _make_player(active_shield_id=116, shield_proficiency={'116': 10})
        self.assertEqual(_lazer_shield_block_chance(player), 33)

    def test_veteran_tier(self):
        from encounters.meteor import _lazer_shield_block_chance
        player = _make_player(active_shield_id=116, shield_proficiency={'116': 50})
        self.assertEqual(_lazer_shield_block_chance(player), 66)

    def test_elite_tier(self):
        from encounters.meteor import _lazer_shield_block_chance
        player = _make_player(active_shield_id=116, shield_proficiency={'116': 99})
        self.assertEqual(_lazer_shield_block_chance(player), 100)


class TestLazerShieldMitigation(unittest.IsolatedAsyncioTestCase):
    async def test_elite_shield_always_blocks_and_halves_damage_again(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=30, active_shield_id=116,
                               shield_proficiency={'116': 99})
        ctx = _make_ctx(player=player)
        # First randint = dodge roll (fails), second = block roll (succeeds).
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', side_effect=[95, 1]):
            await try_encounter(ctx)
        # base_damage = 30 // 2 = 15; shielded halves again -> 7; 30-7=23.
        self.assertEqual(player.hit_points, 23)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('YOUR LAZER SHIELD KICKS IN!', sent)

    async def test_green_shield_can_still_fail_to_block(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=30, active_shield_id=116,
                               shield_proficiency={'116': 0})
        ctx = _make_ctx(player=player)
        # Block roll of 100 always fails a 33% chance.
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', side_effect=[95, 100]):
            await try_encounter(ctx)
        self.assertEqual(player.hit_points, 15)  # full base damage, unmitigated
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn("didn't kick in fast enough", sent)

    async def test_no_shield_shows_spur_flavor_line(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=30)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=95):
            await try_encounter(ctx)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn("Too bad you didn't USE a LAZER SHIELD", sent)


class TestArmorDamageReduction(unittest.TestCase):
    def test_no_armor_is_zero(self):
        from encounters.meteor import _armor_damage_reduction_pct
        self.assertEqual(_armor_damage_reduction_pct(_make_player(armor=0)), 0)

    def test_normal_armor_passes_through(self):
        from encounters.meteor import _armor_damage_reduction_pct
        self.assertEqual(_armor_damage_reduction_pct(_make_player(armor=40)), 40)

    def test_power_armor_150_capped_at_100(self):
        from encounters.meteor import _armor_damage_reduction_pct
        self.assertEqual(_armor_damage_reduction_pct(_make_player(armor=150)), 100)


class TestArmorMitigation(unittest.IsolatedAsyncioTestCase):
    async def test_power_armor_fully_absorbs_damage(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=30, armor=150)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=95):
            await try_encounter(ctx)
        # base_damage = 15, armor caps at 100% -> fully absorbed, but a hit
        # always leaves at least 1 HP of impact (max(1, hp - damage) floor).
        self.assertEqual(player.hit_points, 30)
        sent = ' '.join(str(c) for call in ctx.send.await_args_list for c in call.args)
        self.assertIn('Your armor absorbs', sent)

    async def test_partial_armor_reduces_damage(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=30, armor=50)
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=95):
            await try_encounter(ctx)
        # base_damage=15, 50% absorbed (7) -> 8 damage -> 30-8=22.
        self.assertEqual(player.hit_points, 22)

    async def test_armor_and_shield_stack(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=30, armor=50, active_shield_id=116,
                               shield_proficiency={'116': 99})
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', side_effect=[95, 1]):  # dodge fails, shield blocks
            await try_encounter(ctx)
        # base_damage=15, shield halves -> 7, armor absorbs 50% of 7 (3) -> 4 -> 30-4=26.
        self.assertEqual(player.hit_points, 26)


class TestBystanderBroadcast(unittest.IsolatedAsyncioTestCase):
    def _room_text(self, ctx):
        return ' '.join(
            str(a) for call in ctx.send_room.await_args_list for a in call.args
        )

    async def test_dive_for_cover_broadcast(self):
        from encounters.meteor import try_encounter
        player = _make_player()
        player.name = 'Killerella'
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=1):
            await try_encounter(ctx)
        self.assertIn('Killerella dives for cover', self._room_text(ctx))
        for call in ctx.send_room.await_args_list:
            self.assertTrue(call.kwargs.get('exclude_self'))

    async def test_hit_broadcast_on_damage(self):
        from encounters.meteor import try_encounter
        player = _make_player(hit_points=30)
        player.name = 'Killerella'
        ctx = _make_ctx(player=player)
        with patch('random.uniform', return_value=0.0), \
             patch('random.randint', return_value=95):
            await try_encounter(ctx)
        self.assertIn('Killerella is struck hard', self._room_text(ctx))


if __name__ == '__main__':
    unittest.main()
