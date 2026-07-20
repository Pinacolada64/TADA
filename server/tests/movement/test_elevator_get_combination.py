"""tests/movement/test_elevator_get_combination.py

Focused tests for shoppe.elevator.get_combination()'s non-interactive path
(provided_ans compared against the player's stored ELEVATOR combination).

Rewritten against the current ctx-based API (shoppe/elevator.py's
get_combination(ctx, *, is_interactive=False, provided_ans=None)) — the
previous version of this file called a stale reader/writer/player signature
that no longer exists.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from base_classes import Combination, CombinationTypes
from shoppe import elevator


def make_player_with_combo(tpl=(4, 5, 9)) -> MagicMock:
    player = MagicMock()
    combo = Combination(CombinationTypes.ELEVATOR)
    combo.combination = tpl
    player.combinations = {CombinationTypes.ELEVATOR: combo}
    return player


def make_ctx(player) -> MagicMock:
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    return ctx


def test_get_combination_noninteractive():
    player = make_player_with_combo((4, 5, 9))

    ctx_ok = make_ctx(player)
    ok = asyncio.run(elevator.get_combination(
        ctx_ok, is_interactive=False, provided_ans='4 5 9'))
    assert ok is True

    ctx_bad = make_ctx(player)
    bad = asyncio.run(elevator.get_combination(
        ctx_bad, is_interactive=False, provided_ans='1-2-3'))
    assert bad is False
