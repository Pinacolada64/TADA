"""tests/client/test_tada_client_exact_width_line.py

Regression test for a real bug reported live: when a server-formatted line
(e.g. a full-width box-drawing border) exactly filled tada_client.py's
output pane column width, a blank line appeared below it in the scrollback.

Root cause: prompt_toolkit's wrap_lines=True rendering gives any line whose
length exactly equals the window width a wrapped continuation row --
structurally, regardless of cursor placement -- and that continuation row
has no characters in it, so it renders as a genuinely blank line. Confirmed
live: PREFS reported "Custom (39 rows x 100 columns)" -- the server had
negotiated exactly the client's real terminal width, so frame_text()'s
box-drawing borders (sized to screen_columns on the nose, see
tada_utilities.py) landed exactly on the window's rendered width.

First attempt patched already-formatted lines back apart client-side
(splitting the last character of an exact-width line onto its own line)
-- that did stop the blank row, but the moved character then showed up
alone at the start of the next line, which read as its own bug ("the
table border wraps to the first column of the next line").

Fixed at the source instead: _login() now reports one column narrower
than the real terminal width during the handshake (server_key/columns
init message), so every line the server wraps or draws to screen_columns
-- including borders -- is strictly narrower than the real window and can
never hit the exact-width case that trips the prompt_toolkit artifact.

Run with:
    python -m pytest tests/client/test_tada_client_exact_width_line.py -v
"""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import tada_client as tc


class _FakeReader:
    """Minimal reader satisfying _login() through the handshake only --
    tests here just need the 'init' message that carries 'columns', so
    the connection is left hanging after the terminal-negotiation prompt
    (never answered) rather than driving a full login."""
    def __init__(self):
        frame = json.dumps({
            'lines': ['Handshake successful.'], 'mode': 'login',
        }).encode('utf-8') + b'\n'
        self._frames = [frame]

    async def readline(self):
        if self._frames:
            return self._frames.pop(0)
        return b''


def _sent_init_payload(writer: MagicMock) -> dict:
    for call in writer.write.call_args_list:
        payload = json.loads(call.args[0].decode('utf-8').strip())
        if payload.get('mode') == 'init':
            return payload
    raise AssertionError('no init message was sent')


class TestHandshakeReportsNarrowerThanRealWidth(unittest.TestCase):

    def _run_login(self) -> dict:
        reader = _FakeReader()
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        with patch('shutil.get_terminal_size', return_value=MagicMock(columns=100, lines=39)):
            asyncio.run(tc._login(reader, writer, output_buffer, state, app, 'alexa', 'hunter2'))

        return _sent_init_payload(writer)

    def test_reports_one_column_narrower_than_real_terminal_width(self):
        payload = self._run_login()
        self.assertEqual(payload['columns'], 99)
        self.assertEqual(payload['rows'], 39)

    def test_never_reports_zero_or_negative_columns(self):
        reader = _FakeReader()
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        with patch('shutil.get_terminal_size', return_value=MagicMock(columns=1, lines=25)):
            asyncio.run(tc._login(reader, writer, output_buffer, state, app, 'alexa', 'hunter2'))

        payload = _sent_init_payload(writer)
        self.assertEqual(payload['columns'], 1)


if __name__ == '__main__':
    unittest.main()
