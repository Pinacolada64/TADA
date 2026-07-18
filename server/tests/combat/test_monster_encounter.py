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


if __name__ == '__main__':
    unittest.main()
