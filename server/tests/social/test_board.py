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

import board
from board import (
    MessageHeader,
    build_quote_preamble,
    display_author,
    format_thread,
    format_thread_listing,
    format_thread_summary,
    is_new_since,
    load_board,
    load_config,
    next_id,
    save_board,
    save_config,
)


def _expected_header(fields: list[tuple[str, str]]) -> list[str]:
    """Mirrors MessageHeader.display()'s own right-justify-to-widest-
    label + positional-color logic, computed from *fields* instead of
    hand-counted spaces -- so these tests don't need rewriting every
    time the header format itself changes (still in flux). Reads the
    real color table (board._HEADER_COLORS_BY_POSITION/
    _HEADER_FALLBACK_COLOR) rather than duplicating it, so a color-order
    change doesn't silently desync the expectation from the code."""
    width = max(len(label) for label, _ in fields)
    lines = []
    for i, (label, value) in enumerate(fields):
        color = (board._HEADER_COLORS_BY_POSITION[i]
                 if i < len(board._HEADER_COLORS_BY_POSITION)
                 else board._HEADER_FALLBACK_COLOR)
        lines.append(f'|{color}|{label.rjust(width)}: {value}|reset|')
    return lines


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
    """load_config()/save_config() are a back-compat shim over
    board/meta.py's per-board storage (board_meta.json) -- see that
    module's docstring -- so 'the config file' here means the default
    board's (id 1) own meta entry, not a standalone flat file anymore."""

    def test_missing_file_returns_defaults(self):
        config = load_config(Path('/nonexistent/board_meta.json'))
        self.assertEqual(config, {'anonymous_mode': 'ask'})

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'board_meta.json'
            save_config({'anonymous_mode': 'yes'}, path)
            self.assertEqual(load_config(path), {'anonymous_mode': 'yes'})

    def test_partial_saved_meta_still_fills_in_defaults(self):
        # e.g. a meta file saved before some future second setting
        # existed -- missing keys should still resolve to their default.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'board_meta.json'
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


class TestMessageHeader(unittest.TestCase):
    """Colors are positional, not per-field: 1st line cyan, 2nd
    light_green, every line after that yellow (Ryan's call)."""

    def test_display_without_replies_right_justifies_to_title_width(self):
        header = MessageHeader(title='Hello', author='bob', date='2026-01-01')
        self.assertEqual(header.display(), _expected_header([
            ('From', 'bob'), ('Date', '2026-01-01'), ('Title', 'Hello'),
        ]))

    def test_display_with_replies_adds_replies_line_right_justified_to_it(self):
        header = MessageHeader(title='Hello', author='bob', date='2026-01-01', reply_count=3)
        self.assertEqual(header.display(), _expected_header([
            ('From', 'bob'), ('Date', '2026-01-01'), ('Title', 'Hello'), ('Replies', '3'),
        ]))

    def test_display_omits_replies_line_when_zero(self):
        header = MessageHeader(title='Hello', author='bob', date='2026-01-01', reply_count=0)
        self.assertEqual(len(header.display()), 3)
        self.assertFalse(any('Replies' in l for l in header.display()))

    def test_display_with_thread_number_shows_number_line_first(self):
        header = MessageHeader(title='Hello', author='bob', date='2026-01-01',
                                thread_number=3, total_threads=9)
        self.assertEqual(header.display(), _expected_header([
            ('Number', '3 of 9'), ('From', 'bob'), ('Date', '2026-01-01'), ('Title', 'Hello'),
        ]))

    def test_display_omits_number_line_when_total_threads_is_zero(self):
        header = MessageHeader(title='Hello', author='bob', date='2026-01-01',
                                thread_number=3, total_threads=0)
        self.assertFalse(any('Number' in l for l in header.display()))

    def test_display_number_and_replies_together_justify_to_replies(self):
        header = MessageHeader(title='Hello', author='bob', date='2026-01-01',
                                reply_count=2, thread_number=3, total_threads=9)
        self.assertEqual(header.display(), _expected_header([
            ('Number', '3 of 9'), ('From', 'bob'), ('Date', '2026-01-01'),
            ('Title', 'Hello'), ('Replies', '2'),
        ]))

    def test_for_entry_resolves_author_and_truncates_date(self):
        entry = {'author': 'alexa', 'anonymous': False, 'posted_at': '2026-03-05T14:32:01.123456'}
        header = MessageHeader.for_entry(entry, 'My Title', viewer_is_privileged=False)
        self.assertEqual(header.title, 'My Title')
        self.assertEqual(header.author, 'alexa')
        self.assertEqual(header.date, '2026-03-05')
        self.assertEqual(header.reply_count, 0)

    def test_for_entry_passes_through_reply_count(self):
        entry = {'author': 'alexa', 'anonymous': False, 'posted_at': '2026-01-01T00:00:00'}
        header = MessageHeader.for_entry(entry, 'T', viewer_is_privileged=False, reply_count=5)
        self.assertEqual(header.reply_count, 5)

    def test_for_entry_passes_through_thread_number_and_total(self):
        entry = {'author': 'alexa', 'anonymous': False, 'posted_at': '2026-01-01T00:00:00'}
        header = MessageHeader.for_entry(entry, 'T', viewer_is_privileged=False,
                                          thread_number=4, total_threads=10)
        self.assertEqual(header.thread_number, 4)
        self.assertEqual(header.total_threads, 10)

    def test_for_entry_honors_anonymous_reveal_rule(self):
        entry = {'author': 'alexa', 'anonymous': True, 'posted_at': '2026-01-01T00:00:00'}
        hidden = MessageHeader.for_entry(entry, 'T', viewer_is_privileged=False)
        revealed = MessageHeader.for_entry(entry, 'T', viewer_is_privileged=True)
        self.assertEqual(hidden.author, 'Anonymous')
        self.assertEqual(revealed.author, 'Anonymous (alexa)')


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


class TestFormatThreadListing(unittest.TestCase):
    def test_header_row_has_the_three_column_titles(self):
        threads = [{'id': 1, 'title': 'Hello', 'replies': []}]
        lines = format_thread_listing(threads, width=40)
        self.assertIn('##', lines[0])
        self.assertIn('Title', lines[0])
        self.assertIn('Replies', lines[0])

    def test_row_shows_id_and_reply_count(self):
        threads = [{'id': 7, 'title': 'Hello', 'replies': [{}, {}]}]
        lines = format_thread_listing(threads, width=40)
        row = lines[1]
        self.assertIn('7', row)
        self.assertIn('Hello', row)
        self.assertIn('2', row)

    def test_long_title_is_elided_with_ellipsis_by_default(self):
        threads = [{'id': 1, 'title': 'X' * 60, 'replies': []}]
        lines = format_thread_listing(threads, width=40)
        row = lines[1]
        self.assertIn('…', row)
        self.assertNotIn('X' * 60, row)

    def test_long_title_is_elided_with_dots_on_petscii(self):
        threads = [{'id': 1, 'title': 'X' * 60, 'replies': []}]
        lines = format_thread_listing(threads, width=40, is_petscii=True)
        row = lines[1]
        self.assertIn('...', row)
        self.assertNotIn('…', row)

    def test_short_title_is_not_elided(self):
        threads = [{'id': 1, 'title': 'Short', 'replies': []}]
        lines = format_thread_listing(threads, width=40)
        self.assertIn('Short', lines[1])
        self.assertNotIn('…', lines[1])
        self.assertNotIn('...', lines[1])


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
