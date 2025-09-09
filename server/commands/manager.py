"""
Command manager for handling command registration and execution.
"""
from typing import Dict, Any, Optional, TypeVar
import logging

# TADA-specific imports:
from base import Command, CommandResult, oxford_comma_list

T = TypeVar('T', bound=Command)

class CommandManager:
    """Manages registration and execution of commands."""
    
    def __init__(self):
        self._commands: Dict[str, Command] = {}
        self._help_text_cache: Dict[str, str] = {}
    
    def register_command(self, command: Command) -> None:
        """Register a command with the manager.
        
        :param command: The command instance to register
        """
        # ensure there are no duplicate commands or aliases:
        # (an alias is a command name that is different from the command's real name.
        # when the user enters an alias, we want to execute the command it is an alias for.)
        if command.name.lower() in self._commands:
            logging.warning(f"Command '{command.name}' already registered, skipping.")
            return
        for alias in getattr(command, 'aliases', []):
            if alias.lower() in self._commands:
                logging.warning(f"Alias '{alias}' already registered, skipping.")
                return
        # Register the command and its aliases:
        self._commands[command.name.lower()] = command
        for alias in getattr(command, 'aliases', []):
            self._commands[alias.lower()] = command
        if alias:
            logging.info(f"Registered alias for '{command.name}': '{alias}'")
        logging.info(f"Registered command: '{command.name}'")

    def show_registered_commands(self) -> None:
        """Show all registered commands and their aliases in a formatted way."""
        if not self._commands:
            print("No commands registered.")
            return
            
        print("\nRegistered Commands:")
        print("-" * 50)
        
        # Group commands by their implementation (since aliases point to same command)
        unique_commands = {}
        for cmd_name, cmd in self._commands.items():
            if cmd not in unique_commands.values():
                unique_commands[cmd_name] = cmd
        
        # Sort commands alphabetically
        for cmd_name in sorted(unique_commands.keys()):
            cmd = unique_commands[cmd_name]
            aliases = [a for a in cmd.aliases if a != cmd_name]
            
            if aliases:
                alias_list = oxford_comma_list([f"'{a}'" for a in aliases])
                alias_count = "alias" if len(aliases) == 1 else "aliases"
                print(f"{cmd_name:<15} ({alias_count}: {alias_list})")
            else:
                print(f"{cmd_name}")
    
    async def execute(self, command_name: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute a command by name.
        
        :param command_name: Name of the command to execute
        :param data: Command data
        :return: Command execution result or None if command not found
        """
        command = self._commands.get(command_name.lower())
        if not command:
            return None
            
        return await command.execute(data)
    
    def get_command(self, command_name: str) -> Optional[Command]:
        """Get a command by name.
        
        :param command_name: Name of the command to get
        :return: The command instance or None if not found
        """
        return self._commands.get(command_name.lower())
    
    def get_help_text(self, command_name: str = None) -> str:
        """Get help text for a command or all commands.
        
        :param command_name: Optional name of the command to get help for
        :return: Help text for the specified command or all commands
        """
        # help for a specific command requested ("help <command>"):
        if command_name:
            command = self._commands.get(command_name.lower())
            if not command:
                return f"No help available for '{command_name}'"
            
            help_text = command.help_text()
            
            # Add aliases information if available
            aliases = [a for a in getattr(command, 'aliases', []) if a.lower() != command.name.lower()]
            if aliases:
                alias_list = oxford_comma_list([f"'{a}'" for a in aliases])
                help_text = f"{help_text}\n\nAliases: {alias_list}"
                
            return help_text
        
        # otherwise, just 'help' or 'h' specified, so give summaries of all commands:
        if not self._commands:
            return "No commands available"
        
        # Get unique commands using our optimized method
        unique_commands = self.get_all_commands()
    
        # Generate help text for each command
        help_texts = []
        for cmd_name in sorted(unique_commands.keys()):
            cmd = unique_commands[cmd_name]
            help_text = self._help_text_cache.get(cmd_name)
            if not help_text:
                help_lines = cmd.help_text().split('\n')
                help_text = help_lines[0].strip() if help_lines else ""
                self._help_text_cache[cmd_name] = help_text
            
            help_texts.append(f"{cmd_name:<15} - {help_text}")
            
        return "\n".join(help_texts)
    
    def get_all_commands(self) -> dict:
        """Return a dictionary of all unique command objects, keyed by their primary name."""
        unique_commands = {}
        for name, cmd in self._commands.items():
            if cmd not in unique_commands.values():
                unique_commands[name] = cmd
        return unique_commands        

# Global command manager instance
command_manager = CommandManager()

def register_command(command: Command) -> None:
    """Register a command with the global command manager.
    
    :param command: The command instance to register
    """
    command_manager.register_command(command)
