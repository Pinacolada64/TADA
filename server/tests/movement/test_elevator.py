"""tests/movement/test_elevator.py

Tests for shoppe.elevator.get_combination()'s non-interactive combination
check, plus an end-to-end check that a valid combination entered
interactively lets a player reach the elevator's level menu.

Rewritten against the current ctx-based API (shoppe/elevator.py's
get_combination(ctx, *, is_interactive=False, provided_ans=None) and
_elevator_session(ctx, player)) — the previous version of this file called
a stale reader/writer/player signature and a module-level execute() that
never existed on this module. See tests/movement/test_elevator_session.py
for the fuller ctx-based elevator-session test suite this one complements.
"""
import asyncio

from base_classes import Combination, CombinationTypes
from player import Player
from shoppe import elevator


class FakeCtx:
    """Minimal GameContext-style stub: records ctx.send() output, feeds
    ctx.prompt() from a scripted list of responses."""

    def __init__(self, player, prompts=None):
        self.player = player
        self.sent = []
        self._prompts = iter(prompts or [])
        self.client = type('C', (), {})()
        self.server = type('S', (), {'clients': {}})()

    async def send(self, *args):
        for a in args:
            if isinstance(a, (list, tuple)):
                self.sent.extend(str(x) for x in a)
            else:
                self.sent.append(str(a))

    async def prompt(self, *args, **kwargs):
        return next(self._prompts, None)


def make_player_with_combo(tpl=(1, 2, 3)) -> Player:
    p = Player(name='TestPlayer')
    comb = Combination(CombinationTypes.ELEVATOR)
    comb.combination = tpl
    p.combinations = {CombinationTypes.ELEVATOR: comb}
    return p


def run_coro(coro):
    return asyncio.run(coro)


def test_get_combination_accepts_valid_provided():
    player = make_player_with_combo((1, 2, 3))
    ctx = FakeCtx(player)

    res = run_coro(elevator.get_combination(
        ctx, is_interactive=False, provided_ans='1-2-3'))
    assert res is True
    # ensure no 'not the right combination' error was sent
    assert "not the right combination" not in '\n'.join(ctx.sent)


def test_get_combination_rejects_invalid_provided():
    player = make_player_with_combo((1, 2, 3))
    ctx = FakeCtx(player)

    res = run_coro(elevator.get_combination(
        ctx, is_interactive=False, provided_ans='9-9-9'))
    assert res is False
    assert "not the right combination" in '\n'.join(ctx.sent)


def test_execute_with_provided_combination_returns_success():
    """End-to-end check: entering the correct combination interactively lets
    the player reach the elevator's level menu (rather than being turned
    away by the guard)."""
    player = make_player_with_combo((1, 2, 3))
    player.map_level = 1
    # '1-2-3' answers the combination prompt; 'l' leaves the level menu.
    ctx = FakeCtx(player, prompts=['1-2-3', 'l'])

    run_coro(elevator._elevator_session(ctx, player))
    joined = '\n'.join(ctx.sent)
    assert "not the right combination" not in joined
    assert "can't let you use the elevator" not in joined
    # reached the level menu and left normally
    assert "steps aside" in joined
