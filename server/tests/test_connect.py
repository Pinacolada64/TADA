#!/usr/bin/env python3
"""tests/test_connect.py

Unit tests for commands/connect.py.

Run with:
    python -m pytest tests/test_connect.py -v
    python tests/test_connect.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

# ---------------------------------------------------------------------------
# Stub out server-side modules that aren't installed in the test environment
# ---------------------------------------------------------------------------

def _stub(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules.setdefault(name, m)

_stub("network_context", GameContext=object)
_stub("commands.utils")
_stub("commands.command_processor",
      create_command_processor=MagicMock(return_value=MagicMock()))

from commands.base_command import Command, CommandResult, Mode
from commands.connect import ConnectCommand, _load_credentials


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_ctx(username: str = "", mode: Mode = Mode.LOGIN,
              guest_count: int = 0) -> MagicMock:
    """Return a minimal async-capable GameContext stub."""
    ctx = MagicMock()
    ctx.send      = AsyncMock()
    ctx.send_room = AsyncMock()
    ctx.prompt    = AsyncMock(return_value="")

    ctx.client        = MagicMock()
    ctx.client.username = username
    ctx.client.mode   = mode
    ctx.client.addr   = ("127.0.0.1", 9999)

    # Populate server.clients with fake guests so numbering tests work
    fake_guests = {
        i: MagicMock(username=f"Guest {i}" if i > 1 else "Guest")
        for i in range(1, guest_count + 1)
    }
    ctx.server.clients = fake_guests

    return ctx


class TestConnectCommandMetadata(unittest.TestCase):
    """Verify class-level attributes are correct."""

    def setUp(self):
        self.cmd = ConnectCommand()

    def test_name(self):
        self.assertEqual(self.cmd.name, "connect")

    def test_aliases(self):
        self.assertIn("con",   self.cmd.aliases)
        self.assertIn("login", self.cmd.aliases)

    def test_mode_is_login_only(self):
        self.assertIn(Mode.LOGIN, self.cmd.modes)
        self.assertNotIn(Mode.GAME,  self.cmd.modes)
        self.assertNotIn(Mode.ADMIN, self.cmd.modes)
        self.assertNotIn(Mode.ANY,   self.cmd.modes)

    def test_help_present(self):
        from commands.help import HelpCategory
        self.assertIsNotNone(self.cmd.help)
        self.assertEqual(self.cmd.help.category, HelpCategory.AUTHENTICATION)
        self.assertTrue(self.cmd.help.summary)

    def test_is_available_in_login_mode(self):
        self.assertTrue(self.cmd.is_available_in(Mode.LOGIN))

    def test_not_available_in_game_mode(self):
        self.assertFalse(self.cmd.is_available_in(Mode.GAME))


class TestConnectNoArgs(unittest.IsolatedAsyncioTestCase):
    """connect with no arguments shows usage."""

    async def test_no_args_returns_failure(self):
        cmd = ConnectCommand()
        ctx = _make_ctx()
        result = await cmd.execute(ctx)
        self.assertFalse(result.success)
        self.assertEqual(result.error, "missing_args")

    async def test_no_args_sends_usage(self):
        cmd = ConnectCommand()
        ctx = _make_ctx()
        await cmd.execute(ctx)
        ctx.send.assert_awaited_once()


class TestConnectGuest(unittest.IsolatedAsyncioTestCase):
    """connect guest — happy path and name numbering."""

    async def test_guest_success(self):
        cmd = ConnectCommand()
        ctx = _make_ctx(guest_count=0)
        result = await cmd.execute(ctx, "guest")
        self.assertTrue(result.success)

    async def test_guest_sets_username_on_client(self):
        cmd = ConnectCommand()
        ctx = _make_ctx(guest_count=0)
        await cmd.execute(ctx, "guest")
        self.assertEqual(ctx.client.username, "Guest")

    async def test_guest_numbering_with_existing_guests(self):
        cmd = ConnectCommand()
        ctx = _make_ctx(guest_count=2)
        await cmd.execute(ctx, "guest")
        # Two guests already online → should become Guest 3
        self.assertEqual(ctx.client.username, "Guest 3")

    async def test_guest_sets_game_mode(self):
        cmd = ConnectCommand()
        ctx = _make_ctx(guest_count=0)
        await cmd.execute(ctx, "guest")
        # Mode now lives on the processor, not ctx.client.mode
        self.assertEqual(ctx.client.command_processor.current_mode, Mode.GAME)

    async def test_guest_sends_welcome(self):
        cmd = ConnectCommand()
        ctx = _make_ctx(guest_count=0)
        await cmd.execute(ctx, "guest")
        ctx.send.assert_awaited()
        all_output = " ".join(
            str(a) for call in ctx.send.await_args_list
            for a in call.args
        )
        self.assertIn("Guest", all_output)


class TestConnectAuthentication(unittest.IsolatedAsyncioTestCase):
    """connect <user> <password> — credential checking."""

    def setUp(self):
        # A successful login against a plaintext (legacy) password writes an
        # upgraded bcrypt hash back to disk (see _authenticate()'s "rehashed"
        # handling) -- isolate that write to a tmp dir so these tests can't
        # touch the real project's run/server/net/ directory.
        #
        # Patches commands.connect.user_dir directly (not net_common's
        # run_server_dir global) because some test modules elsewhere in the
        # suite pop and re-import net_common at collection time to dodge
        # *other* files' stale sys.modules stubs, which leaves this module
        # holding a second, divergent copy -- setting the attribute on
        # whichever copy `import net_common` resolves to here wouldn't
        # necessarily be the copy commands.connect's own `from net_common
        # import user_dir` bound to at its own import time.
        import tempfile
        from pathlib import Path
        self._tmpdir = tempfile.TemporaryDirectory()
        fake_user_dir = Path(self._tmpdir.name) / "net"
        fake_user_dir.mkdir(parents=True, exist_ok=True)
        self._user_dir_patcher = patch(
            "commands.connect.user_dir", return_value=fake_user_dir,
        )
        self._user_dir_patcher.start()

    def tearDown(self):
        self._user_dir_patcher.stop()
        self._tmpdir.cleanup()

    def _creds_file(self, password: str) -> str:
        return json.dumps({"password": password})

    async def test_valid_credentials_succeed(self):
        cmd = ConnectCommand()
        ctx = _make_ctx()
        with patch("commands.connect._load_credentials",
                   return_value={"password": "s3cr3t"}):
            result = await cmd.execute(ctx, "alexa", "s3cr3t")
        self.assertTrue(result.success)

    async def test_valid_login_sets_username(self):
        cmd = ConnectCommand()
        ctx = _make_ctx()
        with patch("commands.connect._load_credentials",
                   return_value={"password": "s3cr3t"}):
            await cmd.execute(ctx, "alexa", "s3cr3t")
        self.assertEqual(ctx.client.username, "alexa")

    async def test_valid_login_sets_game_mode(self):
        cmd = ConnectCommand()
        ctx = _make_ctx()
        with patch("commands.connect._load_credentials",
                   return_value={"password": "s3cr3t"}):
            await cmd.execute(ctx, "alexa", "s3cr3t")
        # Mode now lives on the processor, not ctx.client.mode
        self.assertEqual(ctx.client.command_processor.current_mode, Mode.GAME)

    async def test_wrong_password_fails(self):
        cmd = ConnectCommand()
        ctx = _make_ctx()
        with patch("commands.connect._load_credentials",
                   return_value={"password": "correct"}):
            result = await cmd.execute(ctx, "alexa", "wrong")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "authentication_failed")

    async def test_unknown_user_fails(self):
        cmd = ConnectCommand()
        ctx = _make_ctx()
        with patch("commands.connect._load_credentials", return_value=None):
            result = await cmd.execute(ctx, "nobody", "password")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "authentication_failed")

    async def test_failed_auth_does_not_reveal_user_existence(self):
        """Both 'unknown user' and 'wrong password' must produce the same message."""
        cmd = ConnectCommand()

        ctx_unknown = _make_ctx()
        with patch("commands.connect._load_credentials", return_value=None):
            result_unknown = await cmd.execute(ctx_unknown, "nobody", "x")

        ctx_bad_pw = _make_ctx()
        with patch("commands.connect._load_credentials",
                   return_value={"password": "correct"}):
            result_bad_pw = await cmd.execute(ctx_bad_pw, "alexa", "wrong")

        self.assertEqual(result_unknown.message, result_bad_pw.message)

    async def test_missing_password_prompts(self):
        """connect <user> with no password should prompt via ctx.prompt."""
        cmd = ConnectCommand()
        ctx = _make_ctx()
        ctx.prompt = AsyncMock(return_value="prompted_pw")
        with patch("commands.connect._load_credentials",
                   return_value={"password": "prompted_pw"}):
            result = await cmd.execute(ctx, "alexa")
        ctx.prompt.assert_awaited_once()
        self.assertTrue(result.success)

    async def test_empty_prompted_password_fails(self):
        cmd = ConnectCommand()
        ctx = _make_ctx()
        ctx.prompt = AsyncMock(return_value="")   # user just hit Enter
        result = await cmd.execute(ctx, "alexa")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "missing_password")


class TestLoadCredentials(unittest.TestCase):
    """Unit tests for the _load_credentials helper."""

    def test_returns_none_for_missing_file(self):
        with patch.object(Path, "exists", return_value=False):
            self.assertIsNone(_load_credentials("nobody"))

    def test_returns_dict_for_existing_file(self):
        data = json.dumps({"password": "abc"})
        # exists() must return True; patch Path.open at the pathlib level
        # so the code's `with path.open() as f` succeeds.
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "open", mock_open(read_data=data)):
            result = _load_credentials("alexa")
        self.assertEqual(result, {"password": "abc"})

    def test_returns_none_on_json_error(self):
        # Path.open, not builtins.open -- _load_credentials calls
        # `path.open()`, matching test_returns_dict_for_existing_file above.
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "open", mock_open(read_data="not json")):
            result = _load_credentials("alexa")
        self.assertIsNone(result)


class TestShowLoginStatus(unittest.IsolatedAsyncioTestCase):
    """_show_login_status stub behaviour."""

    async def test_no_username_sends_not_logged_in(self):
        cmd = ConnectCommand()
        ctx = _make_ctx(username="")
        result = await cmd._show_login_status(ctx)
        self.assertTrue(result.success)
        ctx.send.assert_awaited()
        all_output = " ".join(
            str(a) for call in ctx.send.await_args_list
            for a in call.args
        )
        self.assertIn("not currently logged in", all_output)

    async def test_with_username_sends_welcome(self):
        cmd = ConnectCommand()
        ctx = _make_ctx(username="alexa")
        result = await cmd._show_login_status(ctx)
        self.assertTrue(result.success)
        all_output = " ".join(
            str(a) for call in ctx.send.await_args_list
            for a in call.args
        )
        self.assertIn("alexa", all_output)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)s %(name)s: %(message)s")
    unittest.main()