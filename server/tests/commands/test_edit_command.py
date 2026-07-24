"""tests/commands/test_edit_command.py

Unit tests for commands/edit.py -- the EDIT command: general-purpose
personal text files, plus resuming a text_editor.py recovery file left
behind by Server.graceful_shutdown() (see tests/e2e/test_graceful_shutdown.py
for the save-on-shutdown half).
"""
from __future__ import annotations

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import commands.edit as edit_mod
from commands.edit import EditCommand


def run(coro):
    return asyncio.run(coro)


def make_ctx(name='Bob', prompts=None):
    ctx = MagicMock()
    ctx.player.name = name
    ctx.player.client_settings = SimpleNamespace(screen_columns=80)
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(side_effect=prompts or [])
    return ctx


class _TmpServerDirCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        import net_common
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = getattr(net_common, 'run_server_dir', None)
        from pathlib import Path
        net_common.run_server_dir = Path(self._tmp.name)
        self.addCleanup(self._restore)

    def _restore(self):
        import net_common
        net_common.run_server_dir = self._orig
        self._tmp.cleanup()


class TestEditBareNoRecovery(_TmpServerDirCase):

    @patch('commands.edit.run_editor', new_callable=AsyncMock)
    def test_opens_blank_editor_when_nothing_to_recover(self, mock_run_editor):
        mock_run_editor.return_value = [{'text': 'hello'}]
        ctx = make_ctx()
        result = run(EditCommand().execute(ctx))
        self.assertTrue(result.success)
        mock_run_editor.assert_awaited_once()
        kwargs = mock_run_editor.call_args.kwargs
        self.assertEqual(kwargs['activity_id'], 'edit_scratch')
        self.assertIn('not saved anywhere', str(ctx.send.call_args_list).lower())

    @patch('commands.edit.run_editor', new_callable=AsyncMock)
    def test_abort_reports_cancelled(self, mock_run_editor):
        mock_run_editor.return_value = None
        ctx = make_ctx()
        result = run(EditCommand().execute(ctx))
        self.assertTrue(result.success)
        self.assertIn('Cancelled', str(ctx.send.call_args))


class TestEditBareWithRecovery(_TmpServerDirCase):

    def _seed_recovery(self, name='Bob', internal_id='mail_compose:Alice',
                        label='writing mail to Alice'):
        from text_editor import _recovery_dir
        path = _recovery_dir() / f'{name}-20260101_000000.json'
        path.write_text(json.dumps({
            'player': name,
            'internal_id': internal_id,
            'activity_label': label,
            'lines': [{'text': 'unsaved body'}],
        }))
        return path

    def test_declining_discards_recovery_file(self):
        path = self._seed_recovery()
        ctx = make_ctx(prompts=['n'])
        result = run(EditCommand().execute(ctx))
        self.assertTrue(result.success)
        self.assertFalse(path.exists())
        self.assertIn('discarded', str(ctx.send.call_args).lower())

    @patch('commands.edit.run_editor', new_callable=AsyncMock)
    def test_resuming_passes_recovered_lines_and_activity_id(self, mock_run_editor):
        self._seed_recovery(internal_id='edit_file:notes.txt', label='editing "notes.txt"')
        mock_run_editor.return_value = [{'text': 'unsaved body'}]
        ctx = make_ctx(prompts=['y'])
        run(EditCommand().execute(ctx))
        kwargs = mock_run_editor.call_args.kwargs
        self.assertEqual(kwargs['activity_id'], 'edit_file:notes.txt')
        self.assertEqual(kwargs['activity_label'], 'editing "notes.txt"')
        initial_lines = kwargs['initial_lines']
        self.assertEqual(len(initial_lines), 1)
        self.assertEqual(initial_lines[0].text, 'unsaved body')

    @patch('commands.edit.run_editor', new_callable=AsyncMock)
    def test_unregistered_activity_falls_back_to_personal_file(self, mock_run_editor):
        self._seed_recovery(internal_id='board_post', label='posting a board thread')
        mock_run_editor.return_value = [{'text': 'unsaved body'}]
        ctx = make_ctx(prompts=['y'])
        result = run(EditCommand().execute(ctx))
        self.assertTrue(result.success)
        sent = str(ctx.send.call_args_list)
        self.assertIn('board_post.txt', sent)
        from text_editor import _user_files_dir
        saved = _user_files_dir('Bob') / 'board_post.txt'
        self.assertTrue(saved.exists())
        self.assertIn('unsaved body', saved.read_text())

    @patch('commands.edit.run_editor', new_callable=AsyncMock)
    def test_registered_activity_dispatches_instead_of_saving_file(self, mock_run_editor):
        self._seed_recovery(internal_id='mail_compose:Alice', label='writing mail to Alice')
        mock_run_editor.return_value = [{'text': 'unsaved body'}]
        ctx = make_ctx(prompts=['y'])
        with patch.object(edit_mod, '_dispatch_resume', new_callable=AsyncMock) as mock_dispatch:
            mock_dispatch.return_value = 'Mail sent to Alice.'
            result = run(EditCommand().execute(ctx))
        self.assertTrue(result.success)
        mock_dispatch.assert_awaited_once()
        self.assertIn('Mail sent to Alice.', str(ctx.send.call_args))
        from text_editor import _user_files_dir
        self.assertFalse((_user_files_dir('Bob') / 'mail_compose.txt').exists())


class TestEditFilename(_TmpServerDirCase):

    @patch('commands.edit.run_editor', new_callable=AsyncMock)
    def test_new_file_created_on_save(self, mock_run_editor):
        mock_run_editor.return_value = [{'text': 'line one'}]
        ctx = make_ctx()
        result = run(EditCommand().execute(ctx, 'notes.txt'))
        self.assertTrue(result.success)
        from text_editor import _user_files_dir
        saved = _user_files_dir('Bob') / 'notes.txt'
        self.assertTrue(saved.exists())
        self.assertIn('line one', saved.read_text())

    @patch('commands.edit.run_editor', new_callable=AsyncMock)
    def test_existing_file_loaded_as_initial_lines(self, mock_run_editor):
        from text_editor import _user_files_dir
        existing = _user_files_dir('Bob') / 'notes.txt'
        existing.write_text('old content')
        mock_run_editor.return_value = [{'text': 'old content'}]

        ctx = make_ctx()
        run(EditCommand().execute(ctx, 'notes.txt'))
        kwargs = mock_run_editor.call_args.kwargs
        self.assertEqual(kwargs['initial_lines'], ['old content'])

    def test_blank_filename_arg_is_rejected(self):
        ctx = make_ctx()
        result = run(EditCommand()._edit_file(ctx, ''))
        self.assertFalse(result.success)
        self.assertIn('Usage', str(ctx.send.call_args))


class TestDispatchResume(unittest.TestCase):

    def test_no_activity_id_returns_none(self):
        ctx = make_ctx()
        self.assertIsNone(run(edit_mod._dispatch_resume(ctx, None, [])))

    def test_unknown_prefix_returns_none(self):
        ctx = make_ctx()
        self.assertIsNone(run(edit_mod._dispatch_resume(ctx, 'unknown_thing', [])))

    def test_news_edit_dispatches_to_news_store(self):
        import news as news_store
        with patch.object(news_store, 'load_news', return_value=[{'id': 5, 'body': 'old'}]), \
             patch.object(news_store, 'save_news') as mock_save:
            ctx = make_ctx()
            result = run(edit_mod._dispatch_resume(ctx, 'news_edit:5', [{'text': 'new'}]))
        self.assertEqual(result, 'News item #5 updated.')
        mock_save.assert_called_once()
        saved_items = mock_save.call_args.args[0]
        self.assertEqual(saved_items[0]['body'], [{'text': 'new'}])

    def test_news_edit_missing_item_returns_none(self):
        import news as news_store
        with patch.object(news_store, 'load_news', return_value=[]):
            ctx = make_ctx()
            result = run(edit_mod._dispatch_resume(ctx, 'news_edit:999', [{'text': 'x'}]))
        self.assertIsNone(result)

    def test_board_reply_dispatches_to_board_store(self):
        import board as board_store
        thread = {'id': 3, 'replies': []}
        with patch.object(board_store, 'load_board', return_value=[thread]), \
             patch.object(board_store, 'save_board') as mock_save:
            ctx = make_ctx()
            result = run(edit_mod._dispatch_resume(ctx, 'board_reply:3', [{'text': 'reply body'}]))
        self.assertEqual(result, 'Reply posted to thread #3.')
        mock_save.assert_called_once()
        self.assertEqual(thread['replies'][0]['body'], [{'text': 'reply body'}])
        self.assertEqual(thread['replies'][0]['author'], 'Bob')

    def test_news_post_dispatches_with_title_and_permanent_lifetime(self):
        import news as news_store
        with patch.object(news_store, 'load_news', return_value=[]), \
             patch.object(news_store, 'next_id', return_value=7), \
             patch.object(news_store, 'save_news') as mock_save:
            ctx = make_ctx()
            result = run(edit_mod._dispatch_resume(
                ctx, 'news_post:Server Maintenance: 8pm', [{'text': 'body'}]))
        self.assertEqual(result, 'News item #7 posted (as "permanent" -- '
                                  "use 'news edit 7' to change that).")
        mock_save.assert_called_once()
        posted = mock_save.call_args.args[0][0]
        self.assertEqual(posted['title'], 'Server Maintenance: 8pm')
        self.assertEqual(posted['lifetime'], 'permanent')
        self.assertEqual(posted['author'], 'Bob')

    def test_news_post_blank_title_returns_none(self):
        result = run(edit_mod._dispatch_resume(make_ctx(), 'news_post:', [{'text': 'x'}]))
        self.assertIsNone(result)

    def test_board_post_dispatches_with_title_and_anonymous_flag(self):
        import board as board_store
        with patch.object(board_store, 'load_board', return_value=[]), \
             patch.object(board_store, 'next_id', return_value=9), \
             patch.object(board_store, 'save_board') as mock_save:
            ctx = make_ctx()
            result = run(edit_mod._dispatch_resume(
                ctx, 'board_post:Trade offer\x1f1', [{'text': 'body'}]))
        self.assertEqual(result, 'Thread #9 posted.')
        mock_save.assert_called_once()
        posted = mock_save.call_args.args[0][0]
        self.assertEqual(posted['title'], 'Trade offer')
        self.assertTrue(posted['anonymous'])

    def test_board_post_not_anonymous_when_flag_is_zero(self):
        import board as board_store
        with patch.object(board_store, 'load_board', return_value=[]), \
             patch.object(board_store, 'next_id', return_value=10), \
             patch.object(board_store, 'save_board'):
            ctx = make_ctx()
            result = run(edit_mod._dispatch_resume(
                ctx, 'board_post:Question\x1f0', [{'text': 'body'}]))
        self.assertEqual(result, 'Thread #10 posted.')

    def test_board_post_blank_title_returns_none(self):
        result = run(edit_mod._dispatch_resume(make_ctx(), 'board_post:\x1f0', [{'text': 'x'}]))
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
