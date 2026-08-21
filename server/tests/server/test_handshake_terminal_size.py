"""tests/server/test_handshake_terminal_size.py

Regression test for Server._handshake() applying a JSON client's reported
terminal size to ctx.player.client_settings. Before this, ANSI/JSON clients
(tada_client.py) never reported their real window size, so every non-
PETSCII connection silently inherited ClientSettings' 40x25 default
regardless of the player's actual terminal width.
"""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from simple_server import Server


def _ctx():
    ctx = MagicMock()
    ctx.player.client_settings.screen_columns = 40
    ctx.player.client_settings.screen_rows = 25
    ctx.send = AsyncMock()
    ctx.writer = MagicMock()
    ctx.reader = MagicMock()
    return ctx


class TestHandshakeAppliesReportedTerminalSize(unittest.IsolatedAsyncioTestCase):

    async def test_columns_and_rows_applied(self):
        server = Server('127.0.0.1', port=0)
        server.send_message = AsyncMock()
        server.receive_message = AsyncMock(return_value={
            'server_id': 'test_server', 'server_key': 'test_key',
            'protocol_version': 1, 'translation': 'ANSI',
            'columns': 132, 'rows': 50,
        })
        ctx = _ctx()

        result = await server._handshake(ctx)

        self.assertTrue(result)
        self.assertEqual(ctx.player.client_settings.screen_columns, 132)
        self.assertEqual(ctx.player.client_settings.screen_rows, 50)

    async def test_missing_columns_keeps_default(self):
        server = Server('127.0.0.1', port=0)
        server.send_message = AsyncMock()
        server.receive_message = AsyncMock(return_value={
            'server_id': 'test_server', 'server_key': 'test_key',
            'protocol_version': 1, 'translation': 'ANSI',
        })
        ctx = _ctx()

        result = await server._handshake(ctx)

        self.assertTrue(result)
        self.assertEqual(ctx.player.client_settings.screen_columns, 40)
        self.assertEqual(ctx.player.client_settings.screen_rows, 25)

    async def test_out_of_range_columns_ignored(self):
        server = Server('127.0.0.1', port=0)
        server.send_message = AsyncMock()
        server.receive_message = AsyncMock(return_value={
            'server_id': 'test_server', 'server_key': 'test_key',
            'protocol_version': 1, 'translation': 'ANSI',
            'columns': 9999, 'rows': 2,
        })
        ctx = _ctx()

        await server._handshake(ctx)

        self.assertEqual(ctx.player.client_settings.screen_columns, 40)
        self.assertEqual(ctx.player.client_settings.screen_rows, 25)

    async def test_columns_beyond_prefs_custom_max_ignored(self):
        # Matches commands/prefs.py's _MAX_COLS/_MAX_ROWS -- a client
        # reporting a size wider/taller than the "Custom" client type would
        # ever accept (e.g. a maximized modern terminal) must not produce a
        # stored value manual entry would reject.
        server = Server('127.0.0.1', port=0)
        server.send_message = AsyncMock()
        server.receive_message = AsyncMock(return_value={
            'server_id': 'test_server', 'server_key': 'test_key',
            'protocol_version': 1, 'translation': 'ANSI',
            'columns': 200, 'rows': 70,
        })
        ctx = _ctx()

        await server._handshake(ctx)

        self.assertEqual(ctx.player.client_settings.screen_columns, 40)
        self.assertEqual(ctx.player.client_settings.screen_rows, 25)


if __name__ == '__main__':
    unittest.main(verbosity=2)
