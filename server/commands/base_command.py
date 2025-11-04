from typing import List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
import logging

# Try to import BaseHelpText from commands.help, but avoid hard dependency to prevent circular imports
try:
    from commands.help import BaseHelpText
except Exception:
    # Minimal fallback for cases when help module isn't available at import time
    class BaseHelpText:
        def __init__(self):
            self.name = "(no-help)"
            self.aliases = []
            self.category = None
            self.summary = ""
            self.description = ""

from net_common import Message


# -----------------
# 1. Command Result
# -----------------
@dataclass
class CommandResult:
    """Represents the outcome of a command execution."""
    success: bool
    message: str = ""
    error: str = ""
    lines: List[str] = field(default_factory=list) # Added 'lines' for multi-line output
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the CommandResult instance into a dictionary."""
        # dataclasses.asdict(self) is the canonical and safest way to convert
        # a dataclass instance (and its fields) into a dictionary.
        return asdict(self)


# -----------------
# 2. Help Category
# -----------------
class HelpCategory(Enum):
    """Categories for grouping commands."""
    GENERAL = auto()
    # n, e, s, w, u, d, etc.:
    MOVEMENT = auto()
    # page, whisper, etc.:
    COMMUNICATION = auto()
    # attack, etc.:
    COMBAT = auto()
    MISCELLANEOUS = auto()

# -----------------
# 3. Base Command Interface
# -----------------
class BaseCommand:
    """
    Base command interface. Metadata (name, aliases, category) is usually
    set by the @command decorator.
    """
    name: str = ""
    aliases: List[str] = field(default_factory=list)

    async def execute(self, context: Dict[str, Any], args: List[str]) -> CommandResult:
        """Execute the command with the given arguments and context."""
        raise NotImplementedError("Subclasses must implement execute()")


class HelpText(BaseHelpText):
    def __init__(self):
        super().__init__()
        self.category: HelpCategory = HelpCategory.MISCELLANEOUS
        self.summary: str = "A short summary of what the command is for."
        self.description: str = "Command description"
        self.usage: str = "command [<parameter>]"


class Command:
    logging.info("Command called")
