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
        self.return_key = 'Enter'

    def query_flag(self, flag):
        if flag == PlayerFlags.ADMIN:
            return self._admin
        return False


def make_ctx(player=None, prompts=None):
    ctx = MagicMock()
    ctx.player = player or _FakePlayer()
    ctx.client.virtual_location = None
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
        ctx = make_ctx(prompts=[''])
        run(NewsCommand().execute(ctx))
        sent = str(ctx.prompt.call_args)
        self.assertIn('Patch Notes', sent)

    def test_listing_shows_date_before_title(self):
        self._seed([{'id': 1, 'title': 'Patch Notes', 'body': ['x'],
                      'lifetime': 'permanent', 'posted_at': '2026-01-01T00:00:00'}])
        ctx = make_ctx(prompts=[''])
        run(NewsCommand().execute(ctx))
        preamble = ctx.prompt.call_args.kwargs['preamble_lines']
        row = next(l for l in preamble if 'Patch Notes' in l)
        self.assertLess(row.index('2026-01-01'), row.index('Patch Notes'))

    def test_listing_has_header_row_and_rule(self):
        self._seed([{'id': 1, 'title': 'Patch Notes', 'body': ['x'],
                      'lifetime': 'permanent', 'posted_at': '2026-01-01T00:00:00'}])
        ctx = make_ctx(prompts=[''])
        run(NewsCommand().execute(ctx))
        preamble = ctx.prompt.call_args.kwargs['preamble_lines']
        self.assertIn('Num', ' '.join(preamble))
        self.assertIn('Date', ' '.join(preamble))
        self.assertIn('Title', ' '.join(preamble))
        # A rule line -- some run of a single repeated non-space character.
        self.assertTrue(any(
            len(set(l.strip())) == 1 and len(l.strip()) > 3 for l in preamble
        ))

    def test_blank_input_exits_the_listing_loop(self):
        self._seed([{'id': 1, 'title': 'Patch Notes', 'body': ['x'],
                      'lifetime': 'permanent', 'posted_at': '2026-01-01T00:00:00'}])
        ctx = make_ctx(prompts=[''])
        result = run(NewsCommand().execute(ctx))
        self.assertTrue(result.success)
        self.assertEqual(ctx.prompt.await_count, 1)

    def test_reading_an_item_returns_to_the_listing(self):
        self._seed([{'id': 1, 'title': 'Patch Notes', 'body': ['x'],
                      'lifetime': 'permanent', 'posted_at': '2026-01-01T00:00:00'}])
        ctx = make_ctx(prompts=['1', ''])
        run(NewsCommand().execute(ctx))
        # First prompt reads item 1, second exits -- listing redisplayed
        # in between means prompt() was called twice.
        self.assertEqual(ctx.prompt.await_count, 2)
        sent = str(ctx.send.call_args_list)
        self.assertIn('x', sent)   # the item body was actually shown

    def test_invalid_choice_stays_in_listing(self):
        self._seed([{'id': 1, 'title': 'Patch Notes', 'body': ['x'],
                      'lifetime': 'permanent', 'posted_at': '2026-01-01T00:00:00'}])
        ctx = make_ctx(prompts=['bogus', ''])
        run(NewsCommand().execute(ctx))
        self.assertEqual(ctx.prompt.await_count, 2)
        sent = str(ctx.send.call_args_list)
        self.assertIn('not a valid news id', sent)

    def test_virtual_location_set_while_listing(self):
        self._seed([{'id': 1, 'title': 'Patch Notes', 'body': ['x'],
                      'lifetime': 'permanent', 'posted_at': '2026-01-01T00:00:00'}])
        seen_location = {}

        async def _prompt(*a, **kw):
            seen_location['during'] = ctx.client.virtual_location
            return ''

        ctx = make_ctx()
        ctx.prompt = _prompt
        run(NewsCommand().execute(ctx))

        self.assertEqual(seen_location['during'], 'Reading news')
        self.assertIsNone(ctx.client.virtual_location)   # restored after

    def test_virtual_location_restored_to_prior_value(self):
        self._seed([{'id': 1, 'title': 'Patch Notes', 'body': ['x'],
                      'lifetime': 'permanent', 'posted_at': '2026-01-01T00:00:00'}])
        ctx = make_ctx(prompts=[''])
        ctx.client.virtual_location = 'somewhere else'
        run(NewsCommand().execute(ctx))
        self.assertEqual(ctx.client.virtual_location, 'somewhere else')

    def test_no_news_does_not_set_virtual_location(self):
        ctx = make_ctx()
        run(NewsCommand().execute(ctx))
        self.assertIsNone(ctx.client.virtual_location)


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
            prompts=['Server Maintenance', 'permanent', 'We will be down Friday.', '.s'],
        )
        result = run(NewsCommand().execute(ctx, 'post'))
        self.assertTrue(result.success)
        items = news_store.load_news(self.path)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], 'Server Maintenance')
        # body is now formatting.serialize_lines()'s output (structured
        # Line dicts), not plain strings -- see news.py's module docstring.
        self.assertEqual(items[0]['body'], [{'text': 'We will be down Friday.'}])
        self.assertEqual(items[0]['author'], 'alexa')

    def test_admin_can_delete(self):
        self._seed([{'id': 1, 'title': 'X', 'body': [], 'lifetime': 'permanent'}])
        ctx = make_ctx(player=_FakePlayer(admin=True))
        result = run(NewsCommand().execute(ctx, 'delete', '1'))
        self.assertTrue(result.success)
        self.assertEqual(news_store.load_news(self.path), [])


if __name__ == '__main__':
    unittest.main()
