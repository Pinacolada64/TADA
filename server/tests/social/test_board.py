"""tests/social/test_board.py

Unit tests for board.py -- the threaded message board's storage/
rendering rules. Mirrors tests/social/test_news.py's structure.
"""
from __future__ import annotations

import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from board import (
    build_quote_preamble,
    display_author,
    format_thread,
    format_thread_summary,
    is_new_since,
    load_board,
    load_config,
    next_id,
    save_board,
    save_config,
)


def _ctx(screen_columns: int = 80):
    ctx = MagicMock()
    ctx.player.client_settings.screen_columns = screen_columns
    return ctx


class TestLoadSave(unittest.TestCase):
    def test_missing_file_returns_empty_list(self):
        self.assertEqual(load_board(Path('/nonexistent/board.json')), [])

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'board.json'
            threads = [{'id': 1, 'title': 'Hello', 'body': [{'text': 'line'}],
                        'author': 'alexa', 'anonymous': False, 'replies': []}]
            save_board(threads, path)
            self.assertEqual(load_board(path), threads)

    def test_next_id_starts_at_one(self):
        self.assertEqual(next_id([]), 1)

    def test_next_id_increments_from_max(self):
        self.assertEqual(next_id([{'id': 1}, {'id': 5}, {'id': 3}]), 6)


class TestConfig(unittest.TestCase):
    def test_missing_file_returns_defaults(self):
        config = load_config(Path('/nonexistent/board_config.json'))
        self.assertEqual(config, {'anonymous_mode': 'ask'})

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'board_config.json'
            save_config({'anonymous_mode': 'yes'}, path)
            self.assertEqual(load_config(path), {'anonymous_mode': 'yes'})

    def test_partial_saved_config_still_fills_in_defaults(self):
        # e.g. a config file saved before some future second setting
        # existed -- missing keys should still resolve to their default.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'board_config.json'
            path.write_text('{}')
            self.assertEqual(load_config(path), {'anonymous_mode': 'ask'})


class TestDisplayAuthor(unittest.TestCase):
    def test_non_anonymous_shows_real_name(self):
        entry = {'author': 'alexa', 'anonymous': False}
        self.assertEqual(display_author(entry, viewer_is_privileged=False), 'alexa')
        self.assertEqual(display_author(entry, viewer_is_privileged=True), 'alexa')

    def test_anonymous_hides_name_from_ordinary_viewer(self):
        entry = {'author': 'alexa', 'anonymous': True}
        self.assertEqual(display_author(entry, viewer_is_privileged=False), 'Anonymous')

    def test_anonymous_reveals_name_to_privileged_viewer(self):
        entry = {'author': 'alexa', 'anonymous': True}
        self.assertEqual(display_author(entry, viewer_is_privileged=True), 'Anonymous (alexa)')


class TestIsNewSince(unittest.TestCase):
    def test_none_since_means_everything_is_new(self):
        thread = {'posted_at': '2020-01-01T00:00:00', 'replies': []}
        self.assertTrue(is_new_since(thread, None))

    def test_root_posted_after_since_is_new(self):
        thread = {'posted_at': '2026-07-05T12:00:00', 'replies': []}
        self.assertTrue(is_new_since(thread, datetime.date(2026, 7, 1)))

    def test_root_posted_before_since_and_no_replies_is_not_new(self):
        thread = {'posted_at': '2026-06-01T12:00:00', 'replies': []}
        self.assertFalse(is_new_since(thread, datetime.date(2026, 7, 1)))

    def test_old_root_but_new_reply_counts_as_new(self):
        thread = {
            'posted_at': '2026-06-01T12:00:00',
            'replies': [{'posted_at': '2026-07-10T12:00:00'}],
        }
        self.assertTrue(is_new_since(thread, datetime.date(2026, 7, 1)))

    def test_old_root_and_old_replies_not_new(self):
        thread = {
            'posted_at': '2026-06-01T12:00:00',
            'replies': [{'posted_at': '2026-06-15T12:00:00'}],
        }
        self.assertFalse(is_new_since(thread, datetime.date(2026, 7, 1)))


class TestFormatThreadSummary(unittest.TestCase):
    def test_includes_id_title_author_and_reply_count(self):
        thread = {'id': 3, 'title': 'Hello', 'author': 'alexa', 'anonymous': False,
                  'replies': [{}, {}]}
        summary = format_thread_summary(thread, viewer_is_privileged=False)
        self.assertIn('3', summary)
        self.assertIn('Hello', summary)
        self.assertIn('alexa', summary)
        self.assertIn('2 replies', summary)

    def test_singular_reply_count(self):
        thread = {'id': 1, 'title': 'X', 'author': 'a', 'anonymous': False, 'replies': [{}]}
        summary = format_thread_summary(thread, viewer_is_privileged=False)
        self.assertIn('1 reply', summary)
        self.assertNotIn('1 replies', summary)


class TestFormatThread(unittest.TestCase):
    def test_includes_root_and_replies(self):
        thread = {
            'id': 1, 'title': 'Hello', 'author': 'alexa', 'anonymous': False,
            'posted_at': '2026-07-01T00:00:00',
            'body': [{'text': 'root text'}],
            'replies': [
                {'author': 'bob', 'anonymous': False, 'posted_at': '2026-07-02T00:00:00',
                 'body': [{'text': 'reply text'}]},
            ],
        }
        lines = format_thread(thread, _ctx(), viewer_is_privileged=False)
        joined = '\n'.join(lines)
        self.assertIn('Hello', joined)
        self.assertIn('root text', joined)
        self.assertIn('reply text', joined)
        self.assertIn('bob', joined)

    def test_anonymous_reply_hidden_from_ordinary_viewer(self):
        thread = {
            'id': 1, 'title': 'Hello', 'author': 'alexa', 'anonymous': False,
            'posted_at': '2026-07-01T00:00:00', 'body': [{'text': 'root'}],
            'replies': [
                {'author': 'bob', 'anonymous': True, 'posted_at': '2026-07-02T00:00:00',
                 'body': [{'text': 'reply text'}]},
            ],
        }
        lines = format_thread(thread, _ctx(), viewer_is_privileged=False)
        joined = '\n'.join(lines)
        self.assertNotIn('bob', joined)
        self.assertIn('Anonymous', joined)


class TestBuildQuotePreamble(unittest.TestCase):
    def test_titles_the_box_with_the_authors_name(self):
        thread = {'author': 'alexa', 'anonymous': False, 'body': [{'text': 'quoted line'}]}
        lines = build_quote_preamble(_ctx(40), thread, viewer_is_privileged=False)
        joined = '\n'.join(lines)
        self.assertIn('Quoting alexa', joined)
        self.assertIn('quoted line', joined)

    def test_anonymous_author_quoted_as_anonymous(self):
        thread = {'author': 'alexa', 'anonymous': True, 'body': [{'text': 'quoted line'}]}
        lines = build_quote_preamble(_ctx(), thread, viewer_is_privileged=False)
        joined = '\n'.join(lines)
        self.assertIn('Quoting Anonymous', joined)


if __name__ == '__main__':
    unittest.main()
