#!/usr/bin/env python3
"""tests/test_commands.py

Unit tests for:
  - commands/base_command.py  (Command, CommandResult, Mode, parse_args)
  - commands/command_processor.py  (CommandProcessor: register, find,
        search, category grouping, process_command, mode gating, error handling)

Run with:
    python -m pytest tests/test_commands.py -v
    # or
    python tests/test_commands.py
"""

from __future__ import annotations

import asyncio
import logging
import unittest
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Minimal stubs so the tests run without the full TADA server installed
# ---------------------------------------------------------------------------

import sys, types

# Stub out network_context so base_command / command_processor don't need it
nc_stub = types.ModuleType("network_context")
nc_stub.GameContext = object
sys.modules.setdefault("network_context", nc_stub)

from commands.base_command import Command, CommandResult, Mode
from commands.command_processor import CommandProcessor


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_ctx(screen_columns: int = 78):
    """Return a minimal async-capable context stub."""
    ctx = MagicMock()
    ctx.player.client_settings.screen_columns = screen_columns
    ctx.send  = AsyncMock()
    ctx.prompt = AsyncMock(return_value="")
    return ctx


class _EchoCommand(Command):
    """Echoes its args back.  Available in GAME mode (default)."""
    name    = "echo"
    aliases = ["ec"]
    modes   = {Mode.GAME}

    async def execute(self, ctx, *args):
        positional, switches = self.parse_args(*args)
        msg = " ".join(positional) or "(nothing)"
        return CommandResult.ok(f"echo: {msg}")


class _LoginCommand(Command):
    """Only available at the login prompt."""
    name  = "connect"
    modes = {Mode.LOGIN}

    async def execute(self, ctx, *args):
        return CommandResult.ok("connected")


class _AnyModeCommand(Command):
    """Available everywhere."""
    name  = "quit"
    modes = {Mode.ANY}

    async def execute(self, ctx, *args):
        return CommandResult.ok("goodbye")


class _BoomCommand(Command):
    """Always raises — tests error handling."""
    name  = "boom"
    modes = {Mode.ANY}

    async def execute(self, ctx, *args):
        raise RuntimeError("kaboom")


# ---------------------------------------------------------------------------
# CommandResult tests
# ---------------------------------------------------------------------------

class TestCommandResult(unittest.TestCase):

    def test_ok_factory(self):
        r = CommandResult.ok("done")
        self.assertTrue(r.success)
        self.assertEqual(r.message, "done")
        self.assertEqual(r.error, "")

    def test_fail_factory(self):
        r = CommandResult.fail("oops", error="bad_input")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "bad_input")

    def test_to_dict(self):
        r = CommandResult(success=True, message="hi", error="", data={"x": 1})
        d = r.to_dict()
        self.assertEqual(d["success"], True)
        self.assertEqual(d["data"], {"x": 1})


# ---------------------------------------------------------------------------
# Command base-class tests
# ---------------------------------------------------------------------------

class TestCommandBase(unittest.TestCase):

    def setUp(self):
        self.cmd = _EchoCommand()

    def test_name_and_aliases(self):
        self.assertEqual(self.cmd.name, "echo")
        self.assertIn("ec", self.cmd.aliases)

    def test_parse_args_splits_switches(self):
        pos, sw = self.cmd.parse_args("hello", "world", "#verbose", "#debug")
        self.assertEqual(pos, ["hello", "world"])
        self.assertEqual(sw, ["#verbose", "#debug"])

    def test_parse_args_empty(self):
        pos, sw = self.cmd.parse_args()
        self.assertEqual(pos, [])
        self.assertEqual(sw, [])

    def test_is_available_in_matching_mode(self):
        self.assertTrue(self.cmd.is_available_in(Mode.GAME))

    def test_is_available_in_wrong_mode(self):
        self.assertFalse(self.cmd.is_available_in(Mode.LOGIN))

    def test_any_mode_always_available(self):
        cmd = _AnyModeCommand()
        for m in Mode:
            self.assertTrue(cmd.is_available_in(m), f"should be available in {m}")

    def test_execute_returns_commandresult(self):
        ctx = _make_ctx()
        result = asyncio.run(self.cmd.execute(ctx, "one", "two"))
        self.assertIsInstance(result, CommandResult)
        self.assertTrue(result.success)
        self.assertIn("one", result.message)


# ---------------------------------------------------------------------------
# CommandProcessor — registration
# ---------------------------------------------------------------------------

class TestCommandProcessorRegistration(unittest.TestCase):

    def setUp(self):
        self.proc = CommandProcessor()
        self.echo = _EchoCommand()
        self.quit = _AnyModeCommand()
        self.proc.register_command(self.echo)
        self.proc.register_command(self.quit)

    def test_canonical_name_registered(self):
        self.assertIn("echo", self.proc._commands)
        self.assertIn("quit", self.proc._commands)

    def test_alias_registered(self):
        self.assertIn("ec", self.proc._aliases)
        self.assertEqual(self.proc._aliases["ec"], "echo")

    def test_duplicate_name_raises(self):
        with self.assertRaises(ValueError):
            self.proc.register_command(_EchoCommand())

    def test_duplicate_alias_logs_warning(self):
        class _ClashCommand(Command):
            name    = "clash"
            aliases = ["ec"]   # same alias as _EchoCommand
            async def execute(self, ctx, *args): return CommandResult.ok()

        with self.assertLogs(level="WARNING"):
            self.proc.register_command(_ClashCommand())
        # The alias should still point at the original command
        self.assertEqual(self.proc._aliases["ec"], "echo")

    def test_get_all_commands(self):
        all_cmds = self.proc.get_all_commands()
        self.assertIn("echo", all_cmds)
        self.assertIn("quit", all_cmds)
        self.assertIsInstance(all_cmds, dict)


# ---------------------------------------------------------------------------
# CommandProcessor — lookup
# ---------------------------------------------------------------------------

class TestCommandProcessorLookup(unittest.TestCase):

    def setUp(self):
        self.proc = CommandProcessor()
        self.proc.register_command(_EchoCommand())

    def test_find_by_canonical_name(self):
        cmd, is_alias = self.proc.find_command("echo")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "echo")
        self.assertFalse(is_alias)

    def test_find_by_alias(self):
        cmd, is_alias = self.proc.find_command("ec")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "echo")
        self.assertTrue(is_alias)

    def test_find_case_insensitive(self):
        cmd, _ = self.proc.find_command("ECHO")
        self.assertIsNotNone(cmd)

    def test_find_nonexistent(self):
        cmd, is_alias = self.proc.find_command("zzz")
        self.assertIsNone(cmd)
        self.assertFalse(is_alias)


# ---------------------------------------------------------------------------
# CommandProcessor — category grouping
# ---------------------------------------------------------------------------

class TestCommandProcessorCategories(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Import Help / HelpCategory only if available; skip gracefully
        try:
            from help import Help, HelpCategory
            self.HelpCategory = HelpCategory

            class _CatCmdA(Command):
                name = "say"
                help = Help(summary="Say something.", category=HelpCategory.COMMUNICATION)
                async def execute(self, ctx, *args): return CommandResult.ok()

            class _CatCmdB(Command):
                name = "go"
                help = Help(summary="Move.", category=HelpCategory.MOVEMENT)
                async def execute(self, ctx, *args): return CommandResult.ok()

            self.proc = CommandProcessor()
            self.proc.register_command(_CatCmdA())
            self.proc.register_command(_CatCmdB())
            self.skip = False
        except ImportError:
            self.skip = True

    def test_get_commands_by_category_all(self):
        if self.skip:
            self.skipTest("help module not available")
        groups = self.proc.get_commands_by_category()
        cats   = list(groups.keys())
        self.assertIn(self.HelpCategory.COMMUNICATION, cats)
        self.assertIn(self.HelpCategory.MOVEMENT, cats)

    def test_get_commands_by_category_filter(self):
        if self.skip:
            self.skipTest("help module not available")
        groups = self.proc.get_commands_by_category(self.HelpCategory.MOVEMENT)
        self.assertEqual(list(groups.keys()), [self.HelpCategory.MOVEMENT])
        self.assertEqual(len(groups[self.HelpCategory.MOVEMENT]), 1)
        self.assertEqual(groups[self.HelpCategory.MOVEMENT][0].name, "go")


# ---------------------------------------------------------------------------
# CommandProcessor — search
# ---------------------------------------------------------------------------

class TestCommandProcessorSearch(unittest.TestCase):

    def setUp(self):
        self.proc = CommandProcessor()
        self.proc.register_command(_EchoCommand())   # name contains "echo"
        self.proc.register_command(_AnyModeCommand())  # name = "quit"
        self.proc.register_command(_LoginCommand())    # name = "connect"

    def test_search_by_name(self):
        results = self.proc.search_commands("echo")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "echo")

    def test_search_by_alias(self):
        # "ec" is an alias of echo; it also appears as a substring of "connect",
        # so search may return both — we just verify echo is included.
        results = self.proc.search_commands("ec")
        names = {r.name for r in results}
        self.assertIn("echo", names)

    def test_search_case_insensitive(self):
        results = self.proc.search_commands("ECHO")
        self.assertEqual(len(results), 1)

    def test_search_no_match(self):
        results = self.proc.search_commands("xyzzy")
        self.assertEqual(len(results), 0)

    def test_search_partial_match(self):
        # "on" appears in "connect"
        results = self.proc.search_commands("on")
        names = {r.name for r in results}
        self.assertIn("connect", names)


# ---------------------------------------------------------------------------
# CommandProcessor — dispatch and mode gating
# ---------------------------------------------------------------------------

class TestCommandProcessorDispatch(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.proc = CommandProcessor(current_mode=Mode.GAME)
        self.echo = _EchoCommand()
        self.quit = _AnyModeCommand()
        self.boom = _BoomCommand()
        self.conn = _LoginCommand()
        self.proc.register_command(self.echo)
        self.proc.register_command(self.quit)
        self.proc.register_command(self.boom)
        self.proc.register_command(self.conn)
        self.ctx = _make_ctx()
        self.proc.context = self.ctx

    async def test_dispatch_by_name(self):
        result = await self.proc.process_command(["echo", "hello"])
        self.assertTrue(result.success)
        self.assertIn("hello", result.message)

    async def test_dispatch_by_alias(self):
        result = await self.proc.process_command(["ec", "world"])
        self.assertTrue(result.success)
        self.assertIn("world", result.message)

    async def test_unknown_command(self):
        result = await self.proc.process_command(["xyzzy"])
        self.assertFalse(result.success)
        self.assertEqual(result.error, "unknown_command")

    async def test_empty_input(self):
        result = await self.proc.process_command([])
        self.assertFalse(result.success)
        self.assertEqual(result.error, "no_command")

    async def test_process_input_string(self):
        result = await self.proc.process_input("echo one two three")
        self.assertTrue(result.success)
        self.assertIn("one", result.message)

    async def test_any_mode_available_in_game(self):
        # quit has modes={Mode.ANY} — should work in GAME mode
        result = await self.proc.process_command(["quit"])
        self.assertTrue(result.success)

    async def test_login_command_blocked_in_game_mode(self):
        # connect has modes={Mode.LOGIN} — blocked in GAME mode
        result = await self.proc.process_command(["connect"])
        self.assertFalse(result.success)
        self.assertEqual(result.error, "wrong_mode")

    async def test_login_command_allowed_in_login_mode(self):
        self.proc.current_mode = Mode.LOGIN
        result = await self.proc.process_command(["connect"])
        self.assertTrue(result.success)

    async def test_exception_in_execute_returns_failure(self):
        result = await self.proc.process_command(["boom"])
        self.assertFalse(result.success)
        self.assertEqual(result.error, "command_error")
        self.assertIn("kaboom", result.message)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(levelname)s %(name)s: %(message)s")
    unittest.main()