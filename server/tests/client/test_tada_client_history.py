"""tests/client/test_tada_client_history.py

Regression coverage for tada_client.py's '^N'/'^^' command-history recall
(Ryan's request, 2026-08-19): '^N' resends the Nth-most-recent command
(0 = the last one sent), and '^^' is an alias for '^0'.

Run with:
    python -m pytest tests/client/test_tada_client_history.py -v
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, MagicMock

from prompt_toolkit.buffer import Buffer
from unittest.mock import patch

import tada_client as tc


def _make_writer():
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    return writer


def _sent_texts(writer) -> list[str]:
    out = []
    for call in writer.write.call_args_list:
        data = call.args[0]
        obj = json.loads(data.decode('utf-8').strip())
        out.append(obj.get('text'))
    return out


class TestHistoryRecall(unittest.IsolatedAsyncioTestCase):

    async def test_caret_caret_repeats_most_recent_command(self):
        writer = _make_writer()
        state = tc.ClientState()
        state.connected = True
        app = MagicMock()
        output_buffer = Buffer(name='output', read_only=True)

        with patch.object(tc, '_get_input', new=AsyncMock(side_effect=['get guide', '^^', None])):
            await tc._input_loop(writer, output_buffer, state, app)

        self.assertEqual(_sent_texts(writer), ['get guide', 'get guide'])

    async def test_caret_n_indexes_back_from_most_recent(self):
        writer = _make_writer()
        state = tc.ClientState()
        state.connected = True
        app = MagicMock()
        output_buffer = Buffer(name='output', read_only=True)

        # history after 'look', 'i': ['i', 'look'] (most-recent first) --
        # '^1' should recall 'look', not 'i'.
        with patch.object(tc, '_get_input', new=AsyncMock(side_effect=['look', 'i', '^1', None])):
            await tc._input_loop(writer, output_buffer, state, app)

        self.assertEqual(_sent_texts(writer), ['look', 'i', 'look'])

    async def test_out_of_range_recall_sends_nothing(self):
        writer = _make_writer()
        state = tc.ClientState()
        state.connected = True
        app = MagicMock()
        output_buffer = Buffer(name='output', read_only=True)

        # No history yet -- '^0' has nothing to recall, must not send
        # the literal '^0' text to the server.
        with patch.object(tc, '_get_input', new=AsyncMock(side_effect=['^0', 'look', None])):
            await tc._input_loop(writer, output_buffer, state, app)

        self.assertEqual(_sent_texts(writer), ['look'])

    async def test_repeated_recalls_keep_repeating_the_original(self):
        """Recalling twice in a row should repeat the same original
        command both times, not recurse into repeating '^^' itself --
        the resolved text, not the trigger, is what gets pushed back
        into history."""
        writer = _make_writer()
        state = tc.ClientState()
        state.connected = True
        app = MagicMock()
        output_buffer = Buffer(name='output', read_only=True)

        with patch.object(tc, '_get_input',
                           new=AsyncMock(side_effect=['get guide', '^^', '^^', None])):
            await tc._input_loop(writer, output_buffer, state, app)

        self.assertEqual(_sent_texts(writer), ['get guide', 'get guide', 'get guide'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
