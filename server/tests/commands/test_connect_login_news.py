"""tests/commands/test_connect_login_news.py

Covers commands/connect.py's _login_news_lines() -- specifically that a
'once' news item doesn't come back on a later login just because the
player's news_show_all preference bypasses is_new_since()'s filtering,
or seen_by somehow didn't stick. See news.is_visible()'s last_played
param for the underlying fix.
"""
from __future__ import annotations

import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import news as news_store
from commands.connect import _login_news_lines


def _player(name='Rulan', last_connection=None, news_show_all=False):
    player = MagicMock()
    player.name = name
    player.last_connection = last_connection
    player.command_settings.news_show_all = news_show_all
    return player


class TestLoginNewsOnceLifetime(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'news.json'
        patcher = patch.object(news_store, 'NEWS_FILE', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

        news_store.save_news([{
            'id': 1, 'title': 'Server Update', 'body': ['hi'],
            'author': 'admin', 'lifetime': 'once',
            'posted_at': '2026-08-01T00:00:00', 'seen_by': [],
        }])

        self.ctx = MagicMock()
        self.ctx.player.client_settings.screen_columns = 80

    def _current_items(self):
        return news_store.load_news(self.path)

    def test_shown_on_first_login_since_posting(self):
        player = _player(last_connection=datetime.datetime(2026, 7, 31))
        lines = _login_news_lines(self.ctx, player)
        self.assertTrue(any('Server Update' in line for line in lines))
        self.assertIn('Rulan', self._current_items()[0]['seen_by'])

    def test_not_shown_again_next_login_new_only(self):
        # First login marks it seen via seen_by -- news_show_all=False
        # path already relied on is_new_since() plus is_visible().
        player = _player(last_connection=datetime.datetime(2026, 7, 31))
        _login_news_lines(self.ctx, player)
        player.last_connection = datetime.datetime(2026, 8, 2)
        lines = _login_news_lines(self.ctx, player)
        self.assertEqual(lines, [])

    def test_not_shown_again_next_login_show_all(self):
        # Regression: news_show_all=True bypasses is_new_since(), so
        # this path used to only rely on seen_by. last_played now
        # backstops it even if seen_by somehow didn't persist.
        player = _player(last_connection=datetime.datetime(2026, 7, 31), news_show_all=True)
        _login_news_lines(self.ctx, player)
        items = self._current_items()
        items[0]['seen_by'] = []  # simulate seen_by never having stuck
        news_store.save_news(items)
        player.last_connection = datetime.datetime(2026, 8, 2)
        lines = _login_news_lines(self.ctx, player)
        self.assertEqual(lines, [])

    def test_still_shown_if_never_logged_in_since_posting_show_all(self):
        player = _player(last_connection=datetime.datetime(2026, 7, 15), news_show_all=True)
        lines = _login_news_lines(self.ctx, player)
        self.assertTrue(any('Server Update' in line for line in lines))


if __name__ == '__main__':
    unittest.main(verbosity=2)
