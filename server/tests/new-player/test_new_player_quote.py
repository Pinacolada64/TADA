"""tests/test_new_player_quote.py

Covers commands/new_player.py's _choose_quote() -- the character-creation
step tying SPUR.LOGON.S:410,618-624's "quote" prompt into main_flow(). This
differs from the in-game QuoteCommand._write() (commands/quote.py) in one
key way: blank input here is an explicit choice to be silent ("Ok, you
will be silent..", quote left None), not a "No change.." cancel.

Also covers the "$" preview/confirm loop shared with QuoteCommand via
commands.quote.confirm_dollar_quote(), and _final_review()'s "Quote" line.

Run with:
    python -m pytest tests/test_new_player_quote.py -v
"""
from __future__ import annotations

import unittest

from commands.new_player import _CreationAbandoned, _choose_quote
from player import Player


class _FakeCtx:
    def __init__(self, responses, player):
        self._q = list(responses)
        self.sent: list = []
        self.player = player

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        return '\n'.join(str(x) for x in self.sent)


class TestChooseQuote(unittest.IsolatedAsyncioTestCase):

    async def test_blank_means_silent(self):
        player = Player(name='Rulan')
        ctx = _FakeCtx([''], player)
        ok = await _choose_quote(ctx)
        self.assertTrue(ok)
        self.assertIsNone(player.quote)
        self.assertIn('Ok, you will be silent..', ctx._flat())

    async def test_sets_quote_without_dollar(self):
        player = Player(name='Rulan')
        ctx = _FakeCtx(['Trespassers will be shot.'], player)
        ok = await _choose_quote(ctx)
        self.assertTrue(ok)
        self.assertEqual(player.quote, 'Trespassers will be shot.')
        self.assertNotIn('That will look like:', ctx._flat())

    async def test_too_long_reprompts(self):
        player = Player(name='Rulan')
        ctx = _FakeCtx(['x' * 61, 'short'], player)
        ok = await _choose_quote(ctx)
        self.assertTrue(ok)
        self.assertIn('TOO LONG!', ctx._flat())
        self.assertEqual(player.quote, 'short')

    async def test_dollar_quote_shows_preview_and_accepts(self):
        player = Player(name='Rulan')
        ctx = _FakeCtx(['Hello $, welcome!', 'y'], player)
        ok = await _choose_quote(ctx)
        self.assertTrue(ok)
        self.assertEqual(player.quote, 'Hello $, welcome!')
        flat = ctx._flat()
        self.assertIn('That will look like:', flat)
        self.assertIn("'Hello Rulan, welcome!'", flat)

    async def test_dollar_quote_rejected_reprompts(self):
        player = Player(name='Rulan')
        ctx = _FakeCtx(['Bad $ placement', 'n', 'Better, $!', 'y'], player)
        ok = await _choose_quote(ctx)
        self.assertTrue(ok)
        self.assertEqual(player.quote, 'Better, $!')

    async def test_disconnect_during_prompt(self):
        # A disconnect (or typed 'quit'/'q') now raises _CreationAbandoned,
        # caught once centrally in main_flow() -- see _prompt_or_quit().
        player = Player(name='Rulan')
        ctx = _FakeCtx([], player)
        with self.assertRaises(_CreationAbandoned):
            await _choose_quote(ctx)

    async def test_disconnect_during_confirm(self):
        player = Player(name='Rulan')
        ctx = _FakeCtx(['Hello $, welcome!'], player)
        ok = await _choose_quote(ctx)
        self.assertFalse(ok)
        self.assertIsNone(player.quote)


if __name__ == '__main__':
    unittest.main(verbosity=2)
