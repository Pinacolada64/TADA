from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import logging
from typing import Tuple, List, Dict, Any

from commands.command_processor import command
from help import HelpCategory, format_help

"""
To add a new command:

1. Create a new class in commands/ that inherits from Command.
2. Implement the required methods (name, execute, help_text)
3. Add the command class to register_commands() in server_commands.py

Each command is self-contained and includes its own help text by overriding the HelpCommand class from help.py.
"""

# -----------------
# 1. Command Result
# -----------------
@dataclass
class CommandResult:
    """Represents the outcome of a command execution."""
    # whether the command succeeded (True) or not (False):
    success: bool
    # any message to the player at the conclusion of executing the command:
    message: str = ""
    # the error message, if an error occurred:
    error: str = ""

    lines: List[str] = field(default_factory=list)  # Added 'lines' for multi-line output
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the CommandResult instance into a dictionary."""
        # dataclasses.asdict(self) is the canonical and safest way to convert
        # a dataclass instance (and its fields) into a dictionary.
        return asdict(self)


# -------------------------
# 3. Base Command Interface
# -------------------------
class Command:
    """
    Base command interface. Metadata (name, aliases, category) is usually
    set by the @command decorator.
    """
    from server.context import GameContext
    help = Help()

    async def execute(self, ctx: GameContext, *args: str) -> CommandResult:
        raise NotImplementedError("Subclasses must implement execute()")

    def help_text(self):
        """One-line summary of command, when 'help' is executed to list all commands"""
        return self.help.summary

    def help_details(self):
        """full formatted help, used by 'help <command>'"""
        return format_help(self.help, command_name=self.name, max_width=width)