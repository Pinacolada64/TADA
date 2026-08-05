"""tests/ship/test_transporter.py

Covers ship/transporter.py -- the ship's transporter room (SPUR.SHIP.S
`elevator`/`elev.1`/`malfunction`). Reuses the dungeon elevator's own
combination (see shoppe/elevator.py) as the access code, beams the player
into another level's Merchant Shoppe on success, and relocates them to a
random level/room on malfunction.
"""
from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from base_classes import Combination, CombinationTypes, Map, Room
from flags import PlayerFlags
from player import Player
from ship.transporter import main as transporter_main


def _new_player(name: str) -> Player:
    player = Player(name=name)
    player.clear_flag(PlayerFlags.DEBUG_MODE)
    return player


class _FakeClient:
    def __init__(self, room=1):
        self.room = room
        self.virtual_location = None
        self.map_level = 1


class _FakeCtx:
    def __init__(self, responses, player, game_map=None):
        self._q = list(responses)
        self.sent: list = []
        self.player = player
        self.client = _FakeClient()
        self.server = SimpleNamespace(
            clients={}, items=[], game_map=game_map,
            _show_room=AsyncMock(), _teleport_to=AsyncMock(),
        )

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


def _grant_elevator_combo(player, tpl=(4, 5, 9)) -> str:
    """Simulates having READ the scrap of paper (item #69) -- see
    player.py's set_up_combinations(), which deliberately omits ELEVATOR
    until then. Returns the code as a prompt-ready string."""
    combo = Combination(CombinationTypes.ELEVATOR)
    combo.combination = tpl
    player.combinations[CombinationTypes.ELEVATOR] = combo
    return '-'.join(str(d) for d in tpl)


class _IsolatedBattleLog(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        import net_common
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = net_common.run_server_dir
        net_common.run_server_dir = self._tmp.name

    def tearDown(self):
        import net_common
        net_common.run_server_dir = self._orig
        self._tmp.cleanup()


class TestTransporterAccessCode(_IsolatedBattleLog):
    async def test_no_combination_refuses(self):
        player = _new_player('Rulan')
        player.combinations = {}
        ctx = _FakeCtx([], player)
        result = await transporter_main(ctx)
        self.assertFalse(result)
        self.assertIn('The transporter panel is dark -- you have no access code.', ctx._flat())

    async def test_wrong_code_retries_then_cancel(self):
        player = _new_player('Rulan')
        _grant_elevator_combo(player, tpl=(4, 5, 9))
        ctx = _FakeCtx(['9-9-9', ''], player)
        result = await transporter_main(ctx)
        self.assertFalse(result)
        self.assertIn('Wrong!', ctx._flat())


class TestTransporterBeamDown(_IsolatedBattleLog):
    async def test_successful_beam_down_enters_target_shop(self):
        player = _new_player('Rulan')
        code = _grant_elevator_combo(player)
        # code, level 3, then the target shop's own prompt returns None (leaves immediately)
        ctx = _FakeCtx([code, '3', None], player)
        with patch('random.randint', return_value=50):  # well above malfunction threshold
            result = await transporter_main(ctx)
        self.assertTrue(result)
        self.assertEqual(player.map_level, 3)
        ctx.server._show_room.assert_awaited()
        self.assertIn('Standby to beam down!', ctx._flat())

    async def test_bad_level_choice_stays_on_ship(self):
        player = _new_player('Rulan')
        code = _grant_elevator_combo(player)
        ctx = _FakeCtx([code, '9'], player)
        result = await transporter_main(ctx)
        self.assertFalse(result)
        self.assertIn("It don't go there!", ctx._flat())

    async def test_repeat_use_worsens_malfunction_odds(self):
        # SPUR: xz=xz-20 once TR+ is set -- this narrows the safety margin,
        # it does not widen it, despite TODO.md's stale "20 points better" note.
        player = _new_player('Rulan')
        player.once_per_day.append('ship_transporter_used')
        code = _grant_elevator_combo(player)
        ctx = _FakeCtx([code, '2'], player, game_map=None)
        with patch('random.randint', return_value=25):  # 25-20=5 < 10 -> malfunction
            result = await transporter_main(ctx)
        self.assertTrue(result)
        ctx.server._teleport_to.assert_awaited()


class TestTransporterMalfunction(_IsolatedBattleLog):
    async def test_malfunction_teleports_to_random_level_and_room(self):
        player = _new_player('Rulan')
        code = _grant_elevator_combo(player)
        game_map = Map()
        game_map.levels[4] = {7: Room(number=7, name='Somewhere', desc='', exits={})}
        ctx = _FakeCtx([code, '2'], player, game_map=game_map)
        with patch('random.randint', side_effect=[5, 4]):  # roll<10 -> malfunction; target_level=4
            result = await transporter_main(ctx)
        self.assertTrue(result)
        ctx.server._teleport_to.assert_awaited_once_with(ctx, 4, 7)
        self.assertIn('*** MALFUNCTION ***', ctx._flat())


if __name__ == '__main__':
    unittest.main()
