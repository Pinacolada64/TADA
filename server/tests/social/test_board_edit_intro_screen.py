"""tests/social/test_board_edit_intro_screen.py

Coverage for commands/board/edit.py's _edit_intro_screen() itself -- the
editor-selection logic behind the '[I]ntro' option in _sig_detail()/
_board_detail() (see test_board_edit.py for the menu-dispatch wiring:
that it's reachable at all and gets the right path/subject).
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from commands.board.edit import _edit_intro_screen
from network_context import PETSCIINetworkContext
from petscii_editor import store as canvas_store


def _petscii_ctx():
    ctx = PETSCIINetworkContext.__new__(PETSCIINetworkContext)
    ctx.player = MagicMock()
    ctx.send = AsyncMock()
    return ctx


def _plain_ctx():
    ctx = MagicMock()  # not a PETSCIINetworkContext instance
    ctx.send = AsyncMock()
    return ctx


class TestEditIntroScreenDispatch(unittest.IsolatedAsyncioTestCase):

    async def test_petscii_connection_uses_canvas_streaming(self):
        ctx = _petscii_ctx()
        path = Path('run') / 'server' / 'board_intros' / '__unused.canvas'
        with patch('commands.board.edit.stream_canvas_edit', new=AsyncMock()) as mock_stream:
            await _edit_intro_screen(ctx, path, subject='the Test board')
        mock_stream.assert_awaited_once()
        (called_ctx, called_path), kwargs = mock_stream.call_args
        self.assertIs(called_ctx, ctx)
        self.assertEqual(called_path, path)
        self.assertIn('the Test board', kwargs['opening_msg'])

    async def test_non_petscii_connection_uses_text_editor_and_saves_tokenized(self):
        ctx = _plain_ctx()
        path = Path('run') / 'server' / 'board_intros' / '__test_edit_intro.canvas'
        path.unlink(missing_ok=True)
        try:
            with patch('commands.board.edit.run_editor', new=AsyncMock(
                    return_value=[{'text': 'Hello!'}, {'text': 'Welcome.'}])) as mock_run:
                await _edit_intro_screen(ctx, path, subject='the Test board')
            mock_run.assert_awaited_once()
            saved = canvas_store.load(path)
            self.assertEqual(saved, ['Hello!', 'Welcome.'])
            ctx.send.assert_any_call('Intro screen for the Test board saved.')
        finally:
            path.unlink(missing_ok=True)

    async def test_non_petscii_cancel_does_not_save(self):
        ctx = _plain_ctx()
        path = Path('run') / 'server' / 'board_intros' / '__test_edit_intro_cancel.canvas'
        path.unlink(missing_ok=True)
        with patch('commands.board.edit.run_editor', new=AsyncMock(return_value=None)):
            await _edit_intro_screen(ctx, path, subject='the Test board')
        self.assertFalse(path.exists())
        ctx.send.assert_any_call('Cancelled.')


if __name__ == '__main__':
    unittest.main()
