"""tests/test_terminal_negotiation.py

Regression tests for Server._negotiate_terminal()'s ANSI/plain-text branch.

An alpha tester reported being unsure which option (A/P/Q) to pick at the
"Terminal type" prompt. Added:
  - 'HA'/'HP'/'HQ' help text for each option (matching the h<key> convention
    used elsewhere, e.g. commands/prefs.py's prefs_menu()).
  - A 'C' color test: shows colored lines and asks Y/N whether the player
    can see color, then sets ANSI or Plain accordingly.
  - A note directing real Commodore 64/128 users to the PETSCII port
    instead of this ANSI/plain-text negotiation.

Run with:
    python -m pytest tests/test_terminal_negotiation.py -v
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

for _mod in ('network_context', 'net_common', 'simple_server'):
    sys.modules.pop(_mod, None)

from simple_server import Server, PETSCII_PORT
from terminal import Translation


def _ctx(responses, translation=Translation.ANSI):
    ctx = MagicMock()
    ctx.player.client_settings.translation = translation
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(side_effect=responses)
    ctx.writer = MagicMock()
    return ctx


def _flat_sent(ctx) -> str:
    out = []
    for call in ctx.send.call_args_list:
        for arg in call.args:
            if isinstance(arg, (list, tuple)):
                out.extend(str(x) for x in arg)
            else:
                out.append(str(arg))
    return '\n'.join(out)


class TestTerminalNegotiationBasics(unittest.IsolatedAsyncioTestCase):

    async def test_mentions_petscii_port_for_commodore_users(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['A'])
        result = await server._negotiate_terminal(ctx)
        self.assertTrue(result)
        text = _flat_sent(ctx)
        self.assertIn(str(PETSCII_PORT), text)
        self.assertIn('Commodore', text)

    async def test_a_sets_ansi(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['A'])
        await server._negotiate_terminal(ctx)
        self.assertEqual(ctx.player.client_settings.translation, Translation.ANSI)

    async def test_p_sets_plain(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['P'])
        await server._negotiate_terminal(ctx)
        self.assertEqual(ctx.player.client_settings.translation, Translation.ASCII)

    async def test_q_disconnects(self):
        server = Server('127.0.0.1', port=0)
        server._graceful_close = AsyncMock()
        ctx = _ctx(['Q'])
        result = await server._negotiate_terminal(ctx)
        self.assertFalse(result)


class TestTerminalNegotiationHelp(unittest.IsolatedAsyncioTestCase):

    async def test_ha_shows_help_then_reprompts(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['HA', 'A'])
        result = await server._negotiate_terminal(ctx)
        self.assertTrue(result)
        text = _flat_sent(ctx)
        self.assertIn('ANSI color mode uses', text)
        self.assertEqual(ctx.prompt.await_count, 2)

    async def test_hp_shows_help_then_reprompts(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['HP', 'A'])
        await server._negotiate_terminal(ctx)
        text = _flat_sent(ctx)
        self.assertIn('Plain text mode strips', text)

    async def test_hq_shows_help_then_reprompts(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['HQ', 'A'])
        await server._negotiate_terminal(ctx)
        text = _flat_sent(ctx)
        self.assertIn('Disconnects immediately', text)

    async def test_help_does_not_set_translation(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['HA', 'A'], translation=Translation.ASCII)
        await server._negotiate_terminal(ctx)
        # Only the second answer ('A') should have taken effect.
        self.assertEqual(ctx.player.client_settings.translation, Translation.ANSI)


class TestColorTest(unittest.IsolatedAsyncioTestCase):

    async def test_color_test_shows_colored_lines(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['C', 'Y'])
        await server._negotiate_terminal(ctx)
        text = _flat_sent(ctx)
        self.assertIn('RED', text)
        self.assertIn('GREEN', text)
        self.assertIn('BLUE', text)

    async def test_color_test_yes_sets_ansi(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['C', 'Y'])
        await server._negotiate_terminal(ctx)
        self.assertEqual(ctx.player.client_settings.translation, Translation.ANSI)

    async def test_color_test_no_sets_plain(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['C', 'N'])
        await server._negotiate_terminal(ctx)
        self.assertEqual(ctx.player.client_settings.translation, Translation.ASCII)

    async def test_color_test_disconnect_returns_false(self):
        server = Server('127.0.0.1', port=0)
        ctx = _ctx(['C', None])
        result = await server._negotiate_terminal(ctx)
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
