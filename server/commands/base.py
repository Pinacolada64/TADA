#!/bin/env python3
"""
To add a new command:

1. Create a new class in commands/ that inherits from Command.
2. Implement the required methods (name, execute, help_text)
3. Add the command class to register_commands() in server_commands.py

The code is now more maintainable and follows better object-oriented principles.
Each command is self-contained and includes its own help text.
"""

"""Base command class for server commands."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union, Callable, Awaitable, TypeVar, Generic, Type

# Type variable for the command context
T = TypeVar('T')

def oxford_comma_list(items: list) -> str:
    """Format a list of items with proper Oxford comma usage.
    
    >>> oxford_comma_list(["apple", "banana"])
    'apple and banana'
    >>> oxford_comma_list(["apple", "banana", "orange"])
    'apple, banana, and orange'
    >>> oxford_comma_list(["apple"])
    'apple'
    >>> oxford_comma_list([])
    ''
    """
    if not items:
        return ""
    elif len(items) == 1:
        return items[0]
    elif len(items) == 2:
        return f"{items[0]} and {items[1]}"
    else:
        return f"{', '.join(items[:-1])}, and {items[-1]}"

@dataclass
class CommandResult:
    """Result of a command execution."""
    success: bool = True
    message: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class Command(ABC, Generic[T]):
    """Base class for all server commands.
    
    Commands are the primary way users interact with the server. Each command
    handles a specific action and can be invoked by its name or aliases.
    """
    
    def __init__(self, context: T = None):
        """Initialize the command with an optional context."""
        # context is a dictionary of objects that are used by the command,
        # for example, the command manager, the player, etc.
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
        
        By default, this is Player, but it can be overridden in subclasses.

        For example, the 'login' command should only be executable by a Guest (an unauthenticated user).
        'create' should only be executable by a Guest (an unauthenticated user).
        'quit' should only be executable by a Player (an authenticated user).
        'edit' should only be executable by an Administrator (an authenticated user with the Administrator flag set).
        The permissions required to execute this command. Some example locks:

        # TODO: implement a Lock class to handle such locks as:
        # reboot: Lock(PlayerFlag.ADMINISTRATOR)
        # connect: Lock(Mode == Mode.LOGIN)
        
        # Prevent certain players from going north:
        # Exit('n': {'lock': Lock(Player.name in ["Railbender", "Eowyn", "Gandalf"])})
        """
        return []
            
    async def execute(self, data: Dict[str, Any]) -> CommandResult:
        """Execute the command with the given data.
        
        Args:
            data: Dictionary containing command arguments and context
            
        Returns:
            CommandResult: The result of the command execution
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
        
        Subclasses must implement this method to provide the command's functionality.
        
        Args:
            data: Dictionary containing command arguments and context
            
        Returns:
            CommandResult: The result of the command execution
        """
        pass
    
    def help_text(self) -> str:
        """Return the help text for this command."""
        return f"No help available for command '{self.name}'"
