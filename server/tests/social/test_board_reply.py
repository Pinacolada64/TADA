"""tests/social/test_board_reply.py

Unit tests for commands/board_reply.py -- the interactive, one-message-
at-a-time thread reader gated behind PlayerFlags.PROMPT_MODE.
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import board as board_store
from commands.board_reply import read_thread_interactive
from flags import PlayerFlags


def run(coro):
    return asyncio.run(coro)


class _FakePlayer:
    def __init__(self, name='alexa', admin=False):
        self.name = name
        self._admin = admin
        self.return_key = 'Enter'
        self.client_settings = MagicMock()
        self.client_settings.screen_columns = 80

    def query_flag(self, flag):
        if flag == PlayerFlags.ADMIN:
            return self._admin
        return False


def make_ctx(player=None, prompts=None):
    """side_effect is a callable (not a bare list) so exhausting the
    scripted responses cleanly yields None (simulating a disconnect)
    instead of a plain list's StopIteration -> RuntimeError under
    PEP 479 -- see tests/test_text_editor.py's _make_ctx for the same
    convention."""
    ctx = MagicMock()
    ctx.player = player or _FakePlayer()
    ctx.send = AsyncMock()
    it = iter(prompts or [])
    ctx.prompt = AsyncMock(side_effect=lambda *a, **kw: next(it, None))
    return ctx


def _sent_text(ctx) -> str:
    parts = []
    for call in ctx.send.await_args_list:
        for arg in call.args:
            if isinstance(arg, list):
                parts.extend(str(x) for x in arg)
            else:
                parts.append(str(arg))
    return '\n'.join(parts)


def _thread(**overrides):
    base = {
        'id': 1, 'title': 'Hello', 'author': 'bob', 'anonymous': False,
        'posted_at': '2026-01-01T00:00:00',
        'body': [{'text': 'root line one'}, {'text': 'root line two'}],
        'replies': [
            {'author': 'carol', 'anonymous': False, 'posted_at': '2026-01-02T00:00:00',
             'body': [{'text': 'reply one text'}]},
            {'author': 'dave', 'anonymous': False, 'posted_at': '2026-01-03T00:00:00',
             'body': [{'text': 'reply two text'}]},
        ],
    }
    base.update(overrides)
    return base


class TestSteppedNavigation(unittest.TestCase):
    def test_bare_enter_walks_through_every_message_then_stops(self):
        ctx = make_ctx(prompts=['', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        text = _sent_text(ctx)
        self.assertIn('root line one', text)
        self.assertIn('reply one text', text)
        self.assertIn('reply two text', text)
        self.assertEqual(ctx.prompt.await_count, 3)

    def test_jump_to_reply_number(self):
        ctx = make_ctx(prompts=['2', ''])
        run(read_thread_interactive(ctx, _thread()))
        text = _sent_text(ctx)
        self.assertIn('reply two text', text)

    def test_jump_to_invalid_reply_number_reports_error(self):
        ctx = make_ctx(prompts=['99', ''])
        run(read_thread_interactive(ctx, _thread()))
        self.assertIn('No reply #99', _sent_text(ctx))

    def test_disconnect_mid_read_stops_cleanly(self):
        ctx = make_ctx(prompts=[])
        run(read_thread_interactive(ctx, _thread()))  # should not raise
        self.assertEqual(ctx.prompt.await_count, 1)

    def test_unrecognized_choice_reports_error(self):
        ctx = make_ctx(prompts=['zzz', '', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        self.assertIn("Unrecognized choice 'zzz'", _sent_text(ctx))


class BoardReplyTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'board.json'
        patcher = patch.object(board_store, 'BOARD_FILE', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        board_store.save_board([_thread()], self.path)


class TestReplyWithQuote(BoardReplyTestCase):
    def test_quote_all_then_confirm_posts_reply_with_body(self):
        # At the root message: 'r' -> quote range 'all' -> confirm y ->
        # anonymous 'n' -> editor typed 'my reply' then '.s' to save.
        prompts = ['r', 'all', 'y', 'n', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertEqual(len(threads[0]['replies']), 3)  # 2 seeded + 1 new
        new_reply = threads[0]['replies'][-1]
        self.assertEqual(new_reply['author'], 'alexa')
        self.assertFalse(new_reply['anonymous'])
        self.assertIn('Quoting bob', _sent_text(ctx))
        self.assertIn('root line one', _sent_text(ctx))

    def test_no_quote_posts_reply_without_a_quote_box(self):
        prompts = ['r', 'n', 'n', 'unquoted reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertEqual(len(threads[0]['replies']), 3)
        self.assertNotIn('Quoting', _sent_text(ctx))

    def test_declining_the_preview_reprompts_for_a_range(self):
        # First offer '1' -> preview -> decline (blank) -> then 'all' -> confirm y.
        prompts = ['r', '1', '', 'all', 'y', 'n', 'ok', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertEqual(len(threads[0]['replies']), 3)

    def test_anonymous_reply(self):
        prompts = ['r', 'n', 'y', 'hi', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertTrue(threads[0]['replies'][-1]['anonymous'])
        self.assertEqual(threads[0]['replies'][-1]['author'], 'alexa')  # real name stored

    def test_disconnect_during_editor_does_not_post_a_reply(self):
        # 'r' -> no quote -> not anonymous -> then editor gets no more
        # input (disconnect), run_editor() returns None.
        prompts = ['r', 'n', 'n']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertEqual(len(threads[0]['replies']), 2)  # unchanged


class TestMailPoster(BoardReplyTestCase):
    def test_mail_delegates_to_page_command(self):
        with patch('commands.page.PageCommand') as MockPageCommand:
            instance = MockPageCommand.return_value
            instance.execute = AsyncMock()
            prompts = ['m', 'hey bob, nice post', '', '', '']
            ctx = make_ctx(prompts=prompts)
            run(read_thread_interactive(ctx, _thread()))
            instance.execute.assert_awaited_once_with(ctx, 'bob=hey bob, nice post')

    def test_mail_blocked_for_anonymous_post_and_non_privileged_viewer(self):
        thread = _thread()
        thread['anonymous'] = True
        ctx = make_ctx(prompts=['m', '', '', ''])
        run(read_thread_interactive(ctx, thread))
        self.assertIn('cannot mail', _sent_text(ctx))

    def test_mail_allowed_for_anonymous_post_when_viewer_is_admin(self):
        with patch('commands.page.PageCommand') as MockPageCommand:
            instance = MockPageCommand.return_value
            instance.execute = AsyncMock()
            thread = _thread()
            thread['anonymous'] = True
            ctx = make_ctx(player=_FakePlayer(admin=True), prompts=['m', 'hi', '', '', ''])
            run(read_thread_interactive(ctx, thread))
            instance.execute.assert_awaited_once_with(ctx, 'bob=hi')

    def test_blank_message_cancels_without_calling_page(self):
        with patch('commands.page.PageCommand') as MockPageCommand:
            ctx = make_ctx(prompts=['m', '', '', '', ''])
            run(read_thread_interactive(ctx, _thread()))
            MockPageCommand.assert_not_called()


if __name__ == '__main__':
    unittest.main()
