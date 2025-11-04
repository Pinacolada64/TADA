"""
Command manager for handling command registration and execution.
"""
import logging
from typing import Dict, Optional, Type, TypeVar, Generic, Any

from commands.base_command import CommandResult, Command

logger = logging.getLogger(__name__)

class CommandManager:
    """Manages registration and execution of commands."""
    
    def __init__(self):
        """Initialize the command manager."""
        self._commands: Dict[str, Command] = {}
        self._aliases: Dict[str, str] = {}
    
    def register(self, command: Command) -> None:
        """
        Register a command with the manager.
        
        Args:
            command: The command to register
        """
        if not command.name:
            raise ValueError("Command must have a name")
            
        # Register the main command name
        if command.name in self._commands:
            logger.warning(f"Command '{command.name}' is already registered. Overwriting.")
        
        self._commands[command.name] = command
        
        # Register aliases
        for alias in getattr(command, 'aliases', []):
            if alias in self._aliases and self._aliases[alias] != command.name:
                logger.warning(f"Alias '{alias}' is already registered to command '{self._aliases[alias]}'. "
                             f"Cannot register it for '{command.name}'.")
            else:
                self._aliases[alias] = command.name
    
    def get_command(self, name: str) -> Optional[Command]:
        """
        Get a command by name or alias.
        
        Args:
            name: The name or alias of the command to get
            
        Returns:
            Optional[Command]: The command if found, None otherwise
        """
        # Try to get the command directly
        if name in self._commands:
            return self._commands[name]
            
        # Try to resolve aliases
        if name in self._aliases:
            return self._commands.get(self._aliases[name])
            
        return None
    
    def get_all_commands(self) -> Dict[str, Command]:
        """
        Get all registered commands.
        
        Returns:
            Dict[str, Command]: A dictionary mapping command names to command instances
        """
        return self._commands.copy()
    
    async def execute(self, command_name: str, **kwargs) -> CommandResult:
        """
        Execute a command by name.
        
        Args:
            command_name: The name or alias of the command to execute
            **kwargs: Additional arguments to pass to the command
            
        Returns:
            CommandResult: The result of the command execution
        """
        command = self.get_command(command_name)
        if not command:
            return CommandResult(
                success=False,
                error=f"Command '{command_name}' not found"
            )
        
        try:
            result = await command.execute(kwargs)
            return result
        except Exception as e:
            logger.exception(f"Error executing command '{command_name}': {e}")
            return CommandResult(
                success=False,
                error=f"Error executing command: {str(e)}"
            )

# Global instance of the command manager
command_manager = CommandManager()

def register_command(command: Command) -> None:
    """
    Register a command with the global command manager.
    
    Args:
        command: The command to register
    """
    command_manager.register(command)
