"""tests/test_news_command.py

Unit tests for commands/news.py -- the in-game NEWS command surface.

Run with:
    python -m pytest tests/test_news_command.py -v
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import news as news_store
from commands.news import NewsCommand
from flags import PlayerFlags


def run(coro):
    return asyncio.run(coro)


class _FakePlayer:
    def __init__(self, name='alexa', admin=False):
        self.name = name
        self._admin = admin

    def query_flag(self, flag):
        if flag == PlayerFlags.ADMIN:
            return self._admin
        return False


def make_ctx(player=None, prompts=None):
    ctx = MagicMock()
    ctx.player = player or _FakePlayer()
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(side_effect=prompts or [])
    return ctx


class NewsCommandTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'news.json'
        patcher = patch.object(news_store, 'NEWS_FILE', self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def _seed(self, items):
        news_store.save_news(items, self.path)


class TestList(NewsCommandTestCase):
    def test_no_news_message(self):
        ctx = make_ctx()
        run(NewsCommand().execute(ctx))
        sent = str(ctx.send.call_args)
        self.assertIn('No news', sent)

    def test_lists_visible_items(self):
        self._seed([{'id': 1, 'title': 'Patch Notes', 'body': ['x'],
                      'lifetime': 'permanent', 'posted_at': '2026-01-01T00:00:00'}])
        ctx = make_ctx()
        run(NewsCommand().execute(ctx))
        sent = str(ctx.send.call_args)
        self.assertIn('Patch Notes', sent)


class TestReadOne(NewsCommandTestCase):
    def test_read_marks_once_item_seen(self):
        self._seed([{'id': 7, 'title': 'Welcome', 'body': ['hi'], 'lifetime': 'once',
                      'posted_at': '2026-01-01T00:00:00', 'seen_by': []}])
        ctx = make_ctx()
        run(NewsCommand().execute(ctx, '7'))
        items = news_store.load_news(self.path)
        self.assertIn('alexa', items[0]['seen_by'])

    def test_unknown_id_reports_error(self):
        ctx = make_ctx()
        result = run(NewsCommand().execute(ctx, '99'))
        self.assertFalse(result.success)


class TestAdminGating(NewsCommandTestCase):
    def test_non_admin_cannot_post(self):
        ctx = make_ctx(player=_FakePlayer(admin=False))
        result = run(NewsCommand().execute(ctx, 'post'))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'permission_denied')

    def test_non_admin_cannot_delete(self):
        self._seed([{'id': 1, 'title': 'X', 'body': [], 'lifetime': 'permanent'}])
        ctx = make_ctx(player=_FakePlayer(admin=False))
        result = run(NewsCommand().execute(ctx, 'delete', '1'))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'permission_denied')

    def test_admin_can_post(self):
        ctx = make_ctx(
            player=_FakePlayer(admin=True),
            prompts=['Server Maintenance', 'permanent', 'We will be down Friday.', 'END'],
        )
        result = run(NewsCommand().execute(ctx, 'post'))
        self.assertTrue(result.success)
        items = news_store.load_news(self.path)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], 'Server Maintenance')
        self.assertEqual(items[0]['body'], ['We will be down Friday.'])
        self.assertEqual(items[0]['author'], 'alexa')

    def test_admin_can_delete(self):
        self._seed([{'id': 1, 'title': 'X', 'body': [], 'lifetime': 'permanent'}])
        ctx = make_ctx(player=_FakePlayer(admin=True))
        result = run(NewsCommand().execute(ctx, 'delete', '1'))
        self.assertTrue(result.success)
        self.assertEqual(news_store.load_news(self.path), [])


if __name__ == '__main__':
    unittest.main()
