"""tests/annex/test_message_board.py

Covers annex/main.py's _message_board_2 -- SPUR.ANNEX.S routes this menu
slot to message #14 ("Shields in Monster Combat"), the in-game readable
version of the shield-block formula combat/resolution.py's
monster_attacks() implements. The rest of the Annex is still stubbed
out; this is the one slot wired so far.
"""
from __future__ import annotations

import json
import os
import unittest

from annex.main import _message_board_2


class _FakeServer:
    def __init__(self, messages=None):
        if messages is not None:
            self.messages = messages
            return
        path = os.path.join(os.path.dirname(__file__), '..', '..', 'messages.json')
        with open(path) as f:
            self.messages = {int(k): v for k, v in json.load(f).items()}


class _FakeCtx:
    def __init__(self, messages=None):
        self.server = _FakeServer(messages)
        self.sent: list = []

    async def send(self, *args):
        for a in args:
            if isinstance(a, list):
                self.sent.extend(a)
            else:
                self.sent.append(a)

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestMessageBoard2(unittest.IsolatedAsyncioTestCase):
    async def test_shows_shield_message(self):
        ctx = _FakeCtx()
        await _message_board_2(ctx)
        flat = ctx._flat()
        self.assertIn('Shields in Monster Combat', flat)
        self.assertIn('Formal shield training', flat)

    async def test_falls_back_when_message_missing(self):
        ctx = _FakeCtx(messages={})
        await _message_board_2(ctx)
        self.assertIn('(Message board not yet available.)', ctx._flat())


if __name__ == '__main__':
    unittest.main(verbosity=2)
