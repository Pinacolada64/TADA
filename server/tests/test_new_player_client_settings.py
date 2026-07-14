"""tests/test_new_player_client_settings.py

Regression test: commands/new_player.py's _choose_client_settings() menu
gained a hint for unsure players ("you are probably connecting using the
TADA client"), while noting real Commodore 64/128 terminals are
supported too.

Run with:
    python -m pytest tests/test_new_player_client_settings.py -v
"""
from __future__ import annotations

import unittest

from commands.new_player import _choose_client_settings


class _FakeClientSettings:
    screen_columns = 80
    screen_rows    = 25
    translation    = None
    border_style   = 'single'


class _FakePlayer:
    def __init__(self):
        self.client_settings = _FakeClientSettings()


class _FakeCtx:
    def __init__(self, responses):
        self._q = list(responses)
        self.sent: list = []
        self.player = _FakePlayer()

    async def send(self, *args):
        for a in args:
            self.sent.append(a)

    async def prompt(self, prompt_text: str = '', preamble_lines=None):
        if preamble_lines:
            self.sent.extend(preamble_lines)
        return self._q.pop(0) if self._q else None

    def _flat(self) -> str:
        out = []
        for item in self.sent:
            if isinstance(item, (list, tuple)):
                out.extend(str(x) for x in item)
            else:
                out.append(str(item))
        return '\n'.join(out)


class TestChooseClientSettingsHelp(unittest.IsolatedAsyncioTestCase):

    async def test_mentions_tada_client_for_unsure_players(self):
        ctx = _FakeCtx(['4'])
        await _choose_client_settings(ctx)
        text = ctx._flat()
        self.assertIn('TADA client', text)

    async def test_mentions_commodore_terminals_supported(self):
        ctx = _FakeCtx(['4'])
        await _choose_client_settings(ctx)
        text = ctx._flat()
        self.assertIn('Commodore 64/128', text)

    async def test_selecting_tada_client_still_works(self):
        ctx = _FakeCtx(['4'])
        result = await _choose_client_settings(ctx)
        self.assertTrue(result)
        self.assertEqual(ctx.player.client_settings.translation, 'ANSI')


if __name__ == '__main__':
    unittest.main(verbosity=2)
