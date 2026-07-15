"""tests/test_tada_client_quit.py

Regression test for a real reported bug: typing 'quit' in tada_client.py
didn't actually disconnect. Root cause -- _input_loop() special-cased
'quit'/'exit'/'/quit' by sending 'quit' and immediately breaking out of
the input loop, never sending the "Y" that commands/quit.py's
QuitCommand.execute() then blocks forever waiting for (it asks a "Leave
SPUR [Y/N]?" confirmation and only sets data={'quit': True} -- which
makes the server actually close the connection -- once answered). The
server sat in ctx.prompt() waiting for that answer while this client's
_receive_loop sat waiting for more server output that would never come:
a deadlock, with no crash and no clean exit either.

Fix: 'quit' is now sent through like any other command, so the
confirmation prompt round-trips normally and the player's next line
('Y' or 'N') goes through too.

Run with:
    python -m pytest tests/test_tada_client_quit.py -v
"""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from prompt_toolkit.buffer import Buffer

import tada_client as tc


def _make_writer():
    writer = MagicMock()
    writer.write = MagicMock()
    writer.drain = AsyncMock()
    return writer


def _sent_texts(writer) -> list[str]:
    """Decode every JSON payload written to the mock writer's .write() calls."""
    out = []
    for call in writer.write.call_args_list:
        data = call.args[0]
        obj = json.loads(data.decode('utf-8').strip())
        out.append(obj.get('text'))
    return out


class TestInputLoopQuit(unittest.IsolatedAsyncioTestCase):

    async def test_quit_is_sent_without_breaking_the_loop(self):
        """The old bug: typing 'quit' sent it, then broke immediately --
        so a subsequent 'Y' confirmation was never sent at all."""
        writer = _make_writer()
        state = tc.ClientState()
        state.connected = True
        app = MagicMock()
        output_buffer = Buffer(name='output', read_only=True)

        with patch.object(tc, '_get_input', new=AsyncMock(side_effect=['quit', 'Y', None])):
            await tc._input_loop(writer, output_buffer, state, app)

        texts = _sent_texts(writer)
        self.assertEqual(texts, ['quit', 'Y'])

    async def test_quit_does_not_call_app_exit_before_confirmation(self):
        """app.exit() should only run once the input loop actually ends
        (state.connected goes False or _get_input returns None) -- not
        immediately after sending 'quit'."""
        writer = _make_writer()
        state = tc.ClientState()
        state.connected = True
        app = MagicMock()
        output_buffer = Buffer(name='output', read_only=True)

        calls: list[str] = []

        async def fake_get_input(_app):
            if not calls:
                calls.append('quit')
                return 'quit'
            if len(calls) == 1:
                calls.append('Y')
                self.assertFalse(app.exit.called, "app.exit() called before 'Y' was sent")
                return 'Y'
            return None

        with patch.object(tc, '_get_input', new=fake_get_input):
            await tc._input_loop(writer, output_buffer, state, app)

        app.exit.assert_called_once()

    async def test_normal_commands_still_sent_and_loop_continues(self):
        writer = _make_writer()
        state = tc.ClientState()
        state.connected = True
        app = MagicMock()
        output_buffer = Buffer(name='output', read_only=True)

        with patch.object(tc, '_get_input', new=AsyncMock(side_effect=['look', 'inv', None])):
            await tc._input_loop(writer, output_buffer, state, app)

        texts = _sent_texts(writer)
        self.assertEqual(texts, ['look', 'inv'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
