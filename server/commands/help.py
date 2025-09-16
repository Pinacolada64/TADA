#!/bin/env python3
"""Help command implementation."""
import sys
import os
from typing import Dict, Any, List, Tuple, Optional
import logging
import textwrap
from collections import defaultdict

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the required modules
from server.commands.base_command import Command, CommandResult
from server.commands.command_help import CommandHelp, HelpCategory

# Import command_manager after all other imports
from server.command_manager import command_manager


def __init__(self, 
                 summary: str = "", 
                 description: str = "", 
                 usage: List[Tuple[str, str]] = None,
                 examples: List[Tuple[str, str]] = None,
                 notes: List[str] = None):
        self.summary = summary
        self.description = description
        self.usage = usage or []
        self.examples = examples or []
        self.notes = notes or []
    
def format_help(self, command_name: str, max_width: int = 80) -> str:
    """Format the help text with proper wrapping."""
    import textwrap
    
    # Calculate indentation and wrap width
    indent = 4
    wrap_width = max_width - indent
        
    # Start building the help text
    lines = []
        
    # Add command name and summary
    if self.summary:
        lines.append(f"\n{command_name} - {self.summary}")
        lines.append("-" * max_width)
        
    # Add description
    if self.description:
        wrapped = textwrap.fill(self.description.strip(), width=wrap_width)
        lines.append(f"\n{wrapped}")
        
    # Add usage section
    if self.usage:
        lines.append("\nUsage:")
        for syntax, desc in self.usage:
            # Format the syntax line
            syntax_line = f"  {syntax}"
            lines.append(syntax_line)
                
            # Format and indent the description
            if desc:
                wrapped = textwrap.fill(
                    desc,
                    width=wrap_width,
                    initial_indent=' ' * (indent + 2),
                    subsequent_indent=' ' * (indent + 2)
                )
                lines.append(wrapped)
        
        # Add examples section
        if self.examples:
            lines.append("\nExamples:")
            for example, desc in self.examples:
                # Format the example line
                example_line = f"  {example}"
                lines.append(example_line)
                
                # Format and indent the description
                if desc:
                    wrapped = textwrap.fill(
                        desc,
                        width=wrap_width,
                        initial_indent=' ' * (indent + 2),
                        subsequent_indent=' ' * (indent + 2)
                    )
                    lines.append(wrapped)
        
        # Add notes section
        if self.notes:
            lines.append("\nNotes:")
            for note in self.notes:
                wrapped = textwrap.fill(
                    note,
                    width=wrap_width,
                    initial_indent=' ' * indent,
                    subsequent_indent=' ' * indent
                )
                lines.append(wrapped)
        
        return "\n".join(lines)

class HelpCommand(Command):
    """Handle the 'help' command."""
    
    name = "help"
    aliases = ["h", "?"]
    
    def __init__(self, context=None):
        super().__init__(context)
        self.help_info = CommandHelp(
            category=HelpCategory.SYSTEM,
            summary="Show help about commands",
            description=(
                "The help command provides information about available commands and their usage. "
                "Commands are organized into categories for easier navigation."
            ),
            usage=[
                ("help", "Show list of all available commands by category"),
                ("help <command>", "Show detailed help for a specific command"),
                ("help <category>", "Show all commands in a specific category")
            ],
            examples=[
                ("help", "Show all available commands by category"),
                ("help page", "Show help for the 'page' command"),
                ("? look", "Alternative way to get help for the 'look' command"),
                ("help auth", "Show all authentication-related commands")
            ],
            notes=[
                "You can use either 'help' or '?' to access help.",
                "Command names are case-insensitive.",
                "Some commands may have aliases (shown in parentheses)."
            ]
        )
    
    async def execute(self, context: Dict[str, Any], args: List[str]) -> Dict[str, Any]:
        """Execute the help command.
        
        Args:
            context: The command context
            args: Command arguments [command_name or category]
                
        Returns:
            Dict containing the help text result
        """
        if not args:
            # Show general help if no arguments
            return await self._show_general_help(command_manager, context)
            
        # Get the command or category name from args
        name = args[0].lower()
        
        # First check if it's a category
        for category in HelpCategory:
            if category.value.lower() == name:
                return await self._show_category_help(name, command_manager)
        
        # Then check if it's a command
        cmd = command_manager.get_command(name)
        if cmd is not None:
            return await self._show_command_help(name)
            
        # If we get here, it's neither a category nor a command
        return CommandResult(
            success=False,
            message=f"No help found for '{name}'. Type 'help' for a list of commands and categories."
        ).to_dict()
    
    async def _show_command_help(self, command_name: str) -> Dict[str, Any]:
        """Show detailed help for a specific command."""
        cmd = command_manager.get_command(command_name)
        if not cmd:
            return CommandResult(
                success=False,
                error="command_not_found",
                message=f"No help found for command: {command_name}"
            ).to_dict()
        
        # Get the formatted help text
        help_text = cmd.help_text
        
        return CommandResult(success=True, message=help_text).to_dict()
            

    async def _show_general_help(self, command_manager, context):
        """Show general help with commands organized by category.
        
        Args:
            command_manager: The command manager instance
            context: The command context
            
        Returns:
            CommandResult with the formatted help text
        """
        help_texts = [
            headline("Available Commands by Category"),
            "Type 'help <category>' to see commands in a specific category.",
            "Type 'help <command>' for detailed help about a specific command.\n"
        ]
        
        commands_by_category = defaultdict(list)
        
        # Group commands by category
        for cmd_name, cmd in command_manager.items():
            if hasattr(cmd, 'help_info') and hasattr(cmd.help_info, 'category'):
                category = cmd.help_info.category
            else:
                category = HelpCategory.GENERAL
            commands_by_category[category].append(cmd)
        
        # Sort categories alphabetically
        sorted_categories = sorted(commands_by_category.keys(), key=lambda c: c.value)
        
        # Generate help text for each category
        for category in sorted_categories:
            commands = sorted(commands_by_category[category], key=lambda c: c.name)
            help_texts.append(f"\n{category.value.upper()} (help {category.value.lower()}):")
            help_texts.append("-" * (len(category.value) + 14))  # +14 for ' (help XXXX):'
            
            # Group commands in columns for better readability
            cmd_list = []
            for cmd in commands:
                # Get aliases (excluding the command name itself)
                aliases = [a for a in getattr(cmd, 'aliases', []) if a != cmd.name]
                alias_text = f" ({', '.join(aliases)})" if aliases else ""
                cmd_list.append(f"{cmd.name}{alias_text}")
            
            # Format commands in columns
            col_width = max(len(cmd) for cmd in cmd_list) + 2  # +2 for padding
            num_cols = max(1, min(3, 80 // (col_width + 2)))
            
            # Split commands into rows
            for i in range(0, len(cmd_list), num_cols):
                row = cmd_list[i:i + num_cols]
                # Format each command with consistent width
                formatted_row = "  ".join(cmd.ljust(col_width) for cmd in row)
                help_texts.append(f"  {formatted_row}")
        
        # Add footer with help for specific commands
        help_texts.extend([
            "",
            "For more information on a specific command, type 'help <command>'.",
            "For commands in a specific category, type 'help <category>'.",
            "Example: 'help login' or 'help auth'"
        ])
        
        return CommandResult(
            success=True,
            message="\n".join(help_texts)
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
                    
                # Get the short summary of the command's help text
                try:
                    help_text = cmd.help_text()
                    if isinstance(help_text, (list, tuple)) and len(help_text) > 0:
                        help_text = help_text[0]  # Get the one-line summary
                    elif not isinstance(help_text, str):
                        help_text = f"No help available for {getattr(cmd, 'name', 'unknown')}"
                    help_texts.append(f"  {cmd.name.ljust(max_name_length)}  {help_text}")
                    
                except Exception as e:
                    logging.error(f"Error getting help for {cmd.name}: {str(e)}")
                    help_texts.append(f"  {cmd.name.ljust(max_name_length)}  [Error getting help]")
            
            help_texts.extend(["", "Type 'help <command>' for more information about a specific command."])
            return "\n".join(help_texts)
            
        except Exception as e:
            logging.exception("Error in help command:")
            return "\n".join(help_texts + [f"Error: {str(e)}"])
        
        
    @staticmethod
    def register_command():
        """Register the 'help' command."""
        return HelpCommand()

def headline(text, width=60, char='='):
    """Create a formatted headline for test output."""
    return f"\n{text.center(width, char)}"

def run_tests():
    """Run all command registration and help system tests."""
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('command_tests.log', mode='w')
        ]
    )
    
    # Import needed components - use the same imports as at the top of the file
    try:
        from .base_command import Command, CommandResult
        from ..command_manager import command_manager
    except (ImportError, ValueError):
        from server.commands.base_command import Command, CommandResult
        from server.command_manager import command_manager
    
    # Create test command class
    class TestCommand(Command):
        def __init__(self):
            self.context = {}
            self._name = "test"
            self._aliases = ["t"]
            
        @property
        def name(self) -> str:
            return self._name
            
        @property
        def aliases(self) -> List[str]:
            return self._aliases
            
        @property
        def help_summary(self) -> str:
            return "A test command for the help system"
            
        def help_text(self) -> str:
            return f"This is help text for the {self.name} command."
            
        async def execute(self, context: Dict[str, Any], args: List[str]) -> Dict[str, Any]:
            """Execute the test command.
            
            Args:
                context: The command context
                args: Command arguments
                
            Returns:
                Command result as a dictionary
            """
            return CommandResult(
                success=True, 
                message="Test command executed"
            ).to_dict()

    # Create a fresh command manager for testing
    test_manager = command_manager
    test_manager._commands = {}  # Reset any existing commands
    
    # Test 0: Initial state
    print("\n" + headline("TEST 0: Initial state (should be empty)"))
    print("Registered commands:", list(test_manager._commands.keys()))
    print("Registered aliases:", test_manager._aliases)
    
    # Create command instances
    help_cmd = HelpCommand()
    test_cmd = TestCommand()
    
    # Set up context for commands
    help_cmd.context = {'command_manager': command_manager}
    test_cmd.context = {}
    
    # Test 1: Register commands
    print("\n" + headline("TEST 1: Registering commands"))
    print("Registering 'help' command...")
    test_manager.register(help_cmd)
    print("Registering 'test' command...")
    test_manager.register(test_cmd)
    
    # Show current registered commands and aliases
    print("\nCurrent registered commands:", list(test_manager._commands.keys()))
    print("Current registered aliases:", test_manager._aliases)
    
    # Test 2: Get help for all commands
    print("\n" + headline("TEST 2: Help for all commands"))
    print(help_cmd.help_text())
    
    # Test 3: Get help for specific command
    print("\n" + headline("TEST 3: Help for 'test' command"))
    cmd = test_manager.get_command("test")
    print(cmd.help_text() if cmd else "Command not found")
    
    # Test 4: Get help using alias
    print("\n" + headline("TEST 4: Help using alias 't'"))
    cmd = test_manager.get_command("t")
    print(cmd.help_text() if cmd else "Command not found")
    
    # Test 5: Get non-existent command help
    print("\n" + headline("TEST 5: Non-existent command"))
    cmd = test_manager.get_command("nonexistent")
    print(cmd.help_text if cmd else "Command not found")
    
    # Test 6: Try to register duplicate command (should show warning)
    print("\n" + headline("TEST 6: Register duplicate command"))
    print("Trying to register 'help' command again...")
    test_manager.register(help_cmd)  # Should show warning
    
    # Test 7: Show final registered commands
    print("\n" + headline("TEST 7: Final registered commands"))
    print("Registered commands:", list(test_manager._commands.keys()))
    print("Registered aliases:", test_manager._aliases)
    
    # Return the test manager for further inspection if needed
    return test_manager

if __name__ == "__main__":
    run_tests()
