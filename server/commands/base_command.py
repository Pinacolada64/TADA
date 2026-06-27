#!/usr/bin/env python3
"""base_command.py

Base class and supporting types for all TADA commands.

Every command lives in commands/ as a subclass of Command.  The command
processor scans that package on startup, finds every Command subclass that
has an execute() method, and registers it automatically.

Typical usage
-------------

    from commands.base_command import Command, CommandResult, Mode
    from help import Help, HelpCategory

    class SayCommand(Command):
        name    = "say"
        aliases = ["'"]
        modes   = {Mode.GAME}           # only available in-game

        help = Help(
            summary  = "Say something to everyone in your room.",
            category = HelpCategory.COMMUNICATION,
            usage    = [("say <message>", "Speak aloud.")],
        )

        async def execute(self, ctx, *args):
            args, switches = self.parse_args(*args)
            text = " ".join(args)
            if not text:
                await ctx.send("Say what?")
                return CommandResult(False, "No message.")
            await ctx.send(f'You say: "{text}"')
            await ctx.send_room(f'{ctx.player.name} says, "{text}"', exclude_self=True)
            return CommandResult(True)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mode — where is the player right now?
# ---------------------------------------------------------------------------

class Mode(Enum):
    """Player / connection mode used to gate command availability.

    Assign a set of Modes to Command.modes; the processor checks that the
    player's current mode is in that set before dispatching.

    LOGIN   — before authentication (connect, new, quit)
    GAME    — authenticated and in the game world
    ADMIN   — logged in and has administrative privileges
    ANY     — no restriction (e.g. help, quit)
    """
    LOGIN = auto()
    GAME  = auto()
    ADMIN = auto()
    ANY   = auto()


# ---------------------------------------------------------------------------
# CommandResult
# ---------------------------------------------------------------------------

@dataclass
class CommandResult:
    """Returned by every Command.execute() call.

    Attributes
    ----------
    success : bool
        True if the command completed without error.
    message : str
        Human-readable output (may be empty).
    error   : str
        Short machine-readable error token, e.g. "unknown_command".
        Empty string when success is True.
    data    : dict
        Optional structured payload for callers that need it.
    """
    success: bool
    message: str = ""
    error:   str = ""
    data:    Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "error":   self.error,
            "data":    self.data,
        }

    @classmethod
    def ok(cls, message: str = "") -> "CommandResult":
        return cls(success=True, message=message)

    @classmethod
    def fail(cls, message: str = "", error: str = "") -> "CommandResult":
        return cls(success=False, message=message, error=error)


# ---------------------------------------------------------------------------
# Command base class
# ---------------------------------------------------------------------------

class Command(ABC):
    """Abstract base for all TADA commands.

    Subclass and implement:
      - name      (str class attribute or property)
      - execute() (async method)

    Optionally override:
      - aliases   (list[str])
      - modes     (set[Mode])  — defaults to {Mode.GAME}
      - help      (Help dataclass instance)
    """

    # ------------------------------------------------------------------
    # Class-level defaults — subclasses may set these as class attributes
    # or override as properties.
    # ------------------------------------------------------------------

    #: Primary command name.  Must be set by every subclass.
    name: str = ""

    #: Alternative names / shortcuts.
    aliases: List[str] = []

    #: Modes in which this command is available.
    #: Override to restrict to LOGIN, GAME, ADMIN, or leave as ANY.
    modes: Set[Mode] = {Mode.GAME}

    #: Help metadata — attach a Help() instance here.
    help: Any = None  # type: ignore[assignment]  (Help imported in help.py)

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(self, ctx, *args) -> CommandResult:
        """Run the command.

        Parameters
        ----------
        ctx  : GameContext | TerminalContext
        args : str tokens after the command name, already split
        """

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    def parse_args(self, *args: str) -> Tuple[List[str], List[str]]:
        """Split positional args from switch args (tokens starting with '#').

        Returns
        -------
        (positional, switches)
            Both are lists of strings.  Switches are lowercased.

        Example
        -------
        >>> cmd.parse_args("hello", "world", "#verbose")
        (['hello', 'world'], ['#verbose'])
        """
        positional: List[str] = []
        switches:   List[str] = []
        for token in args:
            if token.startswith("#"):
                switches.append(token.lower())
            else:
                positional.append(token)
        return positional, switches

    def is_available_in(self, mode: Mode) -> bool:
        """Return True if this command can be used in *mode*."""
        return Mode.ANY in self.modes or mode in self.modes

    # Friendly repr for logging / debugging
    def __repr__(self) -> str:
        return f"<Command {self.name!r}>"