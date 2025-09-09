#!/bin/env python3
"""Help command implementation."""
from typing import Dict, Any, List
import logging

# TADA-specific imports:
from base import Command, CommandResult
from server.command_manager import command_manager

def oxford_comma_list(items: list) -> str:
    """
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


def headline(text: str) -> str:
    """Return a headline with a border."""
    # TODO: switch to tada_utilities.headline() - output() isn't ready yet
    return "\n".join(["=" * len(text), text, "=" * len(text)])

class HelpCommand(Command):
    """Handle the 'help' command."""
    
    @property
    def name(self) -> str:
        return "help"
    
    @property
    def aliases(self) -> List[str]:
        return ["h", "?"]
    
    def help_text(self) -> str:
        return f"This is help text for the '{self.name}' command."

    async def _execute(self, data: Dict[str, Any]) -> CommandResult:
        """Execute the help command.
        
        :param data: Dictionary containing command data including 'command' (optional)
        
        :return: CommandResult: Result containing help text
        """
        command_name = data.get('command')
        command_manager = self.context.get('command_manager')
        
        if not command_manager:
            return CommandResult(
                success=False,
                error='missing_command_manager',
                message='Command manager not available.'
            )
        
        if command_name:
            # Show help for a specific command
            help_text = command_manager.get_help_text(command_name)
            return CommandResult(
                success=True,
                message=help_text,
                data={'mode': 'help'}
            )
        else:
            # Show general help
            help_texts = [headline("Available commands:")]
            try:
                # Get the help text for all commands at once
                help_text = command_manager.get_help_text()
                help_texts.extend(help_text.split('\n'))
            except Exception as e:
                return CommandResult(
                    success=False,
                    error='get_help_text_failed',
                    message=f'Failed to get help text: {str(e)}'
                )
            
            help_texts.append("\nUse 'help <command>' to get more information about a command.")
            
            return CommandResult(
                success=True,
                message='\n'.join(help_texts),
                data={'mode': 'help'}
            )
    
    def help_text(self) -> str:
        """Display one-line summaries of all registered commands when just "help" is called."""
        help_texts = [headline("Help Command"),
                     "Usage: 'help' or 'h'",
                     "Displays brief summaries of all available commands.",
                     "",
                     "Available commands:",
                     ""]
        
        # Get all commands and calculate max name length for alignment
        try:
            logging.debug("Getting all commands from command manager...")
            commands_dict = command_manager.get_all_commands()
            logging.debug(f"Raw commands from manager: {commands_dict}")
            
            # Convert to list of unique commands (since aliases point to same command)
            unique_commands = []
            seen = set()
            for cmd in commands_dict.values():
                if id(cmd) not in seen:
                    seen.add(id(cmd))
                    unique_commands.append(cmd)
            
            commands = unique_commands
            logging.debug(f"Found {len(commands)} unique commands: {[c.name for c in commands]}")
            
        except Exception as e:
            logging.exception("Error getting commands:")
            return "\n".join(help_texts + [f"Error: {str(e)}"])
            
        if not commands:
            logging.warning("No commands found in command manager!")
            return "\n".join(help_texts + ["No commands available"])
            
        max_name_length = max((len(cmd.name) for cmd in commands), default=0)
        
        # Add each command's help summary
        for cmd in sorted(commands, key=lambda c: c.name):
            # Get the first line of the command's help text
            try:
                help_text = cmd.help_text()
                if isinstance(help_text, str):
                    first_line = help_text.split('\n', 1)[0].strip()
                else:
                    first_line = str(help_text).split('\n', 1)[0].strip()
                logging.debug(f"Help text for {cmd.name}: {first_line[:50]}...")
            except Exception as e:
                logging.error(f"Error getting help for {cmd.name}: {str(e)}")
                first_line = "No help available"
                
            help_texts.append(f"  {cmd.name.ljust(max_name_length)}  {first_line}")
        
        help_texts.extend(["", "Type 'help <command>' for more info on a command."])
        return "\n".join(help_texts)
        
        
    def register_command(command: Command):
        """Register the 'help' command."""
        return HelpCommand()

def run_tests():
    """Run all command registration and help system tests."""
    # Set up logging with debug level
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('command_tests.log', mode='w')
        ]
    )
    
    # Import needed components
    from base import Command, CommandResult
    from manager import CommandManager, command_manager
    
    # Create test command class
    class TestCommand(Command):
        name = "test"
        aliases = ["t", "te", "tes"]

        def help_text(self) -> str:
            return f"This is help text for the {self.name} command."
            
        async def _execute(self, data: Dict[str, Any]) -> CommandResult:
            return CommandResult(success=True, message="Test command executed")

    # Use the global command manager for testing
    test_manager = command_manager
    test_manager._commands = {}  # Reset any existing commands
    
    # Test 0: Show initial state (should be empty)
    print("\n" + headline("TEST 0: Initial state (should be empty)"))
    test_manager.show_registered_commands()
    
    # Create command instances
    help_cmd = HelpCommand()
    test_cmd = TestCommand()
    
    # Test 1: Register commands
    print("\n" + headline("TEST 1: Registering commands"))
    print("Registering 'help' command...")
    test_manager.register_command(help_cmd)
    print("Registering 'test' command...")
    test_manager.register_command(test_cmd)
    
    # Show current registered commands
    print("\nCurrent registered commands:")
    test_manager.show_registered_commands()
    
    # Set up context for help command
    help_cmd.context = {'command_manager': test_manager}
    
    # Test 2: Get help for all commands
    print("\n" + headline("TEST 2: Help for all commands"))
    print(help_cmd.help_text())
    
    # Test 3: Get help for specific command
    print("\n" + headline("TEST 3: Help for 'test' command"))
    print(test_manager.get_help_text("test"))
    
    # Test 4: Get help using alias
    print("\n" + headline("TEST 4: Help using alias 't'"))
    print(test_manager.get_help_text("t"))
    
    # Test 5: Get non-existent command help
    print("\n" + headline("TEST 5: Non-existent command"))
    print(test_manager.get_help_text("nonexistent"))
    
    # Test 6: Try to register duplicate command (should show warning)
    print("\n" + headline("TEST 6: Register duplicate command"))
    print("Trying to register 'help' command again...")
    test_manager.register_command(help_cmd)  # Should show warning
    
    # Test 7: Show final registered commands
    print("\n" + headline("TEST 7: Final registered commands"))
    test_manager.show_registered_commands()
    
    # Return the test manager for further inspection if needed
    return test_manager

if __name__ == "__main__":
    run_tests()