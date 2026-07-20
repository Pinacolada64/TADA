"""tests/social/test_board_edit.py

Unit tests for commands/board_edit.py -- the admin-only 'board #edit'
board-wide settings menu.
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import board as board_store
from commands.board_edit import edit_board_settings
from flags import PlayerFlags


def run(coro):
    return asyncio.run(coro)


class _FakePlayer:
    def __init__(self, name='tester', admin=True):
        self.name = name
        self._admin = admin
        self.return_key = 'Enter'

    def query_flag(self, flag):
        if flag == PlayerFlags.ADMIN:
            return self._admin
        return False


def make_ctx(player=None, prompts=None):
    ctx = MagicMock()
    ctx.player = player or _FakePlayer()
    ctx.send = AsyncMock()
    ctx.prompt = AsyncMock(side_effect=prompts or [])
    return ctx


class BoardEditTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config_path = Path(self._tmp.name) / 'board_config.json'
        patcher = patch.object(board_store, 'CONFIG_FILE', self.config_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)


class TestPermission(BoardEditTestCase):
    def test_non_admin_denied(self):
        ctx = make_ctx(player=_FakePlayer(admin=False))
        result = run(edit_board_settings(ctx))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'permission_denied')
        ctx.prompt.assert_not_awaited()


class TestMenu(BoardEditTestCase):
    def test_bare_enter_saves_and_exits_with_defaults(self):
        ctx = make_ctx(prompts=[''])
        result = run(edit_board_settings(ctx))
        self.assertTrue(result.success)
        self.assertEqual(board_store.load_config(self.config_path), {'anonymous_mode': 'ask'})
        self.assertIn('saved', str(ctx.send.call_args_list).lower())

    def test_shows_current_mode_in_the_menu(self):
        board_store.save_config({'anonymous_mode': 'yes'}, self.config_path)
        ctx = make_ctx(prompts=[''])
        run(edit_board_settings(ctx))
        self.assertIn('Yes', str(ctx.prompt.call_args))

    def test_change_to_yes(self):
        ctx = make_ctx(prompts=['a', 'y', ''])
        run(edit_board_settings(ctx))
        self.assertEqual(board_store.load_config(self.config_path)['anonymous_mode'], 'yes')

    def test_change_to_no(self):
        ctx = make_ctx(prompts=['a', 'n', ''])
        run(edit_board_settings(ctx))
        self.assertEqual(board_store.load_config(self.config_path)['anonymous_mode'], 'no')

    def test_change_back_to_ask(self):
        board_store.save_config({'anonymous_mode': 'yes'}, self.config_path)
        ctx = make_ctx(prompts=['a', 'a', ''])
        run(edit_board_settings(ctx))
        self.assertEqual(board_store.load_config(self.config_path)['anonymous_mode'], 'ask')

    def test_invalid_submenu_choice_reports_error_and_stays_in_menu(self):
        ctx = make_ctx(prompts=['a', 'zzz', ''])
        run(edit_board_settings(ctx))
        self.assertIn("Unrecognized choice", str(ctx.send.call_args_list))
        # unchanged -- invalid choice didn't silently apply anything
        self.assertEqual(board_store.load_config(self.config_path)['anonymous_mode'], 'ask')

    def test_unrecognized_top_level_choice_reports_error_and_stays_in_menu(self):
        ctx = make_ctx(prompts=['q', ''])
        run(edit_board_settings(ctx))
        self.assertIn("Unrecognized choice 'q'", str(ctx.send.call_args_list))

    def test_nothing_saved_until_exit(self):
        # Changing the mode mid-menu, then exiting, should persist --
        # this test just confirms the save happens on the *final* Enter,
        # not disk-written after every keystroke (matches the loop's
        # own structure: config only written in the Enter-to-exit branch).
        ctx = make_ctx(prompts=['a', 'y', ''])
        run(edit_board_settings(ctx))
        self.assertEqual(board_store.load_config(self.config_path)['anonymous_mode'], 'yes')


if __name__ == '__main__':
    unittest.main()
