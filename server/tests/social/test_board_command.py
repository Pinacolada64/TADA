"""tests/social/test_board_command.py

Unit tests for commands/board.py -- the in-game BOARD command surface.
Mirrors tests/social/test_news_command.py's structure.
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import board as board_store
from command_settings import CommandSettings
from commands.board import BoardCommand
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
    def __init__(self, name='alexa', admin=False, prompt_mode=False):
        self.name = name
        self._admin = admin
        self._prompt_mode = prompt_mode
        self.return_key = 'Enter'
        self.command_settings = CommandSettings()
        self.client_settings = MagicMock()
        self.unsaved_changes = False

    def query_flag(self, flag):
        if flag == PlayerFlags.ADMIN:
            return self._admin
        if flag == PlayerFlags.PROMPT_MODE:
            return self._prompt_mode
        return False

    def toggle_flag(self, flag):
        if flag == PlayerFlags.PROMPT_MODE:
            self._prompt_mode = not self._prompt_mode
            return self._prompt_mode, None
        return False, None


def make_ctx(player=None, prompts=None, screen_columns=80):
    ctx = MagicMock()
    ctx.player = player or _FakePlayer()
    ctx.player.client_settings.screen_columns = screen_columns
    ctx.client.virtual_location = None
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(side_effect=prompts or [])
    return ctx


class BoardCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'board_threads.json'
        self.config_path = Path(self._tmp.name) / 'board_meta.json'
        patcher = patch.object(board_store.threads, 'BOARD_FILE', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        config_patcher = patch.object(board_store.meta, 'META_FILE', self.config_path)
        config_patcher.start()
        self.addCleanup(config_patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def _seed(self, threads):
        board_store.save_board(threads, self.path)


class TestList(BoardCommandTestCase):
    def test_no_threads_message(self):
        ctx = make_ctx()
        run(BoardCommand().execute(ctx))
        sent = str(ctx.send.call_args)
        self.assertIn('No threads', sent)

    def test_lists_threads(self):
        self._seed([{'id': 1, 'title': 'Hello World', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'x'}], 'replies': []}])
        ctx = make_ctx(prompts=[''])
        run(BoardCommand().execute(ctx))
        sent = str(ctx.prompt.call_args)
        self.assertIn('Hello World', sent)

    def test_reading_a_thread_shows_body_and_returns_to_listing(self):
        self._seed([{'id': 1, 'title': 'Hello', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'thread body'}],
                      'replies': []}])
        ctx = make_ctx(prompts=['1', ''])
        run(BoardCommand().execute(ctx))
        self.assertEqual(ctx.prompt.await_count, 2)
        sent = str(ctx.send.call_args_list)
        self.assertIn('thread body', sent)

    def test_from_and_date_are_separate_colorized_lines(self):
        self._seed([{'id': 1, 'title': 'Hello', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'thread body'}],
                      'replies': []}])
        ctx = make_ctx(prompts=['1', ''])
        run(BoardCommand().execute(ctx))
        lines = [l for call in ctx.send.call_args_list for l in
                 (call.args[0] if isinstance(call.args[0], list) else [call.args[0]])]
        # Fields present: Number, From, Date, Title -- width = len('Number') = 6.
        self.assertIn(_expected_header_line('Number', '1 of 1', 0, 6), lines)
        self.assertIn(_expected_header_line('From', 'bob', 1, 6), lines)
        self.assertIn(_expected_header_line('Date', '2026-01-01', 2, 6), lines)
        self.assertNotIn('From: bob  (2026-01-01)', lines)

    def test_number_line_reflects_id_and_board_wide_total(self):
        self._seed([
            {'id': 1, 'title': 'First', 'author': 'bob', 'anonymous': False,
             'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'x'}], 'replies': []},
            {'id': 5, 'title': 'Fifth', 'author': 'carol', 'anonymous': False,
             'posted_at': '2026-01-02T00:00:00', 'body': [{'text': 'y'}], 'replies': []},
        ])
        ctx = make_ctx(prompts=['5', ''])
        run(BoardCommand().execute(ctx))
        sent = str(ctx.send.call_args_list)
        # thread id 5 is used verbatim (not its position in the list),
        # against the board-wide total of 2 threads.
        self.assertIn('Number: 5 of 2', sent)

    def test_pm_at_listing_prompt_toggles_and_stays_in_listing(self):
        self._seed([{'id': 1, 'title': 'Hello', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'x'}], 'replies': []}])
        player = _FakePlayer(prompt_mode=False)
        ctx = make_ctx(player=player, prompts=['pm', ''])
        run(BoardCommand().execute(ctx))
        self.assertIn('Prompt Mode: On.', str(ctx.send.call_args_list))
        self.assertTrue(player._prompt_mode)
        # 'pm' redisplays the listing rather than exiting -- two prompts
        # were needed (the 'pm' itself, then the blank Enter to exit).
        self.assertEqual(ctx.prompt.await_count, 2)

    def test_virtual_location_set_while_listing(self):
        self._seed([{'id': 1, 'title': 'Hello', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'x'}], 'replies': []}])
        seen_location = {}

        async def _prompt(*a, **kw):
            seen_location['during'] = ctx.client.virtual_location
            return ''

        ctx = make_ctx()
        ctx.prompt = _prompt
        run(BoardCommand().execute(ctx))

        self.assertEqual(seen_location['during'], 'Reading board')
        self.assertIsNone(ctx.client.virtual_location)


class TestReadNew(BoardCommandTestCase):
    def test_rn_with_no_threshold_shows_everything(self):
        self._seed([{'id': 1, 'title': 'Old', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2020-01-01T00:00:00', 'body': [{'text': 'x'}], 'replies': []}])
        ctx = make_ctx(prompts=[''])
        run(BoardCommand().execute(ctx, 'rn'))
        sent = str(ctx.prompt.call_args)
        self.assertIn('Old', sent)

    def test_rn_filters_out_threads_older_than_threshold(self):
        self._seed([
            {'id': 1, 'title': 'Old Thread', 'author': 'bob', 'anonymous': False,
             'posted_at': '2020-01-01T00:00:00', 'body': [{'text': 'x'}], 'replies': []},
            {'id': 2, 'title': 'New Thread', 'author': 'bob', 'anonymous': False,
             'posted_at': '2030-01-01T00:00:00', 'body': [{'text': 'x'}], 'replies': []},
        ])
        player = _FakePlayer()
        player.command_settings.board.last_date = '2026-01-01'
        ctx = make_ctx(player=player, prompts=[''])
        run(BoardCommand().execute(ctx, 'rn'))
        sent = str(ctx.prompt.call_args)
        self.assertIn('New Thread', sent)
        self.assertNotIn('Old Thread', sent)


class TestSetLastDate(BoardCommandTestCase):
    def test_absolute_date_sets_threshold(self):
        player = _FakePlayer()
        ctx = make_ctx(player=player, prompts=['7/1/26'])
        result = run(BoardCommand().execute(ctx, 'ld'))
        self.assertTrue(result.success)
        self.assertEqual(player.command_settings.board.last_date, '2026-07-01')

    def test_relative_shortcut_sets_threshold(self):
        import datetime
        player = _FakePlayer()
        ctx = make_ctx(player=player, prompts=['1 week'])
        run(BoardCommand().execute(ctx, 'ld'))
        expected = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        self.assertEqual(player.command_settings.board.last_date, expected)

    def test_blank_leaves_threshold_unchanged(self):
        player = _FakePlayer()
        player.command_settings.board.last_date = '2026-01-01'
        ctx = make_ctx(player=player, prompts=[''])
        run(BoardCommand().execute(ctx, 'ld'))
        self.assertEqual(player.command_settings.board.last_date, '2026-01-01')

    def test_unparseable_text_reports_error(self):
        player = _FakePlayer()
        ctx = make_ctx(player=player, prompts=['not a date at all!!'])
        result = run(BoardCommand().execute(ctx, 'ld'))
        self.assertFalse(result.success)


class TestPostAndReply(BoardCommandTestCase):
    def test_post_creates_thread(self):
        ctx = make_ctx(prompts=['My Title', 'n', 'hello there', '.s'])
        result = run(BoardCommand().execute(ctx, 'post'))
        self.assertTrue(result.success)
        threads = board_store.load_board(self.path)
        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0]['title'], 'My Title')
        self.assertEqual(threads[0]['author'], 'alexa')
        self.assertFalse(threads[0]['anonymous'])
        self.assertEqual(threads[0]['replies'], [])

    def test_post_anonymous(self):
        ctx = make_ctx(prompts=['Title', 'y', 'body', '.s'])
        run(BoardCommand().execute(ctx, 'post'))
        threads = board_store.load_board(self.path)
        self.assertTrue(threads[0]['anonymous'])
        self.assertEqual(threads[0]['author'], 'alexa')  # real name always stored

    def test_reply_appends_to_thread_and_shows_quote(self):
        self._seed([{'id': 1, 'title': 'Original', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'original text'}],
                      'replies': []}])
        ctx = make_ctx(prompts=['n', '', 'my reply text', '.s'])
        result = run(BoardCommand().execute(ctx, 'reply', '1'))
        self.assertTrue(result.success)
        threads = board_store.load_board(self.path)
        self.assertEqual(len(threads[0]['replies']), 1)
        reply = threads[0]['replies'][0]
        self.assertEqual(reply['author'], 'alexa')
        self.assertEqual([d.get('text') for d in reply['body']], ['my reply text'])
        sent = str(ctx.send.call_args_list)
        self.assertIn('Quoting bob', sent)
        self.assertIn('original text', sent)

    def test_blank_reply_title_defaults_to_re_thread_title(self):
        self._seed([{'id': 1, 'title': 'Original', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'original text'}],
                      'replies': []}])
        ctx = make_ctx(prompts=['n', '', 'my reply text', '.s'])
        run(BoardCommand().execute(ctx, 'reply', '1'))
        threads = board_store.load_board(self.path)
        self.assertEqual(threads[0]['replies'][0]['title'], 'Re: Original')

    def test_custom_reply_title_is_used(self):
        self._seed([{'id': 1, 'title': 'Original', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'original text'}],
                      'replies': []}])
        ctx = make_ctx(prompts=['n', 'A Custom Reply Title', 'my reply text', '.s'])
        run(BoardCommand().execute(ctx, 'reply', '1'))
        threads = board_store.load_board(self.path)
        self.assertEqual(threads[0]['replies'][0]['title'], 'A Custom Reply Title')

    def test_reply_title_prompt_mentions_return_key(self):
        self._seed([{'id': 1, 'title': 'Original', 'author': 'bob', 'anonymous': False,
                      'posted_at': '2026-01-01T00:00:00', 'body': [{'text': 'original text'}],
                      'replies': []}])
        ctx = make_ctx(prompts=['n', '', 'my reply text', '.s'])
        run(BoardCommand().execute(ctx, 'reply', '1'))
        prompt_args = [c.args[0] for c in ctx.prompt.await_args_list]
        self.assertIn('Enter title of reply, [Enter keeps same]', prompt_args)

    def test_reply_confirmation_shows_number_and_title_not_thread_id(self):
        self._seed([{'id': 7, 'title': 'A Bulletin About Cheese', 'author': 'bob',
                      'anonymous': False, 'posted_at': '2026-01-01T00:00:00',
                      'body': [{'text': 'original text'}], 'replies': []}])
        ctx = make_ctx(prompts=['n', '', 'my reply text', '.s'])
        run(BoardCommand().execute(ctx, 'reply', '7'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('Reply 1 posted to "A Bulletin About Cheese".', sent)
        self.assertNotIn('thread #7', sent)

    def test_second_reply_is_numbered_2(self):
        self._seed([{'id': 7, 'title': 'A Bulletin About Cheese', 'author': 'bob',
                      'anonymous': False, 'posted_at': '2026-01-01T00:00:00',
                      'body': [{'text': 'original text'}],
                      'replies': [{'author': 'carol', 'anonymous': False,
                                   'posted_at': '2026-01-02T00:00:00',
                                   'body': [{'text': 'first reply'}]}]}])
        ctx = make_ctx(prompts=['n', '', 'second reply text', '.s'])
        run(BoardCommand().execute(ctx, 'reply', '7'))
        sent = str(ctx.send.call_args_list)
        self.assertIn('Reply 2 posted to "A Bulletin About Cheese".', sent)

    def test_reply_to_unknown_thread_fails(self):
        ctx = make_ctx(prompts=[])
        result = run(BoardCommand().execute(ctx, 'reply', '99'))
        self.assertFalse(result.success)


class TestResolveAnonymous(BoardCommandTestCase):
    """anonymous_mode 'yes'/'no' (set via 'board #edit') skip the prompt
    entirely; 'ask' (the default) still prompts, same as before this
    setting existed."""

    def test_ask_mode_prompts(self):
        from commands.board.board import resolve_anonymous
        ctx = make_ctx(prompts=['y'])
        result = run(resolve_anonymous(ctx))
        self.assertTrue(result)
        ctx.prompt.assert_awaited_once()

    def test_yes_mode_skips_the_prompt(self):
        from commands.board.board import resolve_anonymous
        board_store.save_config({'anonymous_mode': 'yes'}, self.config_path)
        ctx = make_ctx(prompts=[])
        result = run(resolve_anonymous(ctx))
        self.assertTrue(result)
        ctx.prompt.assert_not_awaited()

    def test_no_mode_skips_the_prompt(self):
        from commands.board.board import resolve_anonymous
        board_store.save_config({'anonymous_mode': 'no'}, self.config_path)
        ctx = make_ctx(prompts=[])
        result = run(resolve_anonymous(ctx))
        self.assertFalse(result)
        ctx.prompt.assert_not_awaited()

    def test_post_honors_yes_mode_without_prompting(self):
        board_store.save_config({'anonymous_mode': 'yes'}, self.config_path)
        ctx = make_ctx(prompts=['My Title', 'body', '.s'])  # no anon prompt consumed
        run(BoardCommand().execute(ctx, 'post'))
        threads = board_store.load_board(self.path)
        self.assertTrue(threads[0]['anonymous'])


class TestEditSwitch(BoardCommandTestCase):
    def test_non_admin_denied(self):
        ctx = make_ctx(player=_FakePlayer(admin=False))
        result = run(BoardCommand().execute(ctx, '#edit'))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'permission_denied')

    def test_admin_reaches_the_settings_menu(self):
        ctx = make_ctx(player=_FakePlayer(admin=True), prompts=[''])
        result = run(BoardCommand().execute(ctx, '#edit'))
        self.assertTrue(result.success)
        self.assertIn('Board Settings', str(ctx.prompt.call_args))

    def test_unknown_switch_reports_error(self):
        ctx = make_ctx()
        result = run(BoardCommand().execute(ctx, '#bogus'))
        self.assertFalse(result.success)


class TestDelete(BoardCommandTestCase):
    def test_non_admin_cannot_delete(self):
        self._seed([{'id': 1, 'title': 'X', 'author': 'a', 'anonymous': False,
                      'body': [], 'replies': []}])
        ctx = make_ctx(player=_FakePlayer(admin=False))
        result = run(BoardCommand().execute(ctx, 'delete', '1'))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'permission_denied')

    def test_admin_can_delete(self):
        self._seed([{'id': 1, 'title': 'X', 'author': 'a', 'anonymous': False,
                      'body': [], 'replies': []}])
        ctx = make_ctx(player=_FakePlayer(admin=True))
        result = run(BoardCommand().execute(ctx, 'delete', '1'))
        self.assertTrue(result.success)
        self.assertEqual(board_store.load_board(self.path), [])


if __name__ == '__main__':
    unittest.main()
