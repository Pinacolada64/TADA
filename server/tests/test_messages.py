"""tests/test_messages.py

Unit tests for messages.py: loading server/messages.json (recovered SPUR
message-file flavor text) and displaying it by number, replacing ad-hoc
duplicated flavor text embedded directly in level/quest data.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from messages import get_message, load_messages, send_message


def _ctx(messages):
    server = MagicMock()
    server.messages = messages
    ctx = MagicMock()
    ctx.server = server
    ctx.send = AsyncMock()
    return ctx


class TestLoadMessages(unittest.TestCase):
    def test_loads_real_file(self):
        path = Path(__file__).parent.parent / 'messages.json'
        messages = load_messages(str(path))
        self.assertIn(18, messages)
        self.assertIn('incredibly powerful gust of wind', messages[18][0])

    def test_missing_file_returns_empty_dict(self):
        self.assertEqual(load_messages('/no/such/file.json'), {})

    def test_keys_coerced_to_int(self):
        import tempfile
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump({'5': ['hello']}, f)
            path = f.name
        try:
            messages = load_messages(path)
            self.assertEqual(messages, {5: ['hello']})
        finally:
            Path(path).unlink()


class TestGetMessage(unittest.TestCase):
    def test_returns_paragraphs(self):
        ctx = _ctx({7: ['para one', 'para two']})
        self.assertEqual(get_message(ctx, 7), ['para one', 'para two'])

    def test_missing_number_returns_none(self):
        ctx = _ctx({7: ['para one']})
        self.assertIsNone(get_message(ctx, 99))

    def test_no_messages_loaded_returns_none(self):
        ctx = _ctx({})
        self.assertIsNone(get_message(ctx, 7))


class TestSendMessage(unittest.IsolatedAsyncioTestCase):
    async def test_sends_paragraphs_and_returns_true(self):
        ctx = _ctx({18: ['para one', 'para two']})
        result = await send_message(ctx, 18)
        self.assertTrue(result)
        ctx.send.assert_awaited_once_with(['para one', 'para two'])

    async def test_missing_number_returns_false_and_does_not_send(self):
        ctx = _ctx({18: ['para one']})
        result = await send_message(ctx, 99)
        self.assertFalse(result)
        ctx.send.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
