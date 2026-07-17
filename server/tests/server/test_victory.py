"""tests/test_victory.py — win/escape detection (victory.py), the
level-6 "Ladder Up" (room 117 "Shimmering Portal") win check.

SPUR.MISC7.S's win/win2/win5/nowin gates, ported: (1) Wraith King must be
dead, (2) victory_item_number carried if victory_type is item/both,
(3) victory_gold_amount in hand if victory_type is gold/both.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from base_classes import Map, PlayerMoneyTypes, Room
from commands.movement import MoveCommand
from flags import PlayerFlags
from victory import VictoryResult, evaluate_victory


class _FakeItem:
    def __init__(self, id_number):
        self.id_number = id_number


class _FakeEntry:
    def __init__(self, id_number):
        self.item = _FakeItem(id_number)


class _FakeInventory:
    def __init__(self, item_ids):
        self._entries = [_FakeEntry(i) for i in item_ids]

    def entries(self, category=None):
        return self._entries


def _make_player(wraith_king_alive=True, silver_in_hand=0, item_ids=()):
    player = MagicMock()
    player.name = 'Testerson'
    player.query_flag = MagicMock(
        side_effect=lambda flag: wraith_king_alive if flag == PlayerFlags.WRAITH_KING_ALIVE else False
    )
    player.get_silver = MagicMock(
        side_effect=lambda kind: silver_in_hand if kind == PlayerMoneyTypes.IN_HAND else 0
    )
    player.inventory = _FakeInventory(item_ids)
    player.char_class = None
    player.char_race = None
    player.xp_level = 1
    return player


def _patched_config(**overrides):
    cfg = MagicMock()
    cfg.victory_type = overrides.get('victory_type', 'gold')
    cfg.victory_gold_amount = overrides.get('victory_gold_amount', 5000)
    cfg.victory_item_number = overrides.get('victory_item_number', 0)
    return cfg


class TestEvaluateVictoryWraithKingGate(unittest.TestCase):
    def test_wraith_king_alive_blocks_regardless_of_other_gates(self):
        player = _make_player(wraith_king_alive=True, silver_in_hand=999999)
        with patch('config.config', _patched_config(victory_type='gold', victory_gold_amount=100)):
            result = evaluate_victory(player)
        self.assertFalse(result.won)
        self.assertIn("King of the Wraiths", ' '.join(result.lines))

    def test_wraith_king_dead_and_gold_gate_met_wins(self):
        player = _make_player(wraith_king_alive=False, silver_in_hand=6000)
        with patch('config.config', _patched_config(victory_type='gold', victory_gold_amount=5000)):
            result = evaluate_victory(player)
        self.assertTrue(result.won)


class TestEvaluateVictoryGoldGate(unittest.TestCase):
    def test_insufficient_silver_fails(self):
        player = _make_player(wraith_king_alive=False, silver_in_hand=100)
        with patch('config.config', _patched_config(victory_type='gold', victory_gold_amount=5000)):
            result = evaluate_victory(player)
        self.assertFalse(result.won)

    def test_sufficient_silver_passes(self):
        player = _make_player(wraith_king_alive=False, silver_in_hand=5000)
        with patch('config.config', _patched_config(victory_type='gold', victory_gold_amount=5000)):
            result = evaluate_victory(player)
        self.assertTrue(result.won)


class TestEvaluateVictoryItemGate(unittest.TestCase):
    def test_missing_item_fails(self):
        player = _make_player(wraith_king_alive=False, item_ids=[])
        with patch('config.config', _patched_config(victory_type='item', victory_item_number=35)):
            result = evaluate_victory(player)
        self.assertFalse(result.won)

    def test_carrying_item_passes(self):
        player = _make_player(wraith_king_alive=False, item_ids=[35])
        with patch('config.config', _patched_config(victory_type='item', victory_item_number=35)):
            result = evaluate_victory(player)
        self.assertTrue(result.won)


class TestEvaluateVictoryBothGate(unittest.TestCase):
    def test_both_requires_item_and_gold(self):
        player = _make_player(wraith_king_alive=False, silver_in_hand=100, item_ids=[35])
        with patch('config.config', _patched_config(
                victory_type='both', victory_gold_amount=5000, victory_item_number=35)):
            result = evaluate_victory(player)
        self.assertFalse(result.won)

    def test_both_satisfied_wins(self):
        player = _make_player(wraith_king_alive=False, silver_in_hand=5000, item_ids=[35])
        with patch('config.config', _patched_config(
                victory_type='both', victory_gold_amount=5000, victory_item_number=35)):
            result = evaluate_victory(player)
        self.assertTrue(result.won)


def _make_map():
    m = Map()
    rooms = {
        117: Room(number=117, name='Shimmering Portal', desc='',
                  exits={'south': 1, 'rc': 1, 'rt': 1}),
    }
    m.levels[6] = rooms
    m.rooms = rooms
    return m


class TestMovementWinHook(unittest.IsolatedAsyncioTestCase):
    """MoveCommand.execute() intercepts 'up' at room 117/level 6 for the
    win check instead of falling through to the generic rc/rt same-level
    staircase (which would otherwise just walk the player to room rt=1)."""

    def _make_ctx(self):
        ctx = MagicMock()
        ctx.client.room = 117
        ctx.player.map_level = 6
        ctx.player.map_room = 117
        ctx.player.query_flag = MagicMock(return_value=False)
        ctx.send = AsyncMock()
        ctx.send_room = AsyncMock()
        ctx.server.game_map = _make_map()
        ctx.server._move = AsyncMock()
        return ctx

    async def test_win_check_intercepts_before_generic_rc_rt_move(self):
        ctx = self._make_ctx()
        with patch('victory.evaluate_victory', return_value=VictoryResult(True, ['won it'])), \
             patch('victory.declare_victory', return_value=['congrats']), \
             patch('commands.movement._enter_shoppe', new=AsyncMock()) as mock_shoppe:
            await MoveCommand().execute(ctx, 'u')
        mock_shoppe.assert_not_awaited()
        ctx.server._move.assert_not_awaited()
        ctx.send.assert_awaited()

    async def test_losing_gate_blocks_move_without_moving_player(self):
        ctx = self._make_ctx()
        with patch('victory.evaluate_victory', return_value=VictoryResult(False, ['nope'])), \
             patch('commands.movement._enter_shoppe', new=AsyncMock()) as mock_shoppe:
            await MoveCommand().execute(ctx, 'u')
        mock_shoppe.assert_not_awaited()
        ctx.server._move.assert_not_awaited()
        self.assertEqual(ctx.client.room, 117)


if __name__ == '__main__':
    unittest.main()
