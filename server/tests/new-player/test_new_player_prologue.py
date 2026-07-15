"""tests/test_new_player_prologue.py

Regression test: SPUR's own scene-setting intro (messages.json #9,
recovered verbatim from SPUR-data/SPUR Messages.txt) was never actually
shown anywhere -- Ryan pointed out it's background lore that belongs
before character creation starts, not TADA-specific setup instructions.

Also covers a real gap found while wiring this in: messages.py's
get_message() accessed ctx.server directly (not defensively), raising
AttributeError for any ctx without a .server at all instead of just
returning None -- same class of bug as the nested-getattr() fix
elsewhere in this codebase (editplayer.py).

Run with:
    python -m pytest tests/test_new_player_prologue.py -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from commands.new_player import _prologue
from messages import get_message


class _Ctx:
    def __init__(self, server=None):
        self.sent: list = []
        self.server = server

    async def send(self, *args):
        self.sent.extend(args)

    def _flat(self) -> str:
        out = []
        for item in self.sent:
            if isinstance(item, (list, tuple)):
                out.extend(str(x) for x in item)
            else:
                out.append(str(item))
        return '\n'.join(out)


class TestPrologueShowsMessageNine(unittest.IsolatedAsyncioTestCase):

    async def test_message_nine_shown_before_tada_setup_text(self):
        server = MagicMock()
        server.messages = {9: ['Welcome to the Land of SPUR!', 'Second paragraph.']}
        ctx = _Ctx(server=server)

        await _prologue(ctx)

        text = ctx._flat()
        self.assertIn('Welcome to the Land of SPUR!', text)
        lore_idx  = text.index('Welcome to the Land of SPUR!')
        setup_idx = text.index("Totally Awesome Dungeon Adventure")
        self.assertLess(lore_idx, setup_idx)

    async def test_missing_server_does_not_crash(self):
        """A ctx with no .server at all (some test fixtures) must not
        crash _prologue() -- message #9 is just silently skipped."""
        ctx = _Ctx(server=None)
        ok = await _prologue(ctx)
        self.assertTrue(ok)
        self.assertIn("Totally Awesome Dungeon Adventure", ctx._flat())


class TestGetMessageDefensive(unittest.TestCase):

    def test_missing_server_attribute_entirely_returns_none(self):
        ctx = MagicMock(spec=[])   # no .server attribute at all
        self.assertIsNone(get_message(ctx, 9))

    def test_server_present_but_no_messages_returns_none(self):
        ctx = MagicMock()
        ctx.server = MagicMock(spec=[])   # .server exists, no .messages
        self.assertIsNone(get_message(ctx, 9))

    def test_found_message_returns_paragraphs(self):
        ctx = MagicMock()
        ctx.server.messages = {9: ['para one', 'para two']}
        self.assertEqual(get_message(ctx, 9), ['para one', 'para two'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
