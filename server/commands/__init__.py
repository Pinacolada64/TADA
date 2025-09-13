"""
Commands package for TADA server.

This package provides a command system for the TADA server, allowing for
modular command handling and easy registration of new commands.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Type, Any, Optional, List

# Add the server directory to the Python path
server_dir = str(Path(__file__).parent.parent.parent)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

from .base import Command, CommandResult
from .manager import CommandManager, register_command
from .help import HelpCommand

# Initialize the command manager
command_manager = CommandManager()

# Import all command modules to register them with the command manager
from . import help, login, page, who, whisper

# Re-export the command manager and register function
__all__ = [
    'Command',
    'CommandResult',
    'command_manager',
    'register_command',
    'get_command',
    'get_all_commands',
    'execute_command'
]

# Set up logging
logger = logging.getLogger(__name__)

def get_command(name: str) -> Optional[Command]:
    """Get a command by name or alias.
    
    Args:
        name: The name or alias of the command to get
        
    Returns:
        Optional[Command]: The command if found, None otherwise
    """
    return command_manager.get_command(name)

def get_all_commands() -> Dict[str, Command]:
    """Get all registered commands.
    
    Returns:
        Dict[str, Command]: A dictionary mapping command names to command instances
    """
    return command_manager.get_all_commands()

async def execute_command(
    command_name: str, 
    data: Dict[str, Any], 
    context: Optional[Dict[str, Any]] = None
) -> CommandResult:
    """Execute a command with the given data and context.
    
    Args:
        command_name: The name or alias of the command to execute
        data: The command data
        context: Additional context for the command
        
    Returns:
        CommandResult: The result of the command execution
    """
    if context:
        data.update(context)
    
    command = get_command(command_name)
    if not command:
        return CommandResult(
            success=False,
            error='unknown_command',
            message=f"Unknown command: {command_name}"
        )
    
    try:
        return await command.execute(data)
    except Exception as e:
        logger.error(f"Error executing command {command_name}: {e}", exc_info=True)
        return CommandResult(
            success=False,
            error='command_error',
            message=f"An error occurred while executing the command: {str(e)}"
        )

# Import register_commands to ensure all commands are registered
from .register_commands import register_commands

# Log the registered commands on import
register_commands()
logger.debug(f"Registered commands: {', '.join(command_manager.get_all_commands().keys())}")
