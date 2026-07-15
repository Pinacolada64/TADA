#!/usr/bin/env python3
"""Unit tests for the CommandProcessor class."""
import logging
import unittest
from unittest.mock import MagicMock
from typing import Dict, Any, List
import asyncio

# Add the project root to the Python path
import sys
import os

from commands.help import HelpCategory

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from commands.base_command import Command, CommandResult
from commands.command_processor import CommandProcessor


class TestCommand(Command):
    """A test command for unit testing."""

    def __init__(self, name: str, category=HelpCategory.GENERAL, aliases=None, summary=""):
        from commands.help import Help
        super().__init__()
        self._name = name
        self._aliases = aliases or []
        self.help = Help(summary=summary, category=category)
        self.execute_mock = MagicMock(return_value=CommandResult(True, f"{name} executed"))

    @property
    def name(self) -> str:
        return self._name

    @property
    def aliases(self):
        return self._aliases

    async def execute(self, ctx, *args) -> CommandResult:
        """Execute the command. Support sync or async mocks."""
        res = self.execute_mock(ctx, list(args))
        if asyncio.iscoroutine(res):
            return await res
        return res


class TestCommandProcessor(unittest.IsolatedAsyncioTestCase):
    """Test cases for CommandProcessor class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a processor with a dummy client (None is acceptable for unit tests)
        self.processor = CommandProcessor(client=None)
        # Ensure the processor has an explicit context dict we can check
        self.processor.context = {}

        self.command1 = TestCommand(name="test1",
                                    category=HelpCategory.GENERAL,
                                    aliases=["t1", "t1a"],
                                    summary="Test command 1")
        self.command2 = TestCommand(name="test2",
                                    category=HelpCategory.COMMUNICATION,
                                    aliases=["t2"],
                                    summary="Another test command")
        self.command3 = TestCommand("another",
                                    HelpCategory.GENERAL,
                                    [],
                                    "Yet another test command")
        
        # Register test commands
        self.processor.register_command(self.command1)
        self.processor.register_command(self.command2)
        self.processor.register_command(self.command3)
    
    def test_register_command(self):
        """Test command registration."""
        # Test direct command name
        self.assertIn("test1", self.processor._commands)
        self.assertEqual(self.processor._commands["test1"].name, "test1")
        
        # Test aliases (stored in _aliases, not _commands)
        self.assertIn("t1", self.processor._aliases)
        self.assertIn("t1a", self.processor._aliases)
        self.assertIn("t2", self.processor._aliases)

        # Test alias mapping
        self.assertEqual(self.processor._aliases["t1"], "test1")
        self.assertEqual(self.processor._aliases["t1a"], "test1")
        self.assertEqual(self.processor._aliases["t2"], "test2")
        
        # Test duplicate alias
        with self.assertLogs(level='WARNING'):
            self.processor.register_command(TestCommand("duplicate", aliases=["t1"]))

    def test_clear(self):
        """clear() empties both registries so discover() can re-run without
        ValueError on already-registered names (see commands/reload.py --
        hot-reloading mutates an existing CommandProcessor in place rather
        than replacing it, since already-running sessions hold a reference
        to this exact instance)."""
        self.assertTrue(self.processor._commands)
        self.assertTrue(self.processor._aliases)

        self.processor.clear()

        self.assertEqual(self.processor._commands, {})
        self.assertEqual(self.processor._aliases, {})

        # Re-registering after clear() must not raise (no stale duplicates).
        self.processor.register_command(self.command1)
        self.assertIn("test1", self.processor._commands)

    def test_find_command(self):
        """Test finding commands by name or alias."""
        # Test direct command name
        cmd, is_alias = self.processor.find_command("test1")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "test1")
        self.assertFalse(is_alias)
        
        # Test alias
        cmd, is_alias = self.processor.find_command("t1")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "test1")
        self.assertTrue(is_alias)
        
        # Test case insensitivity
        cmd, _ = self.processor.find_command("TEST1")
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.name, "test1")
        
        # Test non-existent command
        cmd, _ = self.processor.find_command("nonexistent")
        self.assertIsNone(cmd)
    
    def test_get_commands_by_category(self):
        """Test getting commands by category."""
        # Get all commands grouped by HelpCategory
        categories = self.processor.get_commands_by_category()
        self.assertIn(HelpCategory.GENERAL, categories)
        self.assertIn(HelpCategory.COMMUNICATION, categories)

        # Check commands in GENERAL category
        general_commands = [cmd.name for cmd in categories[HelpCategory.GENERAL]]
        self.assertIn("test1", general_commands)
        self.assertIn("another", general_commands)
        
        # Check commands in ADMINISTRATION category
        admin_commands = [cmd.name for cmd in categories[HelpCategory.COMMUNICATION]]
        self.assertIn("test2", admin_commands)
        
        # Test filtering by category
        general_only = self.processor.get_commands_by_category(HelpCategory.GENERAL)
        self.assertEqual(len(general_only), 1)  # Only one category key
        self.assertEqual(len(general_only[HelpCategory.GENERAL]), 2)  # test1 and another
    
    def test_search_commands(self):
        """Test searching commands."""
        # Search by name
        results = self.processor.search_commands("test1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "test1")
        
        # Search by alias
        results = self.processor.search_commands("t1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "test1")
        
        # Search by summary (may match multiple commands containing the phrase)
        results = self.processor.search_commands("another test")
        self.assertGreaterEqual(len(results), 1)
        names = {r.name for r in results}
        # Expect at least the 'another' command to be present
        self.assertIn("another", names)

        # Test case insensitivity
        results = self.processor.search_commands("TEST")
        self.assertEqual(len(results), 3)  # Should match all test commands
        
        # Test no results
        results = self.processor.search_commands("nonexistent")
        self.assertEqual(len(results), 0)
    
    async def test_process_command(self):
        """Test command processing."""
        context = {"test": "context"}
        # set the processor context used when executing commands
        self.processor.context = context

        # Test with direct command name
        result = await self.processor.process_command(["test1", "arg1", "arg2"])
        self.assertTrue(result.success)
        self.command1.execute_mock.assert_called_once_with(context, ["arg1", "arg2"])

        # Test with alias
        self.command1.execute_mock.reset_mock()
        result = await self.processor.process_command(["t1", "arg1"])
        self.assertTrue(result.success)
        self.command1.execute_mock.assert_called_once_with(context, ["arg1"])

        # Test unknown command
        result = await self.processor.process_command(["nonexistent"])
        self.assertFalse(result.success)
        self.assertEqual(result.error, "unknown_command")
        
        # Test empty command
        result = await self.processor.process_command([])
        self.assertFalse(result.success)
        self.assertEqual(result.error, "no_command")
    
    async def test_command_execution_error(self):
        """Test error handling during command execution."""
        # Create a command that raises an exception
        error_cmd = TestCommand("error_cmd")
        # Make the mock raise an exception when called
        def raise_exc(ctx, args_list):
            raise Exception("Test error")
        error_cmd.execute_mock.side_effect = raise_exc
        self.processor.register_command(error_cmd)
        
        # Test that the error is caught and returned as a CommandResult
        result = await self.processor.process_command(["error_cmd"])
        self.assertFalse(result.success)
        self.assertEqual(result.error, "command_error")
        self.assertIn("Test error", result.message)


def _make_ctx_with_flags(*, admin=False, dm=False, with_send=False):
    """Minimal ctx stub with a controllable query_flag(), for
    TestVersionSwitch -- a bare MagicMock's query_flag() would otherwise
    return a truthy MagicMock by default, silently acting 'privileged'
    regardless of what the test intends."""
    from flags import PlayerFlags

    ctx = MagicMock()
    ctx.player.query_flag = lambda flag: (
        (admin and flag == PlayerFlags.ADMIN)
        or (dm and flag == PlayerFlags.DUNGEON_MASTER)
    )
    if with_send:
        ctx.send = unittest.mock.AsyncMock()
    else:
        del ctx.send
    return ctx


class TestVersionSwitch(unittest.IsolatedAsyncioTestCase):
    """The universal '#version'/'#ver' switch (command_version.py):
    reports a command's own last-changed date instead of running it,
    handled centrally in process_command() so no individual command
    needs to implement it. Gated to PlayerFlags.ADMIN/DUNGEON_MASTER."""

    def setUp(self):
        self.processor = CommandProcessor(client=None)
        self.processor.context = {}
        self.cmd = TestCommand(name="attack")
        self.processor.register_command(self.cmd)

    async def test_version_switch_short_circuits_execute_for_admin(self):
        ctx = _make_ctx_with_flags(admin=True)
        with unittest.mock.patch('command_version.get_command_version', return_value='2026-07-09'):
            result = await self.processor.process_command(["attack", "#version"], ctx=ctx)
        self.cmd.execute_mock.assert_not_called()
        self.assertTrue(result.success)
        self.assertIn('2026-07-09', result.message)
        self.assertIn('attack', result.message)

    async def test_version_switch_works_for_dungeon_master_too(self):
        ctx = _make_ctx_with_flags(dm=True)
        with unittest.mock.patch('command_version.get_command_version', return_value='2026-07-09'):
            result = await self.processor.process_command(["attack", "#version"], ctx=ctx)
        self.cmd.execute_mock.assert_not_called()
        self.assertIn('2026-07-09', result.message)

    async def test_ver_alias_also_triggers_it(self):
        ctx = _make_ctx_with_flags(admin=True)
        with unittest.mock.patch('command_version.get_command_version', return_value='2026-07-09'):
            result = await self.processor.process_command(["attack", "#ver"], ctx=ctx)
        self.cmd.execute_mock.assert_not_called()
        self.assertIn('2026-07-09', result.message)

    async def test_non_privileged_player_falls_through_to_normal_dispatch(self):
        """A non-admin/DM typing '#version' should NOT get version info --
        it's treated as just another (unrecognized) switch, and the
        command runs normally."""
        ctx = _make_ctx_with_flags(admin=False, dm=False)
        with unittest.mock.patch('command_version.get_command_version', return_value='2026-07-09'):
            result = await self.processor.process_command(["attack", "#version"], ctx=ctx)
        self.cmd.execute_mock.assert_called_once()
        self.assertNotIn('2026-07-09', result.message)

    async def test_no_player_at_all_falls_through_to_normal_dispatch(self):
        """process_command()'s plain-dict context fallback (no ctx passed,
        e.g. some existing tests) has no player at all -- must not crash,
        and must not be treated as privileged."""
        with unittest.mock.patch('command_version.get_command_version', return_value='2026-07-09'):
            await self.processor.process_command(["attack", "#version"])
        self.cmd.execute_mock.assert_called_once()

    async def test_normal_dispatch_unaffected_without_the_switch(self):
        ctx = _make_ctx_with_flags(admin=True)
        with unittest.mock.patch('command_version.get_command_version', return_value='2026-07-09'):
            await self.processor.process_command(["attack", "goblin"], ctx=ctx)
        self.cmd.execute_mock.assert_called_once()

    async def test_sends_to_ctx_when_available(self):
        ctx = _make_ctx_with_flags(admin=True, with_send=True)
        with unittest.mock.patch('command_version.get_command_version', return_value='2026-07-09'):
            await self.processor.process_command(["attack", "#version"], ctx=ctx)
        ctx.send.assert_awaited_once()
        self.assertIn('2026-07-09', ctx.send.await_args.args[0])

    async def test_case_insensitive_switch(self):
        ctx = _make_ctx_with_flags(admin=True)
        with unittest.mock.patch('command_version.get_command_version', return_value='2026-07-09'):
            result = await self.processor.process_command(["attack", "#VERSION"], ctx=ctx)
        self.cmd.execute_mock.assert_not_called()
        self.assertIn('2026-07-09', result.message)


# import a sample command to ensure decorators run during discovery if needed
try:
    from commands.example_commands import TestCommand as _ExampleTestCommand  # noqa: F401
except Exception as e:
    logging.exception(e)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    unittest.main()
