"""tests/logon_events/test_news_login.py

Covers logon_events/news.py's news_lines() -- specifically that a 'once'
news item doesn't come back on a later login just because the player's
news_show_all preference bypasses is_new_since()'s filtering, or
seen_by somehow didn't stick. See news.is_visible()'s last_played param
for the underlying fix.

Also covers command_settings.news.last_read -- the dedicated news-read
cursor that replaced player.last_connection as is_new_since()'s 'since'
argument, and news_lines()'s immediate force-save of it (so an abnormal
disconnect right after login can't leave the cursor stuck at its old
value forever -- see simple_server.py's connection-close save).
"""
from __future__ import annotations

import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import news as news_store
from command_settings import CommandSettings
from logon_events.news import news_lines as _login_news_lines


def _player(name='Rulan', last_read=None, news_show_all=False):
    player = MagicMock()
    player.name = name
    player.command_settings = CommandSettings()
    player.command_settings.news.show_all = news_show_all
    player.command_settings.news.last_read = (
        last_read.isoformat() if last_read else None
    )
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
        player = _player(last_read=datetime.datetime(2026, 7, 31))
        lines = _login_news_lines(self.ctx, player)
        self.assertTrue(any('Server Update' in line for line in lines))
        self.assertIn('Rulan', self._current_items()[0]['seen_by'])

    def test_not_shown_again_next_login_new_only(self):
        # First login marks it seen via seen_by -- news_show_all=False
        # path already relied on is_new_since() plus is_visible().
        player = _player(last_read=datetime.datetime(2026, 7, 31))
        _login_news_lines(self.ctx, player)
        player.command_settings.news.last_read = datetime.datetime(2026, 8, 2).isoformat()
        lines = _login_news_lines(self.ctx, player)
        self.assertEqual(lines, [])

    def test_not_shown_again_next_login_show_all(self):
        # Regression: news_show_all=True bypasses is_new_since(), so
        # this path used to only rely on seen_by. last_played now
        # backstops it even if seen_by somehow didn't persist.
        player = _player(last_read=datetime.datetime(2026, 7, 31), news_show_all=True)
        _login_news_lines(self.ctx, player)
        items = self._current_items()
        items[0]['seen_by'] = []  # simulate seen_by never having stuck
        news_store.save_news(items)
        player.command_settings.news.last_read = datetime.datetime(2026, 8, 2).isoformat()
        lines = _login_news_lines(self.ctx, player)
        self.assertEqual(lines, [])

    def test_still_shown_if_never_logged_in_since_posting_show_all(self):
        player = _player(last_read=datetime.datetime(2026, 7, 15), news_show_all=True)
        lines = _login_news_lines(self.ctx, player)
        self.assertTrue(any('Server Update' in line for line in lines))

    def test_last_read_cursor_advances_and_is_force_saved(self):
        # The cursor moves forward on every login (not just when there's
        # something new to show), and player.save(force=True) is called
        # immediately -- durability that doesn't depend on a later clean
        # quit or the simple_server.py connection-close save.
        player = _player(last_read=datetime.datetime(2026, 7, 31))
        before = player.command_settings.news.last_read
        _login_news_lines(self.ctx, player)
        after = player.command_settings.news.last_read
        self.assertNotEqual(before, after)
        self.assertTrue(player.unsaved_changes)
        player.save.assert_called_once_with(force=True)

    def test_permanent_item_not_reshown_after_cursor_advances(self):
        # Regression for the reported bug: a 'permanent' item has no
        # seen_by/last_played backstop like 'once' items do, so it relies
        # entirely on the last_read cursor advancing and sticking.
        news_store.save_news([{
            'id': 2, 'title': 'Server Rules', 'body': ['be nice'],
            'author': 'admin', 'lifetime': 'permanent',
            'posted_at': '2026-08-10T00:00:00',
        }])
        player = _player(last_read=datetime.datetime(2026, 8, 1))
        lines = _login_news_lines(self.ctx, player)
        self.assertTrue(any('Server Rules' in line for line in lines))

        lines = _login_news_lines(self.ctx, player)
        self.assertEqual(lines, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
