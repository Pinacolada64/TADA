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


def _expected_header_line(label: str, value: str, position: int, width: int) -> str:
    """One line of board_store.MessageHeader.display()'s own output,
    computed instead of hand-counted -- see tests/social/test_board.py's
    _expected_header() for the full multi-line version this mirrors."""
    color = (board_store._HEADER_COLORS_BY_POSITION[position]
             if position < len(board_store._HEADER_COLORS_BY_POSITION)
             else board_store._HEADER_FALLBACK_COLOR)
    return f'|{color}|{label.rjust(width)}: {value}|reset|'


class _FakePlayer:
    def __init__(self, name='alexa', admin=False, expert=False, prompt_mode=True):
        self.name = name
        self._admin = admin
        self._expert = expert
        self._prompt_mode = prompt_mode
        self.return_key = 'Enter'
        self.client_settings = MagicMock()
        self.client_settings.screen_columns = 80
        self.unsaved_changes = False

    def query_flag(self, flag):
        if flag == PlayerFlags.ADMIN:
            return self._admin
        if flag == PlayerFlags.EXPERT_MODE:
            return self._expert
        if flag == PlayerFlags.PROMPT_MODE:
            return self._prompt_mode
        return False

    def toggle_flag(self, flag):
        if flag == PlayerFlags.PROMPT_MODE:
            self._prompt_mode = not self._prompt_mode
            return self._prompt_mode, None
        return False, None

    @property
    def is_expert(self) -> bool:
        return self._expert


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

    def test_only_the_root_header_shows_a_replies_line(self):
        ctx = make_ctx(prompts=['', '', ''])  # walk root, reply 1, reply 2
        run(read_thread_interactive(ctx, _thread()))
        text = _sent_text(ctx)
        self.assertEqual(text.count('Replies:'), 1)

    def test_from_and_date_are_separate_colorized_lines(self):
        ctx = make_ctx(prompts=[''])
        run(read_thread_interactive(ctx, _thread()))
        text = _sent_text(ctx)
        # _thread() seeds 2 replies -- the root header always shows its
        # own "Number: 1 of 3" (this message's position within the
        # thread: root + 2 replies), so fields are Number/From/Date/
        # Title/Replies, width = len('Replies') = 7.
        self.assertIn(_expected_header_line('Number', '1 of 3', 0, 7), text)
        self.assertIn(_expected_header_line('From', 'bob', 1, 7), text)
        self.assertIn(_expected_header_line('Date', '2026-01-01', 2, 7), text)
        self.assertIn(_expected_header_line('Title', 'Hello', 3, 7), text)
        self.assertIn(_expected_header_line('Replies', '2', 4, 7), text)
        self.assertNotIn('From: bob  (2026-01-01)', text)

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

    def test_q_quits_immediately_without_reading_the_rest(self):
        ctx = make_ctx(prompts=['q'])
        run(read_thread_interactive(ctx, _thread()))
        self.assertEqual(ctx.prompt.await_count, 1)
        text = _sent_text(ctx)
        self.assertNotIn('reply one text', text)
        self.assertNotIn('reply two text', text)

    def test_q_quits_from_mid_thread_too(self):
        ctx = make_ctx(prompts=['', 'q'])
        run(read_thread_interactive(ctx, _thread()))
        self.assertEqual(ctx.prompt.await_count, 2)
        text = _sent_text(ctx)
        self.assertIn('reply one text', text)
        self.assertNotIn('reply two text', text)

    def test_non_expert_menu_preamble_mentions_quit(self):
        ctx = make_ctx(player=_FakePlayer(expert=False), prompts=[''])
        run(read_thread_interactive(ctx, _thread()))
        preambles = [c.kwargs.get('preamble_lines') for c in ctx.prompt.await_args_list]
        self.assertTrue(any('[Q]uit' in line for line in preambles[0]))

    def test_list_shows_thread_message_index_not_a_new_message(self):
        ctx = make_ctx(prompts=['l', '', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        text = _sent_text(ctx)
        self.assertIn('Hello', text)   # thread title
        self.assertIn('bob', text)     # root author
        self.assertIn('carol', text)   # reply 1 author
        self.assertIn('dave', text)    # reply 2 author
        # Listing doesn't advance -- still on the root message afterward.
        self.assertEqual(ctx.prompt.await_count, 4)

    def test_prompt_text_is_end_of_bulletin_option(self):
        ctx = make_ctx(prompts=['', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        prompt_args = [c.args[0] for c in ctx.prompt.await_args_list]
        self.assertTrue(all(p == 'End of bulletin option>' for p in prompt_args))

    def test_non_expert_sees_option_preamble(self):
        ctx = make_ctx(player=_FakePlayer(expert=False), prompts=['', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        preambles = [c.kwargs.get('preamble_lines') for c in ctx.prompt.await_args_list]
        self.assertTrue(all(p is not None for p in preambles))
        self.assertTrue(any('[R]eply' in line for line in preambles[0]))
        self.assertTrue(any('[L]ist' in line for line in preambles[0]))

    def test_expert_does_not_see_option_preamble(self):
        ctx = make_ctx(player=_FakePlayer(expert=True), prompts=['', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        preambles = [c.kwargs.get('preamble_lines') for c in ctx.prompt.await_args_list]
        # Root gets no preamble at all; replies still get the short
        # "[Reply x of y]" position hint even for experts -- only the
        # full option list is expert-gated, not that.
        self.assertIsNone(preambles[0])
        self.assertTrue(all(p is not None and '[R]eply' not in ''.join(p) for p in preambles[1:]))

    def test_question_mark_redisplays_options_for_expert(self):
        ctx = make_ctx(player=_FakePlayer(expert=True), prompts=['?', '', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        text = _sent_text(ctx)
        self.assertIn('[R]eply', text)
        self.assertIn('[L]ist', text)
        self.assertIn("show this list again", text)

    def test_root_does_not_show_reply_position_preamble(self):
        ctx = make_ctx(player=_FakePlayer(expert=True), prompts=['', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        preambles = [c.kwargs.get('preamble_lines') for c in ctx.prompt.await_args_list]
        self.assertIsNone(preambles[0])  # root message, no [Reply x of y]

    def test_reply_shows_reply_position_preamble(self):
        ctx = make_ctx(player=_FakePlayer(expert=True), prompts=['', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        preambles = [c.kwargs.get('preamble_lines') for c in ctx.prompt.await_args_list]
        self.assertIn('[Reply 1 of 2]', preambles[1])
        self.assertIn('[Reply 2 of 2]', preambles[2])

    def test_reply_position_preamble_hidden_when_prompt_mode_off(self):
        ctx = make_ctx(player=_FakePlayer(expert=True, prompt_mode=False), prompts=['', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        preambles = [c.kwargs.get('preamble_lines') for c in ctx.prompt.await_args_list]
        self.assertTrue(all(p is None for p in preambles))

    def test_pm_toggles_prompt_mode_and_does_not_advance(self):
        player = _FakePlayer(expert=True, prompt_mode=True)
        ctx = make_ctx(player=player, prompts=['pm', '', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        self.assertIn('Prompt Mode: Off.', _sent_text(ctx))
        self.assertFalse(player._prompt_mode)
        # 'pm' didn't advance -- still reading the root afterward, so
        # the walk needed one more Enter than usual to finish (4, not 3).
        self.assertEqual(ctx.prompt.await_count, 4)

    def test_non_expert_menu_preamble_mentions_pm(self):
        ctx = make_ctx(player=_FakePlayer(expert=False), prompts=['', '', ''])
        run(read_thread_interactive(ctx, _thread()))
        preambles = [c.kwargs.get('preamble_lines') for c in ctx.prompt.await_args_list]
        self.assertTrue(any("'pm'" in line for line in preambles[0]))


class BoardReplyTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'board.json'
        patcher = patch.object(board_store, 'BOARD_FILE', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        board_store.save_board([_thread()], self.path)


class TestQuoteRangeListLines(BoardReplyTestCase):
    """[L]ist lines inside the 'Quote which lines?' picker -- shows the
    message's own lines numbered, then reprompts (doesn't consume the
    quote-range answer)."""

    def test_list_shows_numbered_lines_of_message_being_quoted(self):
        # r -> l (list) -> N (no quote, done)
        prompts = ['r', 'l', 'N', '', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        text = _sent_text(ctx)
        self.assertIn('1: root line one', text)
        self.assertIn('2: root line two', text)

    def test_list_then_a_real_range_still_works(self):
        prompts = ['r', 'l', '1', 'y', 'n', '', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        new_reply = threads[0]['replies'][-1]
        body_texts = [d.get('text', '') for d in new_reply['body']]
        self.assertIn('root line one', body_texts)
        self.assertNotIn('root line two', body_texts)

    def test_quote_prompt_text_is_short(self):
        # A short prompt text -- not the whole explanation -- since the
        # prompt string becomes a client's single-line input prefix with
        # nowhere to wrap on an 80-column terminal.
        prompts = ['r', 'N', '', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        prompt_args = [c.args[0] for c in ctx.prompt.await_args_list
                       if c.args and 'lines' in str(c.args[0]).lower()]
        self.assertTrue(all(p == 'Quote which lines?' for p in prompt_args))

    def test_non_expert_sees_quote_option_table(self):
        prompts = ['r', 'N', '', '', '', '']
        ctx = make_ctx(player=_FakePlayer(expert=False), prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        quote_call = next(c for c in ctx.prompt.await_args_list
                          if c.args and c.args[0] == 'Quote which lines?')
        preamble = '\n'.join(quote_call.kwargs.get('preamble_lines') or [])
        self.assertIn('[L]ist lines', preamble)
        self.assertIn('line ranges accepted', preamble)
        self.assertIn('Line range', preamble)
        self.assertIn('3-, 1-3, -6, 6-+6', preamble)
        self.assertIn('Enter', preamble)
        self.assertIn('no quote', preamble)

    def test_expert_does_not_see_quote_option_table(self):
        prompts = ['r', 'N', '', '', '', '']
        ctx = make_ctx(player=_FakePlayer(expert=True), prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        quote_call = next(c for c in ctx.prompt.await_args_list
                          if c.args and c.args[0] == 'Quote which lines?')
        self.assertIsNone(quote_call.kwargs.get('preamble_lines'))


class TestReplyWithQuote(BoardReplyTestCase):
    def test_confirmation_shows_reply_number_and_title_not_thread_id(self):
        prompts = ['r', 'all', 'y', 'n', '', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        # _thread() seeds 2 replies -- this one lands as #3.
        self.assertIn('Reply 3 posted to "Hello".', _sent_text(ctx))
        self.assertNotIn('thread #1', _sent_text(ctx))

    def test_blank_reply_title_defaults_to_re_quoted_message_title(self):
        prompts = ['r', 'all', 'y', 'n', '', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertEqual(threads[0]['replies'][-1]['title'], 'Re: Hello')

    def test_custom_reply_title_is_used(self):
        prompts = ['r', 'all', 'y', 'n', 'A Custom Title', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertEqual(threads[0]['replies'][-1]['title'], 'A Custom Title')

    def test_replying_to_a_titled_reply_defaults_to_re_its_own_title(self):
        # Jump to reply #1 (carol's) which has its own title, then reply
        # to *that* -- default should be "Re: " + carol's reply title,
        # not the thread's own root title.
        thread = _thread()
        thread['replies'][0]['title'] = "Carol's Reply Title"
        prompts = ['1', 'r', 'all', 'y', 'n', '', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, thread))
        threads = board_store.load_board(self.path)
        self.assertEqual(threads[0]['replies'][-1]['title'], "Re: Carol's Reply Title")

    def test_replying_to_an_already_re_titled_reply_does_not_double_up(self):
        thread = _thread()
        thread['replies'][0]['title'] = "Re: Hello"
        prompts = ['1', 'r', 'all', 'y', 'n', '', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, thread))
        threads = board_store.load_board(self.path)
        self.assertEqual(threads[0]['replies'][-1]['title'], 'Re: Hello')

    def test_reply_title_prompt_mentions_return_key(self):
        prompts = ['r', 'all', 'y', 'n', '', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        prompt_args = [c.args[0] for c in ctx.prompt.await_args_list]
        self.assertIn('Enter title of reply, [Enter keeps same]', prompt_args)

    def test_reply_header_shows_its_own_title_when_read_back(self):
        # read_thread_interactive() snapshots 'messages' once at the top
        # of the walk, so a reply posted mid-session isn't reachable in
        # that same call -- post it, then start a fresh read of the
        # reloaded thread to see its header.
        post_prompts = ['r', 'all', 'y', 'n', 'A Custom Title', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=post_prompts)
        run(read_thread_interactive(ctx, _thread()))

        threads = board_store.load_board(self.path)
        read_ctx = make_ctx(prompts=['', '', '', ''])
        run(read_thread_interactive(read_ctx, threads[0]))
        self.assertIn('Title: A Custom Title', _sent_text(read_ctx))

    def test_quote_all_then_confirm_posts_reply_with_body(self):
        # At the root message: 'r' -> quote range 'all' -> confirm y ->
        # anonymous 'n' -> editor typed 'my reply' then '.s' to save.
        prompts = ['r', 'all', 'y', 'n', '', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertEqual(len(threads[0]['replies']), 3)  # 2 seeded + 1 new
        new_reply = threads[0]['replies'][-1]
        self.assertEqual(new_reply['author'], 'alexa')
        self.assertFalse(new_reply['anonymous'])
        self.assertIn('Quoting bob', _sent_text(ctx))
        self.assertIn('root line one', _sent_text(ctx))
        # The confirmed quote must actually land as real buffer content in
        # the reply body -- not just shown once as a preview and then
        # discarded (a real bug caught live: run_editor() was being
        # called with no initial_lines at all).
        body_texts = [d.get('text', '') for d in new_reply['body']]
        self.assertIn('bob wrote:', body_texts)
        self.assertIn('root line one', body_texts)
        self.assertIn('root line two', body_texts)
        self.assertIn('my reply', body_texts)
        # And it must be tagged QUOTE (protected, same as IMMUTABLE), not
        # plain editable text -- otherwise a player could edit the quote
        # into something the original poster never said (Ryan's explicit
        # call).
        quote_entries = [d for d in new_reply['body'] if d.get('text') != 'my reply']
        self.assertTrue(quote_entries)
        for entry in quote_entries:
            self.assertEqual(entry.get('line_flag'), 'QUOTE')

    def test_quoted_content_renders_boxed_when_the_reply_is_later_read(self):
        # The box isn't just a one-off compose-time preview -- it's
        # stored as real Border metadata on the QUOTE lines (same
        # mechanism .B Border uses), so it's still boxed whenever anyone
        # reads this reply later, not just while composing it.
        prompts = ['r', 'all', 'y', 'n', '', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        new_reply = threads[0]['replies'][-1]

        border_roles = [d.get('border', {}).get('role') for d in new_reply['body'] if 'border' in d]
        self.assertIn('TOP', border_roles)
        self.assertIn('CONTENT', border_roles)
        self.assertIn('BOTTOM', border_roles)

        rendered = board_store.render_message_lines(new_reply, ctx, 40)
        joined = '\n'.join(rendered)
        # ANSI box-drawing corner, or the plain-ASCII '+' fallback,
        # depending on which codec this ctx (a bare MagicMock) resolves
        # to -- either way, something drew a box.
        self.assertTrue('┌' in joined or '+' in joined)

    def test_quoted_lines_cannot_be_edited_while_composing(self):
        # '.e 1' would normally prompt to edit line 1 -- since it's the
        # QUOTE-flagged 'bob wrote:' attribution line, it must be skipped
        # instead of prompting for new text.
        prompts = ['r', 'all', 'y', 'n', '', '.e 1', 'my reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        self.assertIn('immutable, skipping', _sent_text(ctx))
        threads = board_store.load_board(self.path)
        new_reply = threads[0]['replies'][-1]
        body_texts = [d.get('text', '') for d in new_reply['body']]
        self.assertIn('bob wrote:', body_texts)  # unchanged, not overwritten

    def test_no_quote_posts_reply_without_a_quote_box(self):
        prompts = ['r', 'n', 'n', '', 'unquoted reply', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertEqual(len(threads[0]['replies']), 3)
        self.assertNotIn('Quoting', _sent_text(ctx))
        body_texts = [d.get('text', '') for d in threads[0]['replies'][-1]['body']]
        self.assertEqual(body_texts, ['unquoted reply'])

    def test_declining_the_preview_reprompts_for_a_range(self):
        # First offer '1' -> preview -> decline (blank) -> then 'all' -> confirm y.
        prompts = ['r', '1', '', 'all', 'y', 'n', '', 'ok', '.s', '', '', '']
        ctx = make_ctx(prompts=prompts)
        run(read_thread_interactive(ctx, _thread()))
        threads = board_store.load_board(self.path)
        self.assertEqual(len(threads[0]['replies']), 3)

    def test_anonymous_reply(self):
        prompts = ['r', 'n', 'y', '', 'hi', '.s', '', '', '']
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
