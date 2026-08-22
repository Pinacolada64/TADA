"""tests/client/test_tada_client_login.py

Unit tests for tada_client.py's auto-login: --username/--password/
--translation flags (main()'s argparse handling) and _login()'s
handshake + 'connect <user> <pass>' send. Added alongside the fix that
made --username/--password actually skip interactive prompts and log a
character in automatically -- previously only --user existed (no
--password at all), so any non-interactive/scripted launch would always
block on a getpass.getpass() prompt no one was there to answer.
"""
from __future__ import annotations

import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import tada_client as tc


def _sent_payloads(writer: MagicMock) -> list[dict]:
    return [json.loads(call.args[0].decode('utf-8').strip())
            for call in writer.write.call_args_list]


class _FakeReader:
    """Feeds _login() a scripted sequence of server messages, one
    newline-delimited JSON frame per readline() call -- mirrors what the
    real server sends: a handshake acknowledgement, then the interactive
    "Terminal type [A/P/C/Q]" prompt _login() must answer before it may
    send 'connect ...' (see simple_server.py's _negotiate_terminal()).
    """
    def __init__(self, messages: list[dict] | None = None):
        default = [
            {'lines': ['Handshake successful.'], 'mode': 'login'},
            {'lines': ['', 'TADA — Terminal negotiation'], 'mode': 'login',
             'prompt': 'Terminal type [A/P/C/Q]'},
        ]
        self._frames = [json.dumps(m).encode('utf-8') + b'\n'
                        for m in (messages if messages is not None else default)]

    async def readline(self):
        if self._frames:
            return self._frames.pop(0)
        return b''


class TestLoginSendsCredentials(unittest.TestCase):
    def test_answers_terminal_negotiation_before_sending_connect(self):
        reader = _FakeReader()
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        asyncio.run(tc._login(reader, writer, output_buffer, state, app, 'alexa', 'hunter2'))

        payloads = _sent_payloads(writer)
        login_msgs = [p for p in payloads if p.get('mode') == 'login']
        # 'A' (answering the negotiation prompt) must be sent, and sent
        # *before* the connect command -- reversing this order is exactly
        # the bug this test guards against (server rejects 'connect ...'
        # as an unrecognized answer while still parked at the prompt).
        self.assertEqual([m['text'] for m in login_msgs], ['A', 'connect alexa hunter2'])

    def test_ascii_translation_answers_p(self):
        reader = _FakeReader()
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        asyncio.run(tc._login(reader, writer, output_buffer, state, app, 'alexa', 'hunter2',
                              translation='ASCII'))

        payloads = _sent_payloads(writer)
        login_msgs = [p for p in payloads if p.get('mode') == 'login']
        self.assertEqual(login_msgs[0]['text'], 'P')

    def test_guest_sends_bare_connect_guest_without_a_password(self):
        reader = _FakeReader()
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        asyncio.run(tc._login(reader, writer, output_buffer, state, app, 'guest', 'guest'))

        payloads = _sent_payloads(writer)
        connect_msgs = [p for p in payloads if p.get('mode') == 'login']
        self.assertEqual(connect_msgs[-1]['text'], 'connect guest')

    def test_translation_defaults_to_ansi_in_handshake(self):
        reader = _FakeReader()
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        asyncio.run(tc._login(reader, writer, output_buffer, state, app, 'alexa', 'hunter2'))

        payloads = _sent_payloads(writer)
        init_msgs = [p for p in payloads if p.get('mode') == 'init']
        self.assertEqual(init_msgs[0]['translation'], 'ANSI')

    def test_init_reports_real_terminal_size(self):
        # columns is one narrower than the real terminal, not the literal
        # value -- see test_tada_client_exact_width_line.py for why (a
        # server-formatted line landing exactly on the real window width
        # trips a prompt_toolkit rendering artifact). rows is unaffected.
        reader = _FakeReader()
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        with patch.object(tc.shutil, 'get_terminal_size',
                           return_value=os.terminal_size((132, 50))):
            asyncio.run(tc._login(reader, writer, output_buffer, state, app, 'alexa', 'hunter2'))

        payloads = _sent_payloads(writer)
        init_msgs = [p for p in payloads if p.get('mode') == 'init']
        self.assertEqual(init_msgs[0]['columns'], 131)
        self.assertEqual(init_msgs[0]['rows'], 50)

    def test_translation_is_passed_through_in_handshake(self):
        reader = _FakeReader()
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        asyncio.run(tc._login(reader, writer, output_buffer, state, app, 'alexa', 'hunter2',
                              translation='ASCII'))

        payloads = _sent_payloads(writer)
        init_msgs = [p for p in payloads if p.get('mode') == 'init']
        self.assertEqual(init_msgs[0]['translation'], 'ASCII')

    def test_returns_true_on_success(self):
        reader = _FakeReader()
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        result = asyncio.run(
            tc._login(reader, writer, output_buffer, state, app, 'alexa', 'hunter2'))
        self.assertTrue(result)

    def test_returns_false_if_disconnected_before_negotiation_prompt(self):
        reader = _FakeReader(messages=[])   # EOF immediately
        writer = MagicMock()
        writer.drain = AsyncMock()
        state = tc.ClientState()
        app = MagicMock()
        output_buffer = MagicMock()

        result = asyncio.run(
            tc._login(reader, writer, output_buffer, state, app, 'alexa', 'hunter2'))
        self.assertFalse(result)
        # Never got far enough to send credentials.
        payloads = _sent_payloads(writer)
        self.assertFalse(any(p.get('mode') == 'login' for p in payloads))


class TestMainCredentialResolution(unittest.TestCase):
    """main()'s argparse -> user_id/password/translation resolution --
    patches tc.run so no real connection is attempted, and asserts what
    it would have been called with."""

    def _run_main(self, argv):
        captured = {}

        async def _fake_run(host, port, user_id, password, debug=False, translation='ANSI'):
            captured.update(host=host, port=port, user_id=user_id,
                            password=password, debug=debug, translation=translation)

        with patch.object(tc, 'run', _fake_run), \
             patch('sys.argv', ['tada_client.py'] + argv):
            tc.main()
        return captured

    def test_username_and_password_together_skip_all_prompts(self):
        with patch('builtins.input') as mock_input, \
             patch.object(tc.getpass, 'getpass') as mock_getpass:
            captured = self._run_main(['--username', 'alexa', '--password', 'hunter2'])
        mock_input.assert_not_called()
        mock_getpass.assert_not_called()
        self.assertEqual(captured['user_id'], 'alexa')
        self.assertEqual(captured['password'], 'hunter2')

    def test_username_alone_prompts_for_password_only(self):
        with patch('builtins.input') as mock_input, \
             patch.object(tc.getpass, 'getpass', return_value='prompted') as mock_getpass:
            captured = self._run_main(['--username', 'alexa'])
        mock_input.assert_not_called()
        mock_getpass.assert_called_once()
        self.assertEqual(captured['user_id'], 'alexa')
        self.assertEqual(captured['password'], 'prompted')

    def test_guest_flag_skips_all_prompts(self):
        with patch('builtins.input') as mock_input, \
             patch.object(tc.getpass, 'getpass') as mock_getpass:
            captured = self._run_main(['--guest'])
        mock_input.assert_not_called()
        mock_getpass.assert_not_called()
        self.assertEqual(captured['user_id'], 'guest')
        self.assertEqual(captured['password'], 'guest')

    def test_translation_default_is_ansi(self):
        with patch('builtins.input'), patch.object(tc.getpass, 'getpass'):
            captured = self._run_main(['--username', 'alexa', '--password', 'x'])
        self.assertEqual(captured['translation'], 'ANSI')

    def test_translation_flag_is_passed_through(self):
        with patch('builtins.input'), patch.object(tc.getpass, 'getpass'):
            captured = self._run_main(
                ['--username', 'alexa', '--password', 'x', '--translation', 'ASCII'])
        self.assertEqual(captured['translation'], 'ASCII')

    def test_translation_flag_is_case_insensitive(self):
        with patch('builtins.input'), patch.object(tc.getpass, 'getpass'):
            captured = self._run_main(
                ['--username', 'alexa', '--password', 'x', '--translation', 'ascii'])
        self.assertEqual(captured['translation'], 'ASCII')

    def test_petscii_is_not_a_valid_choice(self):
        # PETSCII needs the separate raw-byte port, not this JSON client's
        # A/P/C/Q terminal-negotiation answer -- see _TRANSLATION_ANSWER's
        # docstring in tada_client.py.
        with patch('builtins.input'), patch.object(tc.getpass, 'getpass'), \
             self.assertRaises(SystemExit):
            self._run_main(
                ['--username', 'alexa', '--password', 'x', '--translation', 'PETSCII'])

    def test_invalid_translation_choice_raises(self):
        with patch('builtins.input'), patch.object(tc.getpass, 'getpass'), \
             self.assertRaises(SystemExit):
            self._run_main(['--username', 'alexa', '--password', 'x', '--translation', 'bogus'])


if __name__ == '__main__':
    unittest.main()
