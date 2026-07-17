"""tests/test_combat_menu_options.py

Unit tests for CombatSession._run_loop()'s per-round player prompt
(combat/engine.py):

  - Regression: the prompt used to claim "Enter/Return: Exit this menu"
    but blank input actually fell through to the attack branch
    (`cmd = (raw.strip().lower() or 'a')[0]`) -- the label was added in a
    previous session without changing the underlying behavior. Fixed by
    relabeling blank/Enter as the real default ("(Enter: Attack)") and
    adding a genuine e[X]it option: skips the round entirely (no attack,
    no flee roll), distinct from [F]lee.
  - New: [R]eady lets the player switch weapons mid-fight by delegating
    to commands.ready.ReadyCommand, without ending their turn.
  - The option list moved from the prompt_text (which overflowed narrow
    screens once [R]eady/e[X]it were added) into preamble_lines.

Run with:
    python -m pytest tests/test_combat_menu_options.py -v
"""
from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

nc_stub = types.ModuleType('network_context')
nc_stub.GameContext = object
sys.modules.setdefault('network_context', nc_stub)

from combat.engine import CombatSession
from flags import PlayerFlags


class _FakePlayer:
    def __init__(self):
        self.name = 'Rulan'
        self.hit_points = 20
        self.stats = {}
        self.readied_weapon = None
        self.unsaved_changes = False
        self.return_key = 'Enter'
        self._flags = {}

    def query_flag(self, flag):
        return bool(self._flags.get(flag, False))


def _make_session_and_ctx(responses):
    monster = {'name': 'Troll', 'hit_points': 30, 'to_hit': 4}
    session = CombatSession(monster, room_no=1)

    player = _FakePlayer()
    ctx = MagicMock()
    ctx.player = player
    ctx.send = AsyncMock()
    ctx.send_room = AsyncMock()

    it = iter(responses)
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))

    # Neutralize everything before the per-round prompt so only the
    # dispatch logic under test actually runs.
    session._try_class_tame = AsyncMock(return_value=False)
    session._check_crystal_pendant = AsyncMock(return_value=None)
    session._check_tactical_ambush = AsyncMock(return_value=None)

    return session, ctx


class TestCombatMenuOptions(unittest.IsolatedAsyncioTestCase):

    async def test_blank_enter_defaults_to_attack_not_exit(self):
        """Regression: blank input must still reach the attack branch --
        it must NOT be treated as a no-op 'exit' despite what the old
        (wrong) label claimed."""
        session, ctx = _make_session_and_ctx([''])
        session.flee = AsyncMock(return_value=True)
        session._swing = MagicMock(side_effect=RuntimeError('swing-reached'))

        with self.assertRaises(RuntimeError):
            await session._run_loop(ctx)

        session.flee.assert_not_awaited()

    async def test_explicit_attack_key_also_reaches_swing(self):
        session, ctx = _make_session_and_ctx(['a'])
        session._swing = MagicMock(side_effect=RuntimeError('swing-reached'))

        with self.assertRaises(RuntimeError):
            await session._run_loop(ctx)

    async def test_exit_key_skips_turn_without_fleeing_or_attacking(self):
        """e[X]it just exits this round's menu -- no attack, no flee roll."""
        session, ctx = _make_session_and_ctx(['x', None])
        session.flee = AsyncMock(return_value=True)
        session._swing = MagicMock(side_effect=RuntimeError('should not attack'))

        await session._run_loop(ctx)  # ends via the second prompt returning None

        session.flee.assert_not_awaited()

    async def test_flee_key_still_works(self):
        session, ctx = _make_session_and_ctx(['f'])
        session.flee = AsyncMock(return_value=True)

        await session._run_loop(ctx)

        session.flee.assert_awaited_once()

    async def test_ready_key_delegates_to_ready_command_without_attacking(self):
        session, ctx = _make_session_and_ctx(['r', None])
        session._swing = MagicMock(side_effect=RuntimeError('should not attack'))

        with patch('commands.ready.ReadyCommand') as MockReady:
            MockReady.return_value.execute = AsyncMock(return_value=None)
            await session._run_loop(ctx)
            MockReady.return_value.execute.assert_awaited_once_with(ctx)

    async def test_prompt_options_moved_to_preamble_not_prompt_text(self):
        """The option list overflowed narrow screens as part of the prompt
        line -- it must live in preamble_lines, with a short prompt_text."""
        session, ctx = _make_session_and_ctx(['x'])
        session.flee = AsyncMock(return_value=True)

        await session._run_loop(ctx)

        (prompt_text,), kwargs = ctx.prompt.await_args_list[0]
        preamble = '\n'.join(kwargs.get('preamble_lines', []))
        self.assertLessEqual(len(prompt_text), 20)
        self.assertIn('[A]ttack', preamble)
        self.assertIn('[F]lee', preamble)
        self.assertIn('[R]eady', preamble)
        self.assertIn('e[X]it', preamble)


if __name__ == '__main__':
    unittest.main(verbosity=2)
