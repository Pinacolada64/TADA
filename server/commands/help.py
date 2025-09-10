#!/bin/env python3
"""Help command implementation."""
from typing import Dict, Any, List
import logging

# TADA-specific imports:
from server.commands.base import Command, CommandResult
from server.command_manager import command_manager
from server.tada_utilities import oxford_comma_list


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
        return ["h"]
    
    def help_text(self) -> List[str]:
        """
        Return one of two forms of help text for this command:
        - The first list item should be a one-line summary.
        - The second list item should be a full description.
        """
        return [f"This is the one-line summary for the '{self.name}' command.",
                f"This is the full help text for the '{self.name}' command, which is "
                "displayed when you use 'help {self.name}'. It can be as long as you like."]

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
    
    def help_text(self, is_recursive=False) -> str:
        """Display one-line summaries of all registered commands when just "help" is called.
        
        Args:
            is_recursive: Internal flag to prevent recursion when getting help for the help command.
        """
        # Handle the case when help is called for the help command itself
        if is_recursive:
            return "Shows help about available commands.\nUse 'help <command>' for more info on a specific command."
            
        help_texts = [headline("Help Command"),
                     "Usage: 'help'",
                     "Displays brief summaries of all available commands.",
                     "",
                     "Usage: 'help' [command]",
                     "Displays detailed help for the specified command.",
                     "",
                     "Available commands:",
                     ""]
        
        # Get command manager from context
        command_manager = self.context.get('command_manager') if hasattr(self, 'context') else None
        if not command_manager:
            return "\n".join(help_texts + ["Error: Command manager not available in context"])
        
        # Get all commands and calculate max name length for alignment
        try:
            logging.debug("Getting all commands from command manager...")
            commands_dict = command_manager.get_all_commands()
            
            if not commands_dict:
                help_texts.append("No commands currently registered.")
                return "\n".join(help_texts)
                
            # Convert to list of unique commands (since aliases point to same command)
            unique_commands = []
            seen = set()
            for cmd in commands_dict.values():
                if id(cmd) not in seen:
                    seen.add(id(cmd))
                    unique_commands.append(cmd)
            
            commands = sorted(unique_commands, key=lambda c: c.name)
            logging.debug(f"Found {len(commands)} unique commands: {[c.name for c in commands]}")
            
            # Calculate max name length for alignment
            max_name_length = max((len(cmd.name) for cmd in commands), default=0)
            
            # Add each command's help summary
            for cmd in commands:
                # Skip adding help command to avoid recursion
                if cmd.name == 'help':
                    help_texts.append(f"  {cmd.name.ljust(max_name_length)}  Shows this help message")
                    continue
                    
                # Get the first line of the command's help text
                try:
                    help_summary = cmd.help_text() if hasattr(cmd, 'help_text') else "No help available"
                    if isinstance(help_summary, (list, tuple)):
                        # If it's a list, the first item is the one-line summary
                        first_line = help_summary[0] if help_summary else "No help available"
                        if isinstance(first_line, (list, tuple)) and len(first_line) > 1:
                            first_line = first_line[1]  # Get the description if available
                    elif isinstance(help_summary, str):
                        first_line = help_summary.split('\n', 1)[0].strip()
                    else:
                        first_line = str(help_summary).split('\n', 1)[0].strip()
                        
                    help_texts.append(f"  {cmd.name.ljust(max_name_length)}  {first_line}")
                    
                except Exception as e:
                    logging.error(f"Error getting help for {cmd.name}: {str(e)}")
                    help_texts.append(f"  {cmd.name.ljust(max_name_length)}  [Error getting help]")
            
            help_texts.extend(["", "Type 'help <command>' for more information about a specific command."])
            return "\n".join(help_texts)
            
        except Exception as e:
            logging.exception("Error in help command:")
            return "\n".join(help_texts + [f"Error: {str(e)}"])
        
        
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
    from server.commands.base import Command, CommandResult
    from server.commands.manager import command_manager
    
    # Create test command class
    class TestCommand(Command):
        def __init__(self):
            self.context = {}
            
        @property
        def name(self) -> str:
            return "test"
            
        @property
        def aliases(self) -> list:
            return ["t", "te", "tes"]

        def help_text(self) -> str:
            return f"This is help text for the {self.name} command."
            
        async def _execute(self, data: Dict[str, Any]) -> CommandResult:
            return CommandResult(success=True, message="Test command executed")

    # Create a fresh command manager for testing
    test_manager = command_manager
    test_manager._commands = {}  # Reset any existing commands
    
    # Test 0: Show initial state (should be empty)
    print("\n" + headline("TEST 0: Initial state (should be empty)"))
    test_manager.show_registered_commands()
    
    # Create command instances
    help_cmd = HelpCommand()
    test_cmd = TestCommand()
    
    # Set up context for commands
    help_cmd.context = {'command_manager': command_manager}
    test_cmd.context = {}
    
    # Test 1: Register commands
    print("\n" + headline("TEST 1: Registering commands"))
    print("Registering 'help' command...")
    test_manager.register_command(help_cmd)
    print("Registering 'test' command...")
    test_manager.register_command(test_cmd)
    
    # Show current registered commands
    print("\nCurrent registered commands:")
    test_manager.show_registered_commands()
    
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