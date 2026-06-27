"""
commands/types.py

Shared types, enums, and the @command decorator.
Imported by both base_command.py and command_processor.py,
so neither needs to import from the other.

Import order:
    commands/types.py       <- no TADA imports
    commands/base_command.py  <- types.py
    commands/command_processor.py <- types.py, base_command.py
"""

import logging
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Type


# ---------------------------------------------------------------------------
# HelpCategory
# ---------------------------------------------------------------------------

class HelpCategory(Enum):
    """Categories used to group commands in help listings."""
    MOVEMENT     = auto()
    COMBAT       = auto()
    INVENTORY    = auto()
    COMMUNICATION = auto()
    INFORMATION  = auto()
    ADMINISTRATION = auto()
    MISCELLANEOUS = auto()


# ---------------------------------------------------------------------------
# CommandResult
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    """Represents the outcome of a command execution."""
    success: bool
    message: str | list[str] = ''
    error:   str             = ''
    lines:   List[str]       = field(default_factory=list)
    data:    Dict[str, Any]  = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# @command decorator
# ---------------------------------------------------------------------------

# Global registry: command name -> Command class
# Populated at import time when decorated command modules are loaded.
_DECORATED_COMMANDS: Dict[str, Type] = {}


def command(name:     str,
            aliases:  Optional[List[str] | str]          = None,
            category: HelpCategory                        = HelpCategory.MISCELLANEOUS,
            summary:  Optional[str]                       = None,
            example:  Optional[Tuple[str, str]]           = None,
            ) -> Callable[[Type], Type]:
    """
    Decorator to register a Command subclass with the global command registry.

    Usage:
        @command('look', aliases=['l'], category=HelpCategory.MOVEMENT,
                 summary='Describe the current room.')
        class LookCommand(Command):
            async def execute(self, ctx, args):
                ...

    :param name:     Primary command name (e.g. 'look').
    :param aliases:  One alias string or a list of alias strings.
    :param category: HelpCategory enum value for grouping in help output.
    :param summary:  One-line description shown in the command list.
    :param example:  Optional (usage, description) example tuple.
    """
    def decorator(cls: Type) -> Type:
        cls.name     = name
        cls.aliases  = ([aliases] if isinstance(aliases, str) else list(aliases or []))
        cls.category = category
        cls.summary  = summary or getattr(cls, 'summary', None)
        if example:
            cls.example = example

        _DECORATED_COMMANDS[name.lower()] = cls
        logging.debug('@command registered: %s', name)
        return cls

    return decorator