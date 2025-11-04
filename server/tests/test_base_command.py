#!/usr/bin/env python3
"""Unit tests for the base Command class."""

import asyncio
import unittest
from typing import Dict, Any, List

from commands.base_command import Command, CommandResult


class TestCommandClass(unittest.TestCase):
    """Test cases for the base Command class."""

    class TestCommand(Command):
        """A test command for unit testing."""
        @property
        def name(self) -> str:
            return "test"

        def aliases(self) -> List[str]:
            return ['t']

        async def _execute(self, params: List[str], data: Dict[str, Any]) -> CommandResult:
            dict_contents = {}
            if data:
                dict_contents = {k: v for k, v in data.__dict__.items()}
            return CommandResult(True, message=f"Test command executed successfully with context {dict_contents}")

    def setUp(self):
        """Set up test fixtures."""
        self.cmd = self.TestCommand()

    def test_command_creation(self):
        """Test command initialization and properties."""
        self.assertEqual(self.cmd.name, "test")
        self.assertIsNone(self.cmd.context)
        self.assertEqual(self.cmd.aliases, ['t'])
        self.assertEqual(self.cmd.locks, [])

    def test_command_execution(self):
        """Test command execution."""
        # Test basic execution
        result = self.cmd.execute(args=['argument', 'argument_2'], data=type('obj', (), {'__dict__': {'user': 'tester'}}))
        self.assertTrue(result)

        # Test async execution
        result = asyncio.run(
            self.cmd.execute(
                ['argument', 'another_argument'],
                type('obj', (), {'__dict__': {'data': 'null', 'message': 'whatever'}})
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(result.message, 'whatever')
        self.assertIn('Test command executed successfully', result.message)


if __name__ == "__main__":
    unittest.main()
