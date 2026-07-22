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

from commands.base_command import Command, CommandResult, Mode
from commands.connect import ConnectCommand, _load_credentials, guild_welcome_line


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


class TestResumableCreationRouting(unittest.IsolatedAsyncioTestCase):
    """A player who paused character creation (commands/new_player.py's
    main_flow()'s _handle_abandon_or_pause()) has creation_done=False and
    a saved creation_step. _authenticate() must route them back into
    main_flow() at that step instead of the normal game loop."""

    def setUp(self):
        import tempfile
        import net_common
        self._tmpdir = tempfile.TemporaryDirectory()
        fake_user_dir = Path(self._tmpdir.name) / "net"
        fake_user_dir.mkdir(parents=True, exist_ok=True)
        self._user_dir_patcher = patch(
            "commands.connect.user_dir", return_value=fake_user_dir,
        )
        self._user_dir_patcher.start()
        self._old_run_dir = net_common.run_server_dir
        net_common.run_server_dir = self._tmpdir.name

    def tearDown(self):
        import net_common
        self._user_dir_patcher.stop()
        net_common.run_server_dir = self._old_run_dir
        self._tmpdir.cleanup()

    async def test_paused_account_routes_into_main_flow_at_saved_step(self):
        from player import Player
        paused = Player(id="pausedplayer", name="pausedplayer")
        paused.creation_done = False
        paused.creation_step = 5
        paused.unsaved_changes = True
        self.assertTrue(paused.save(force=True))

        cmd = ConnectCommand()
        ctx = _make_ctx()
        fake_result = CommandResult(success=False, error="paused")
        with patch("commands.connect._load_credentials",
                   return_value={"password": "s3cr3t"}), \
             patch("commands.new_player.main_flow",
                   new=AsyncMock(return_value=fake_result)) as mock_main_flow:
            result = await cmd.execute(ctx, "pausedplayer", "s3cr3t")

        mock_main_flow.assert_awaited_once()
        _, kwargs = mock_main_flow.call_args
        self.assertEqual(kwargs.get("resume_step"), 5)
        self.assertIs(result, fake_result)

    async def test_finished_account_does_not_route_into_main_flow(self):
        from player import Player
        finished = Player(id="finishedplayer", name="finishedplayer")
        finished.save(force=True)

        cmd = ConnectCommand()
        ctx = _make_ctx()
        with patch("commands.connect._load_credentials",
                   return_value={"password": "s3cr3t"}), \
             patch("commands.new_player.main_flow",
                   new=AsyncMock()) as mock_main_flow:
            result = await cmd.execute(ctx, "finishedplayer", "s3cr3t")

        mock_main_flow.assert_not_awaited()
        self.assertTrue(result.success)
        self.assertEqual(ctx.client.command_processor.current_mode, Mode.GAME)


class TestGuildWelcomeLine(unittest.TestCase):
    """Regression: the guild welcome used to be sent as two separate
    ctx.send() lines (login_lines += [line1, line2]), breaking the
    sentence in half mid-message. It must render as one continuous line."""

    def test_fist_is_one_line(self):
        from base_classes import Guild
        line = guild_welcome_line(Guild.FIST)
        self.assertEqual(
            line, "The Guild of the Iron Fist bids you, 'Welcome!' ==[]"
        )

    def test_claw_is_one_line(self):
        from base_classes import Guild
        line = guild_welcome_line(Guild.CLAW)
        self.assertEqual(
            line, r"The Guild of the Claw bids you, 'Welcome!' \|/"
        )

    def test_sword_is_one_line(self):
        from base_classes import Guild
        line = guild_welcome_line(Guild.SWORD)
        self.assertEqual(
            line, "The Guild of the Sword bids you, 'Welcome!' -}----"
        )

    def test_civilian_has_no_welcome(self):
        from base_classes import Guild
        self.assertIsNone(guild_welcome_line(Guild.CIVILIAN))


class TestPartyWaitingLine(unittest.TestCase):
    """SPUR.LOGON.S's ally-greeting line ("X is/are waiting for you!"),
    printed at login for each party member (master branch only -- skip
    has no equivalent). Was effectively dead code until player.party
    persistence was fixed (it was always empty on reload before that),
    so this locks in the phrasing now that it actually fires."""

    def test_no_party_returns_none(self):
        from commands.connect import _party_waiting_line
        self.assertIsNone(_party_waiting_line(None))
        self.assertIsNone(_party_waiting_line([]))

    def test_one_member(self):
        from commands.connect import _party_waiting_line
        ally = MagicMock()
        ally.name = 'Grog'
        self.assertEqual(
            _party_waiting_line([ally]), 'Grog is waiting for you!'
        )

    def test_two_members(self):
        from commands.connect import _party_waiting_line
        a1, a2 = MagicMock(), MagicMock()
        a1.name, a2.name = 'Grog', 'Ironclad'
        self.assertEqual(
            _party_waiting_line([a1, a2]), 'Grog and Ironclad are waiting for you!'
        )

    def test_three_members(self):
        from commands.connect import _party_waiting_line
        a1, a2, a3 = MagicMock(), MagicMock(), MagicMock()
        a1.name, a2.name, a3.name = 'Grog', 'Ironclad', 'Zeus'
        self.assertEqual(
            _party_waiting_line([a1, a2, a3]),
            'Grog, Ironclad and Zeus are waiting for you!',
        )


class TestLastConnectedDateFormat(unittest.IsolatedAsyncioTestCase):
    """Regression: 'You last connected on {player.last_connection}.' used
    the raw str(datetime) repr ("2026-07-11 14:32:01.123456"); now
    formatted as 'Month Day, Year' to match this codebase's other
    player-facing date formatting (editplayer.py birthday, ban.py
    suspension date)."""

    async def test_last_connected_uses_readable_date_format(self):
        cmd = ConnectCommand()
        ctx = _make_ctx()
        with patch("commands.connect._load_credentials",
                   return_value={"password": "s3cr3t"}):
            await cmd.execute(ctx, "alexa", "s3cr3t")

        sent_lines = []
        for call in ctx.send.await_args_list:
            for a in call.args:
                if isinstance(a, list):
                    sent_lines.extend(str(x) for x in a)
                else:
                    sent_lines.append(str(a))

        line = next((l for l in sent_lines if l.startswith('You last connected on')), None)
        self.assertIsNotNone(line)
        self.assertRegex(line, r'^You last connected on [A-Z][a-z]+ \d{2}, \d{4}\.$')


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)s %(name)s: %(message)s")
    unittest.main()