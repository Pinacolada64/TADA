"""tests/admin/test_banner_edit.py — Unit tests for commands/banner_edit.py's
'banner' command: '#'-only switch dispatch (#list/#edit), same convention
as reload.py/groups.py/whereat.py. No test file existed for this command
before the switch-consistency audit that touched it (dropping bare
'list'/'edit' positional words in favor of requiring '#').
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from commands.banner_edit import BannerEditCommand
from commands.base_command import CommandResult
from flags import PlayerFlags


def run(coro):
    return asyncio.run(coro)


def make_ctx(*, is_admin=True):
    player = MagicMock()
    player.name = 'Admin'
    player.query_flag = MagicMock(
        side_effect=lambda f: f == PlayerFlags.ADMIN and is_admin
    )
    ctx = MagicMock()
    ctx.player = player
    ctx.send   = AsyncMock()
    return ctx


class TestPermission(unittest.TestCase):
    def test_non_admin_denied(self):
        ctx = make_ctx(is_admin=False)
        result = run(BannerEditCommand().execute(ctx, '#list'))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'permission_denied')


class TestNoSubcommand(unittest.TestCase):
    def test_bare_banner_shows_usage(self):
        ctx = make_ctx()
        result = run(BannerEditCommand().execute(ctx))
        self.assertFalse(result.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('#edit', sent)
        self.assertIn('#list', sent)


class TestBareSubwordsRejected(unittest.TestCase):
    """'list'/'edit' are '#'-only switches -- a bare word here used to
    work exactly like '#list'/'#edit' (sub, *rest = positional). These
    lock in the explicit "needs a '#'" hint added alongside the #-only
    conversion, so a regression back to silently accepting the bare word
    (or silently doing nothing) is caught."""

    def test_bare_list_hints_at_hash_form(self):
        ctx = make_ctx()
        result = run(BannerEditCommand().execute(ctx, 'list'))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'missing_hash')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('#list', sent)

    def test_bare_edit_hints_at_hash_form(self):
        ctx = make_ctx()
        result = run(BannerEditCommand().execute(ctx, 'edit', 'castle'))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'missing_hash')
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('#edit', sent)


class TestListSwitch(unittest.TestCase):
    def test_hash_list_with_no_banners(self):
        ctx = make_ctx()
        fake_dir = MagicMock()
        fake_dir.is_dir.return_value = False
        with patch('commands.banner_edit.canvas_store.CANVASES_DIR', fake_dir):
            result = run(BannerEditCommand().execute(ctx, '#list'))
        self.assertTrue(result.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('No saved banners', sent)

    def test_hash_list_shows_saved_names(self):
        ctx = make_ctx()
        fake_path = MagicMock()
        fake_path.stem = 'castle'
        fake_dir = MagicMock()
        fake_dir.is_dir.return_value = True
        fake_dir.glob.return_value = [fake_path]
        with patch('commands.banner_edit.canvas_store.CANVASES_DIR', fake_dir):
            result = run(BannerEditCommand().execute(ctx, '#list'))
        self.assertTrue(result.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('castle', sent)


class TestEditSwitch(unittest.TestCase):
    def test_hash_edit_without_name_prompts_for_one(self):
        ctx = make_ctx()
        result = run(BannerEditCommand().execute(ctx, '#edit'))
        self.assertFalse(result.success)
        sent = ' '.join(str(c) for c in ctx.send.await_args_list)
        self.assertIn('#edit', sent)

    def test_hash_edit_with_name_opens_the_editor(self):
        ctx = make_ctx()
        with patch('commands.banner_edit.canvas_store.path_for', return_value='castle.canvas'), \
             patch('commands.banner_edit.stream_canvas_edit',
                    new=AsyncMock(return_value=CommandResult.ok('Saved.'))) as mock_stream:
            result = run(BannerEditCommand().execute(ctx, '#edit', 'castle'))
        self.assertTrue(result.success)
        mock_stream.assert_awaited_once()
        self.assertEqual(mock_stream.call_args.args[1], 'castle.canvas')


class TestUnknownSubcommand(unittest.TestCase):
    def test_unknown_hash_switch_reports_error(self):
        ctx = make_ctx()
        result = run(BannerEditCommand().execute(ctx, '#bogus'))
        self.assertFalse(result.success)
        self.assertEqual(result.error, 'unknown_subcommand')


if __name__ == '__main__':
    unittest.main()
