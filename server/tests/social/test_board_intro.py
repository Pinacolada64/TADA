"""tests/social/test_board_intro.py

Coverage for board/intro.py's path helpers and commands/board/board.py's
_show_intro_screen() -- the "shown once on entering a SIG/board" half of
the intro-screen feature (editing is covered in test_board_edit.py).
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from board.intro import board_intro_path, sig_intro_path
from commands.board.board import _show_intro_screen
from petscii_editor import store as canvas_store


class TestIntroPaths(unittest.TestCase):

    def test_sig_and_board_paths_differ_and_are_id_keyed(self):
        self.assertNotEqual(sig_intro_path(1), board_intro_path(1))
        self.assertNotEqual(sig_intro_path(1), sig_intro_path(2))
        self.assertIn('sig-1', str(sig_intro_path(1)))
        self.assertIn('board-3', str(board_intro_path(3)))


def _fake_ctx(is_expert: bool):
    ctx = MagicMock()
    ctx.player.is_expert = is_expert
    ctx.send = AsyncMock()
    return ctx


class TestShowIntroScreen(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.path = Path('run') / 'server' / 'board_intros' / '__test_show_intro.canvas'
        self.path.unlink(missing_ok=True)

    def tearDown(self):
        self.path.unlink(missing_ok=True)

    async def test_missing_file_sends_nothing(self):
        ctx = _fake_ctx(is_expert=False)
        await _show_intro_screen(ctx, self.path)
        ctx.send.assert_not_called()

    async def test_expert_player_skips_even_if_a_screen_exists(self):
        canvas_store.save_tokenized(self.path, ['Welcome!'])
        ctx = _fake_ctx(is_expert=True)
        await _show_intro_screen(ctx, self.path)
        ctx.send.assert_not_called()

    async def test_non_expert_sees_saved_screen(self):
        canvas_store.save_tokenized(self.path, ['Welcome!', 'Enjoy your stay.'])
        ctx = _fake_ctx(is_expert=False)
        await _show_intro_screen(ctx, self.path)
        ctx.send.assert_called_once()
        (lines,), _ = ctx.send.call_args
        self.assertEqual(lines, ['Welcome!', 'Enjoy your stay.'])


if __name__ == '__main__':
    unittest.main()
