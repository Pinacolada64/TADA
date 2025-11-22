#!/bin/env python3
"""
To add a new command:

1. Create a new class in commands/ that inherits from Command.
2. Implement the required methods (name, execute, help_text)
3. Add the command class to register_commands() in server_commands.py

Each command is self-contained and includes its own help text by overriding the HelpCommand class from help.py.
"""
from abc import abstractmethod
from typing import List, Dict, Any
from typing import TypeVar, Generic, Optional

T = TypeVar('T')

# from server.locks import Lock, LockType
from commands.base_command import Command, CommandResult

class GuestCommand(Command):
    """Base class for all server commands.

    Commands are the primary way users interact with the server. Each command
    handles a specific action and can be invoked by its name or aliases.
    """

    def __init__(self, context: T = None):
        """Initialize the command with an optional context.

        Args:
            context: Optional context for the command (e.g., command manager, player info)
        """
        # Initializes the command with an optional context.
        # The context is typically a dictionary or object containing resources
        # needed by the command, such as the command manager, player information,
        # or other relevant objects. This allows each command to access shared
        # or specific data required for its operation.
        self.context = context

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the command (used to invoke it)."""
        pass

    @property
    def aliases(self) -> List[str]:
        """Optional list of command aliases."""
        return []

    @property
    def locks(self) -> List[str]:
        """
        The permissions required to execute this command.

        This is used to check if the user is allowed to execute the command.

        Some examples of locks:
        'login' command should only be executable by a Guest (an unauthenticated user).
        login: Lock(LockType.MODE, Mode.LOGIN, True)

        'new' should only be executable in Mode.LOGIN, or by a Guest (an unauthenticated user).
        new: Lock(LockType.MODE, [Mode.LOGIN, Mode.GUEST], True)

        'quit' can be used by an unauthenticated user (at the login screen) in Mode.LOGIN,
            or by a Player (an authenticated user) in Mode.APP.
        quit: Lock(LockType.MODE, [Mode.LOGIN, Mode.APP], True)

        'edit' should only be executable by an Administrator (an authenticated user with the Administrator flag set).
        edit: Lock(LockType.PLAYER_FLAG, PlayerFlag.ADMINISTRATOR, True)

        # A LockType class is implemented to handle such locks as:
        # reboot: Lock(LockType.PLAYER_FLAG, PlayerFlag.ADMINISTRATOR, True)
        # connect: Lock(LockType.MODE, Mode.LOGIN, True)

        # TODO: Prevent certain players from going north:
        # Exit('n': {'lock': Lock(LockType.CUSTOM, lambda: Player.name in ["Railbender", "Eowyn", "Gandalf"])})
        """
        return []

    async def execute(self, args: List[str], data: Dict[str, Any]) -> CommandResult:
        """
        Execute the command with the given data.

        :param data: Dictionary containing command arguments and context
        :return: CommandResult: The result of the command execution
        """
        try:
            return await self._execute(data)
        except Exception as e:
            return CommandResult(
                success=False,
                error=str(e),
                message=f"An error occurred: {str(e)}"
            )

    @abstractmethod
    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        """Implementation of the command execution.

        This method must be implemented by subclasses to provide the command's functionality.

        Args:
            data: Dictionary containing command arguments and context

        Returns:
            CommandResult: The result of the command execution
        """
        return CommandResult(False, error="Not implemented", message="This command is not yet implemented.")

    def help_text(self) -> str:
        """Return the help text for this command."""
        return f"No help available for command '{self.name}'"


def test_command():
    """Test the Command class"""

    class TestCommand(Command):
        @property
        def name(self) -> str:
            return "test"

        async def _execute(self, data: Dict[str, Any]) -> CommandResult:
            return CommandResult(True, message="Test command executed")

    command = TestCommand()
    assert command.name == "test"
    assert command.aliases == []
    assert command.locks == []

    import asyncio
    result = asyncio.run(command.execute({}))
    assert result.success is True
    assert result.message == "Test command executed"

    print("✅ TestCommand passed")


if __name__ == "__main__":
    test_command()
