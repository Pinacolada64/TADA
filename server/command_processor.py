"""
Command processor for handling and dispatching commands.
"""
import logging
from typing import Dict, Any, Optional, Type, TypeVar, Generic, Callable, Awaitable

from server.commands import command_manager
from server.commands.base import Command, CommandResult

T = TypeVar('T')

class CommandProcessor(Generic[T]):
    """Processes and dispatches commands to the appropriate handlers."""
    
    def __init__(self, context: T = None):
        """Initialize the command processor with an optional context."""
        self.context = context or {}
        self._commands: Dict[str, Command] = {}
        self._setup_commands()
    
    def _setup_commands(self):
        """Register all available commands."""
        # Import all command modules to register them
        from server.commands import help, login, page, who, new_player
        
        # Register all commands
        self._commands = {}
        for cmd in [
            help.register(), 
            login.register(), 
            page.register(), 
            who.register(),
            new_player.register()
        ]:
            if cmd:  # Only register if the command is not None
                self.register(cmd)
    
    def register(self, command: Command) -> None:
        """Register a command with the processor.
        
        :param command: The command to register
        """
        self._commands[command.name.lower()] = command
        for alias in getattr(command, 'aliases', []):
            self._commands[alias.lower()] = command
    
    async def process_command(self, command_name: str, data: Dict[str, Any]) -> CommandResult:
        """Process a command with the given name and data.
        
        :param command_name: Name of the command to execute
        :param data: Command data including arguments and context
            
        :return: CommandResult: The result of the command execution
        """
        command = self._commands.get(command_name.lower())
        if not command:
            return CommandResult(
                success=False,
                error='unknown_command',
                message=f"Unknown command: {command_name}"
            )
        
        # Add context to the data
        data['command'] = command_name
        data.update(self.context)
        
        try:
            # Execute the command
            result = await command.execute(data)
            return result
        except Exception as e:
            logging.exception(f"Error executing command {command_name}")
            return CommandResult(
                success=False,
                error='command_error',
                message=f"An error occurred while executing the command: {str(e)}"
            )
    
    async def process_input(self, input_text: str, context: Optional[Dict[str, Any]] = None) -> CommandResult:
        """Process raw input text as a command.
        
        :param input_text: Raw input text from the user
        :param context: Additional context for the command
            
        :return: CommandResult: The result of the command execution
        """
        if not input_text.strip():
            return CommandResult(
                success=False,
                error='empty_input',
                message='Please enter a command.'
            )
        
        # Parse the command and arguments
        parts = input_text.strip().split()
        command_name = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        # Prepare the command data
        data = {
            'args': args,
            'raw_input': input_text,
            **(context or {})
        }
        
        return await self.process_command(command_name, data)

def create_command_processor(context: Optional[Dict[str, Any]] = None) -> CommandProcessor:
    """Create and initialize a command processor with the given context."""
    return CommandProcessor(context=context)
