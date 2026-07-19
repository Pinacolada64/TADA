"""tests/test_news.py

Unit tests for news.py -- the NEWS command's storage/visibility rules.

Run with:
    python -m pytest tests/test_news.py -v
"""
from __future__ import annotations

import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from news import (
    format_item,
    is_new_since,
    is_visible,
    load_news,
    mark_seen,
    next_id,
    save_news,
)


class TestLoadSave(unittest.TestCase):

    def test_missing_file_returns_empty_list(self):
        self.assertEqual(load_news(Path('/nonexistent/news.json')), [])

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'news.json'
            items = [{'id': 1, 'title': 'Hello', 'body': ['line'], 'lifetime': 'permanent'}]
            save_news(items, path)
            self.assertEqual(load_news(path), items)

    def test_next_id_starts_at_one(self):
        self.assertEqual(next_id([]), 1)

    def test_next_id_increments_from_max(self):
        self.assertEqual(next_id([{'id': 1}, {'id': 5}, {'id': 3}]), 6)


class TestIsVisible(unittest.TestCase):

    def test_permanent_always_visible(self):
        item = {'lifetime': 'permanent'}
        self.assertTrue(is_visible(item, 'alexa'))

    def test_once_visible_until_seen(self):
        item = {'lifetime': 'once', 'seen_by': []}
        self.assertTrue(is_visible(item, 'alexa'))
        item['seen_by'].append('alexa')
        self.assertFalse(is_visible(item, 'alexa'))

    def test_once_seen_by_one_player_still_visible_to_another(self):
        item = {'lifetime': 'once', 'seen_by': ['alexa']}
        self.assertTrue(is_visible(item, 'bob'))

    def test_range_before_start_not_visible(self):
        item = {'lifetime': 'range', 'start_date': '2026-08-01', 'end_date': '2026-08-31'}
        self.assertFalse(is_visible(item, 'alexa', today=datetime.date(2026, 7, 1)))

    def test_range_within_window_visible(self):
        item = {'lifetime': 'range', 'start_date': '2026-08-01', 'end_date': '2026-08-31'}
        self.assertTrue(is_visible(item, 'alexa', today=datetime.date(2026, 8, 15)))

    def test_range_after_end_not_visible(self):
        item = {'lifetime': 'range', 'start_date': '2026-08-01', 'end_date': '2026-08-31'}
        self.assertFalse(is_visible(item, 'alexa', today=datetime.date(2026, 9, 1)))

    def test_range_open_ended_end_visible_indefinitely(self):
        item = {'lifetime': 'range', 'start_date': '2026-08-01', 'end_date': None}
        self.assertTrue(is_visible(item, 'alexa', today=datetime.date(2030, 1, 1)))


class TestIsNewSince(unittest.TestCase):

    def test_none_since_means_everything_is_new(self):
        item = {'posted_at': '2020-01-01T00:00:00'}
        self.assertTrue(is_new_since(item, None))

    def test_posted_after_since_is_new(self):
        item = {'posted_at': '2026-07-05T12:00:00'}
        since = datetime.datetime(2026, 7, 1)
        self.assertTrue(is_new_since(item, since))

    def test_posted_before_since_is_not_new(self):
        item = {'posted_at': '2026-06-01T12:00:00'}
        since = datetime.datetime(2026, 7, 1)
        self.assertFalse(is_new_since(item, since))

    def test_missing_posted_at_treated_as_new(self):
        self.assertTrue(is_new_since({}, datetime.datetime(2026, 7, 1)))


class TestMarkSeen(unittest.TestCase):

    def test_adds_player_once(self):
        item = {'seen_by': []}
        mark_seen(item, 'alexa')
        mark_seen(item, 'alexa')
        self.assertEqual(item['seen_by'], ['alexa'])

    def test_creates_seen_by_if_missing(self):
        item = {}
        mark_seen(item, 'alexa')
        self.assertEqual(item['seen_by'], ['alexa'])


class TestFormatItem(unittest.TestCase):

    def test_includes_title_and_body(self):
        # 'body' here is old-format plain strings (pre-dating structured
        # Line storage) -- format_item() migrates each into an unformatted
        # Line via formatting.deserialize_lines(), so old posts still
        # display exactly as before.
        item = {'title': 'Server Update', 'body': ['Line one.', 'Line two.']}
        ctx = MagicMock()
        ctx.player.client_settings.screen_columns = 80
        lines = format_item(item, ctx)
        self.assertIn('Server Update', lines[0])
        self.assertEqual(lines[1:], ['Line one.', 'Line two.'])

    def test_centered_body_rerenders_per_viewer_screen_width(self):
        # The whole point of storing 'body' as structured Line dicts
        # instead of pre-rendered strings: the same saved item displays
        # correctly at two different screen widths, rather than being
        # frozen at whatever width the author had when they saved it.
        item = {'title': 'Update', 'body': [{'text': 'hi', 'justification': 'CENTER'}]}
        narrow_ctx = MagicMock()
        narrow_ctx.player.client_settings.screen_columns = 10
        wide_ctx = MagicMock()
        wide_ctx.player.client_settings.screen_columns = 20
        narrow_lines = format_item(item, narrow_ctx)
        wide_lines = format_item(item, wide_ctx)
        self.assertEqual(narrow_lines[1], 'hi'.center(10))
        self.assertEqual(wide_lines[1], 'hi'.center(20))


if __name__ == '__main__':
    unittest.main()
