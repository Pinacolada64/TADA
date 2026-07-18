"""tests/combat/test_monster_encounter.py — encounters/monster.py's turf-guard
check (SPUR.MISC4.S:79-83): guild members are saluted by their own guild's
guard monster instead of being surprised/charmed/encountering it normally.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import Guild


def _make_monster(number, name='GUARD'):
    return {
        'number': number,
        'name': name,
        'flags': {'tough': False, 'charmable': False, 'mechanical': False},
        'size': 'man_sized',
        'to_hit': 4,
        'strength': 10,
    }


def _make_ctx(guild=Guild.CIVILIAN, room_no=2, monster_no=67):
    ctx = MagicMock()
    ctx.client.room = room_no
    ctx.player = MagicMock()
    ctx.player.name = 'Testerson'
    ctx.player.guild = guild
    ctx.player.map_level = 1
    ctx.player.monsters_killed = []
    ctx.player.charmed_monsters = []
    ctx.server.active_combats = {}

    room = MagicMock()
    room.monster = monster_no
    game_map = MagicMock()
    game_map.get_room.return_value = room
    ctx.server.game_map = game_map

    ctx.server.monsters = [_make_monster(monster_no)]
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    return ctx


class TestTryTurfGuard(unittest.IsolatedAsyncioTestCase):
    async def test_ignores_non_guard_monster_numbers(self):
        from encounters.monster import _try_turf_guard
        ctx = _make_ctx(guild=Guild.CLAW, monster_no=99)
        result = await _try_turf_guard(ctx, 99)
        self.assertFalse(result)
        ctx.send.assert_not_called()

    async def test_claw_guard_salutes_claw_member(self):
        from encounters.monster import _try_turf_guard
        ctx = _make_ctx(guild=Guild.CLAW, monster_no=67)
        result = await _try_turf_guard(ctx, 67)
        self.assertTrue(result)
        ctx.send.assert_any_await('You meet one of your guards.')
        ctx.send.assert_any_await('He salutes smartly!')

    async def test_sword_guard_ignores_claw_member(self):
        from encounters.monster import _try_turf_guard
        ctx = _make_ctx(guild=Guild.CLAW, monster_no=66)
        result = await _try_turf_guard(ctx, 66)
        self.assertFalse(result)
        ctx.send.assert_not_called()

    async def test_fist_guard_salutes_fist_member(self):
        from encounters.monster import _try_turf_guard
        ctx = _make_ctx(guild=Guild.FIST, monster_no=65)
        result = await _try_turf_guard(ctx, 65)
        self.assertTrue(result)

    async def test_civilian_not_saluted_by_any_guard(self):
        from encounters.monster import _try_turf_guard
        for number in (65, 66, 67):
            ctx = _make_ctx(guild=Guild.CIVILIAN, monster_no=number)
            result = await _try_turf_guard(ctx, number)
            self.assertFalse(result)


class TestTryMonsterEncounterTurfGuardRouting(unittest.IsolatedAsyncioTestCase):
    async def test_turf_guard_short_circuits_surprise_and_charm(self):
        from encounters.monster import try_monster_encounter
        ctx = _make_ctx(guild=Guild.CLAW, monster_no=67)
        with patch('encounters.monster._try_surprise') as mock_surprise, \
             patch('encounters.monster._try_spontaneous_charm') as mock_charm, \
             patch('encounters.monster._try_ally_tactical') as mock_tactical:
            await try_monster_encounter(ctx, level=1, room_no=2)
        mock_surprise.assert_not_called()
        mock_charm.assert_not_called()
        mock_tactical.assert_not_called()
        ctx.send.assert_any_await('You meet one of your guards.')


def _make_shadow_ctx(room_flags=(), prompt_reply='Y'):
    ctx = MagicMock()
    ctx.player.name = 'Testerson'
    ctx.player.honor = 1000
    ctx.player.party = MagicMock()
    ctx.player.party.add = AsyncMock()
    ctx.client.room = 2

    room = MagicMock()
    room.flags = list(room_flags)
    game_map = MagicMock()
    game_map.get_room.return_value = room
    ctx.server.game_map = game_map

    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.prompt = AsyncMock(return_value=prompt_reply)
    return ctx


def _make_candidate(name='ROBIN HOOD', strength=14):
    from bar.ally_data import Ally
    return Ally(name=name, gender='m', strength=strength, to_hit=8)


class TestTryShadowAlly(unittest.IsolatedAsyncioTestCase):
    async def test_water_room_is_safe(self):
        from encounters.monster import try_shadow_ally
        ctx = _make_shadow_ctx(room_flags=['water'])
        with patch('random.randint') as mock_roll:
            await try_shadow_ally(ctx)
        mock_roll.assert_not_called()
        ctx.send.assert_not_called()

    async def test_roll_miss_is_a_no_op(self):
        from encounters.monster import try_shadow_ally
        ctx = _make_shadow_ctx()
        with patch('random.randint', return_value=3):
            await try_shadow_ally(ctx)
        ctx.send.assert_not_called()

    async def test_missing_party_attribute_is_a_no_op(self):
        from encounters.monster import try_shadow_ally
        ctx = _make_shadow_ctx()
        del ctx.player.party
        with patch('random.randint', return_value=10):
            await try_shadow_ally(ctx)
        ctx.send.assert_not_called()

    async def test_no_free_candidates_sends_ambient_line(self):
        from encounters.monster import try_shadow_ally
        ctx = _make_shadow_ctx()
        with patch('random.randint', return_value=10), \
             patch('bar.ally_data.load_allies', return_value=[]):
            await try_shadow_ally(ctx)
        ctx.send.assert_awaited_once()
        ctx.player.party.add.assert_not_called()

    async def test_full_party_sends_ambient_line(self):
        from encounters.monster import try_shadow_ally
        ctx = _make_shadow_ctx()
        candidate = _make_candidate()
        with patch('random.randint', return_value=10), \
             patch('bar.ally_data.load_allies', return_value=[candidate]), \
             patch('bar.allies.owned_allies', return_value=[1, 2, 3]):
            await try_shadow_ally(ctx)
        ctx.send.assert_awaited_once()
        ctx.player.party.add.assert_not_called()

    async def test_accept_joins_party_and_logs(self):
        from encounters.monster import try_shadow_ally
        from bar.ally_data import AllyStatus
        ctx = _make_shadow_ctx(prompt_reply='Y')
        candidate = _make_candidate(name='ROBIN HOOD', strength=14)
        with patch('random.randint', return_value=10), \
             patch('bar.ally_data.load_allies', return_value=[candidate]), \
             patch('bar.ally_data.save_ally_roster') as mock_save, \
             patch('bar.allies.owned_allies', return_value=[]), \
             patch('net_common.append_battle_log') as mock_log:
            await try_shadow_ally(ctx)
        self.assertEqual(candidate.status, AllyStatus.SERVANT)
        self.assertEqual(candidate.owner, 'Testerson')
        self.assertEqual(candidate.hit_points, 14 * 2)
        ctx.player.party.add.assert_awaited_once_with(ctx, ctx.player, candidate)
        mock_save.assert_called_once()
        mock_log.assert_called_once()

    async def test_decline_reduces_honor_and_leaves_free(self):
        from encounters.monster import try_shadow_ally
        from bar.ally_data import AllyStatus
        ctx = _make_shadow_ctx(prompt_reply='N')
        ctx.player.honor = 1000
        candidate = _make_candidate()
        with patch('random.randint', return_value=10), \
             patch('bar.ally_data.load_allies', return_value=[candidate]), \
             patch('bar.allies.owned_allies', return_value=[]):
            await try_shadow_ally(ctx)
        self.assertEqual(candidate.status, AllyStatus.FREE)
        self.assertEqual(ctx.player.honor, 995)
        ctx.player.party.add.assert_not_called()


if __name__ == '__main__':
    unittest.main()
