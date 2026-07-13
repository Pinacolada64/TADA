"""tests/test_tada_client_status.py

Unit tests for tada_client.py's post-login status bar:
"TADA | host:port | <character_name>" once logged in (mode only shown
with --debug), replacing the earlier connection/mode-only status line.

Run with:
    python -m pytest tests/test_tada_client_status.py -v
"""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import MagicMock

from prompt_toolkit.buffer import Buffer

import tada_client as tc


class TestStatusTextFormat(unittest.TestCase):

    def test_pre_login_status_unchanged(self):
        state = tc.ClientState()
        state.host = 'localhost'
        state.port = 34083
        state.connected = True
        state.mode = 'login'
        self.assertIn('localhost:34083', state.status_text)
        self.assertIn('not logged in', state.status_text)
        self.assertIn('login', state.status_text)

    def test_post_login_status_is_pipe_separated(self):
        state = tc.ClientState()
        state.host = 'localhost'
        state.port = 34083
        state.character_name = 'Railbender'
        self.assertEqual(state.status_text, ' TADA | localhost:34083 | Railbender ')

    def test_post_login_status_omits_mode_by_default(self):
        state = tc.ClientState()
        state.host = 'localhost'
        state.port = 34083
        state.character_name = 'Railbender'
        state.mode = 'app'
        self.assertNotIn('app', state.status_text)

    def test_post_login_status_shows_mode_with_debug(self):
        state = tc.ClientState(debug=True)
        state.host = 'localhost'
        state.port = 34083
        state.character_name = 'Railbender'
        state.mode = 'app'
        self.assertIn('Railbender', state.status_text)
        self.assertIn('app', state.status_text)


class TestWelcomeLineParsing(unittest.IsolatedAsyncioTestCase):

    async def _feed_and_run(self, lines: list[str]):
        state = tc.ClientState()
        output_buffer = Buffer(name='output', read_only=True)
        app = MagicMock()

        reader = asyncio.StreamReader()
        reader.feed_data((json.dumps({'lines': lines}) + '\n').encode('utf-8'))
        reader.feed_eof()

        await tc._receive_loop(reader, output_buffer, state, app)
        return state

    async def test_extracts_name_from_plain_welcome(self):
        state = await self._feed_and_run(['Welcome, Railbender!'])
        self.assertEqual(state.character_name, 'Railbender')

    async def test_extracts_name_with_wraith_master_title(self):
        state = await self._feed_and_run(['Welcome, Railbender, Wraith Master of Spur!'])
        self.assertEqual(state.character_name, 'Railbender')

    async def test_extracts_guest_name(self):
        state = await self._feed_and_run(['Welcome, Guest 3!'])
        self.assertEqual(state.character_name, 'Guest 3')

    async def test_unrelated_lines_do_not_set_character_name(self):
        state = await self._feed_and_run(['You are in a dark room.', 'Exits: north, south.'])
        self.assertIsNone(state.character_name)

    async def test_welcome_line_among_others_still_matches(self):
        state = await self._feed_and_run([
            'There is a large... well... illusion here.',
            'Welcome, Railbender!',
            'You last connected on 2026-07-01.',
        ])
        self.assertEqual(state.character_name, 'Railbender')


class TestPromptTextTracking(unittest.IsolatedAsyncioTestCase):
    """Regression test: the server sends a 'prompt' field on every Message
    (e.g. "[A]mmo, [B]ooby traps, [H]elp, or Q to leave> "), but
    _receive_loop() used to ignore it entirely and the input line's
    get_line_prefix was hardcoded to a static '> ' -- so players saw a
    bare '>' with no indication of what was being asked."""

    async def _feed_and_run(self, messages: list[dict]):
        state = tc.ClientState()
        output_buffer = Buffer(name='output', read_only=True)
        app = MagicMock()

        reader = asyncio.StreamReader()
        for msg in messages:
            reader.feed_data((json.dumps(msg) + '\n').encode('utf-8'))
        reader.feed_eof()

        await tc._receive_loop(reader, output_buffer, state, app)
        return state

    async def test_default_prompt_is_bare_arrow(self):
        state = tc.ClientState()
        self.assertEqual(state.prompt_text, '> ')

    async def test_prompt_field_updates_state(self):
        state = await self._feed_and_run([
            {'lines': [], 'prompt': '[A]mmo, [B]ooby traps, [H]elp, or Q to leave> '},
        ])
        self.assertEqual(state.prompt_text, '[A]mmo, [B]ooby traps, [H]elp, or Q to leave> ')

    async def test_blank_prompt_does_not_clear_last_seen_prompt(self):
        state = await self._feed_and_run([
            {'lines': [], 'prompt': 'Your Choice> '},
            {'lines': ['Done!'], 'prompt': ''},
        ])
        self.assertEqual(state.prompt_text, 'Your Choice> ')


if __name__ == '__main__':
    unittest.main()
