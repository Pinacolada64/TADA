"""Register all commands with the command manager."""
import logging
from typing import List, Type, Any, Set

from .manager import command_manager
from .page import PageCommand
from .whisper import WhisperCommand
from .create_character import CreateCharacterCommand

# List of command classes to register
COMMAND_CLASSES = [
    PageCommand,
    WhisperCommand,
    CreateCharacterCommand,
]

def register_commands() -> None:
    """Register all commands with the command manager.
    
    This function is idempotent and can be called multiple times safely.
    """
    logger = logging.getLogger(__name__)
    
    # Get already registered commands to avoid duplicates
    registered_commands = set(command_manager.get_all_commands().keys())
    
    # Register each command class if not already registered
    for command_class in COMMAND_CLASSES:
        try:
            command = command_class()
            
            # Skip if already registered
            if command.name in registered_commands:
                logger.debug(f"Command '{command.name}' is already registered, skipping.")
                continue
                
            # Register the command
            command_manager.register_command(command)
            registered_commands.add(command.name)
            
            # Log registration
            logger.info(f"Registered command: {command.name}")
            if hasattr(command, 'aliases') and command.aliases:
                logger.info(f"  Aliases: {', '.join(command.aliases)}")
                
        except Exception as e:
            logger.error(f"Failed to register command {command_class.__name__}: {e}", 
                        exc_info=True)

# Register commands when this module is imported
register_commands()
