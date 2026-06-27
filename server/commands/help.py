#!/usr/bin/env python3
"""commands/help.py

Help metadata, formatter, and the HelpCommand itself.

Attach a Help() instance to every Command subclass:

    class SayCommand(Command):
        name = "say"
        help = Help(
            summary  = "Say something to players in your room.",
            category = HelpCategory.COMMUNICATION,
            usage    = [("say <message>", "Speak aloud to everyone here.")],
        )
"""

from __future__ import annotations

import logging
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from commands.base_command import Command, Mode
from formatting import hrule_char

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Help categories
# ---------------------------------------------------------------------------

class HelpCategory(Enum):
    ADMINISTRATIVE = "Administrative"   # boot, ban, shutdown, restart
    AUTHENTICATION = "Authentication"   # login, connect
    COMBAT         = "Combat"           # attack
    COMMUNICATION  = "Communication"    # say, shout, whisper, page, mail
    CONCEPT        = "Concept"          # rooms, exits, items, monsters
    GENERAL        = "General"
    INTERACTION    = "Interaction"
    MISCELLANEOUS  = "Miscellaneous"
    MOVEMENT       = "Movement"         # cardinal directions, teleport


# ---------------------------------------------------------------------------
# Help metadata dataclass
# ---------------------------------------------------------------------------

@dataclass
class Help:
    """Structured help metadata attached to a Command subclass.

    Example
    -------
        help = Help(
            summary     = "Say something to players in your room.",
            description = "The say command broadcasts a message to all players
                           currently in your room.",
            category    = HelpCategory.COMMUNICATION,
            usage       = [("say <message>", "Speak aloud.")],
            examples    = [("say Hello!", "Greet everyone nearby.")],
            notes       = ["Shouting reaches adjacent rooms."],
        )
    """
    summary:     str                   = "No summary available."
    description: str                   = "No description available."
    category:    HelpCategory          = HelpCategory.GENERAL
    usage:       List[Tuple[str, str]] = field(default_factory=list)
    examples:    List[Tuple[str, str]] = field(default_factory=list)
    notes:       List[str]             = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper function - guards against Mode.NONE instead of a set {Mode.NONE}
# ---------------------------------------------------------------------------

def _is_available(cmd, mode) -> bool:
    """Safe wrapper around cmd.is_available_in() — guards against modes=None or modes=Mode."""
    modes = getattr(cmd, "modes", None)
    if modes is None:
        return True   # no restriction declared → show it
    if isinstance(modes, set):
        from commands.base_command import Mode
        return Mode.ANY in modes or mode in modes
    return False      # misconfigured — hide it and log

# ---------------------------------------------------------------------------
# Formatter  (pure — no I/O)
# ---------------------------------------------------------------------------

def format_help(help_obj: Help, command_name: str = "", width: int = 78,
                rule_char: str = "-") -> Optional[str]:
    """Format a Help instance into a display string.

    :param help_obj: Help (or a str, or None)
    :param command_name: shown as a header when present
    :param width: total line width; defaults to 78 columns
    :param rule_char: character to use for a horizontal rule line
    """
    if help_obj is None:
        return None
    if isinstance(help_obj, str):
        return textwrap.fill(help_obj.strip(), width=width)

    wrap_width = width - 4
    lines: List[str] = []

    # Summary / header
    summary = getattr(help_obj, "summary", None)
    if summary:
        if command_name:
            cat      = getattr(help_obj, "category", None)
            cat_str  = f"Category: {cat.value.title()}" if cat else ""
            # Left: command name  Right: category label — padded to width
            gap      = width - len(command_name) - len(cat_str)
            if gap >= 1:
                lines.append(command_name + " " * gap + cat_str)
            else:
                lines.append(command_name)
                if cat_str:
                    lines.append(cat_str.rjust(width))
        lines.extend(textwrap.wrap(str(summary).strip(), width=width))
        lines.append(rule_char * width)

    # Description
    desc = getattr(help_obj, "description", None)
    if desc and desc != "No description available.":
        lines.append("")
        lines.extend(textwrap.wrap(str(desc).strip(), width=wrap_width))

    # Usage
    usage = getattr(help_obj, "usage", None)
    if usage:
        lines.append("")
        lines.append("Usage:")
        items = [(str(u[0]), str(u[1]) if len(u) > 1 and u[1] else "")
                 for u in usage]
        left_col  = min(max(len(s) for s, _ in items), int(width * 0.4), 30)
        left_col  = max(left_col, 10)
        right_col = width - 4 - left_col - 2

        for syntax, desc_text in items:
            if desc_text:
                wrapped = textwrap.wrap(desc_text, width=right_col) or [""]
                lines.append(f"  {syntax.ljust(left_col)}  {wrapped[0]}")
                for cont in wrapped[1:]:
                    lines.append(f"  {'':{ left_col}}  {cont}")
            else:
                lines.append(f"  {syntax}")

    # Examples
    examples = getattr(help_obj, "examples", None)
    if examples:
        lines.append("")
        lines.append("Example:" if len(examples) == 1 else "Examples:")
        for item in examples:
            lines.append(f"  {item[0]}")
            if len(item) > 1 and item[1]:
                lines.extend(textwrap.wrap(
                    str(item[1]),
                    width=wrap_width,
                    initial_indent=" " * 6,
                    subsequent_indent=" " * 6,
                ))

    # Notes
    notes = getattr(help_obj, "notes", None)
    if notes:
        lines.append("")
        lines.append("Notes:")
        for note in notes:
            lines.extend(textwrap.wrap(
                str(note),
                width=wrap_width,
                initial_indent=" " * 4,
                subsequent_indent=" " * 4,
            ))

    return lines if lines else None


# ---------------------------------------------------------------------------
# HelpCommand
# ---------------------------------------------------------------------------

class HelpCommand(Command):
    """The 'help' / 'h' / '?' command.

    Registered with CommandProcessor like any other Command.
    Reads the processor from ctx.client.command_processor.
    """

    name    = "help"
    aliases = ["h", "?"]
    modes   = {Mode.ANY}

    help = Help(
        summary     = "Display help for commands.",
        description = (
            "Lists available commands by category and shows detailed "
            "information about each one."
        ),
        category = HelpCategory.GENERAL,
        usage    = [
            ("help",               "List all available commands"),
            ("help <command>",     "Detailed help for a command"),
            ("help <category>",    "Commands in a category"),
            ("help #cat",          "List all categories"),
            ("help search <term>", "Search command names and descriptions"),
        ],
        examples = [
            ("help",      "Show all commands"),
            ("help say",  "Help for the 'say' command"),
            ("help #cat", "List all categories"),
        ],
        notes = [
            "You can use 'help', 'h', or '?' interchangeably.",
            "Command names are case-insensitive.",
        ],
    )

    async def execute(self, ctx, *args):
        from commands.base_command import CommandResult

        # Resolve processor: prefer ctx.client.command_processor, fall back to ctx itself
        processor = (
            getattr(getattr(ctx, "client", None), "command_processor", None)
            or getattr(ctx, "command_processor", None)
        )

        if not args:
            return await self._show_general_help(ctx, processor)

        token = args[0].lower()
        rest  = args[1:]

        # Category listing
        if token in ("categories", "category", "cat", "#cat", "#c"):
            if rest:
                return await self._show_category_help(ctx, rest[0].lower(), processor)
            cats = [c.value for c in HelpCategory]
            await ctx.send("Available categories:\n" + "\n".join(f"  {c}" for c in cats))
            return CommandResult.ok()

        # Search
        if token in ("search", "find") and rest:
            return await self._help_search(ctx, " ".join(rest), processor)

        # Category name used directly (e.g. "help movement")
        for cat in HelpCategory:
            if token in (cat.value.lower(), cat.name.lower()):
                return await self._show_category_help(ctx, token, processor)

        # Specific command
        return await self._show_command_help(ctx, token, processor)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _screen_width(ctx) -> int:
        try:
            return ctx.player.client_settings.screen_columns
        except AttributeError:
            return 78

    async def _show_general_help(self, ctx, processor) -> Any:
        from commands.base_command import CommandResult

        width = self._screen_width(ctx)
        rchar = hrule_char(ctx)
        lines = [f"\n{'Available Commands by Category':^{width}}",
                 "  help <command>: detailed help   |   help #cat: list categories\n"]

        current_mode = getattr(processor, "current_mode", None)
        all_cmds = [
            cmd for cmd in (processor.get_all_commands().values() if processor else [])
    if current_mode is None or _is_available(cmd, current_mode)
        ]
        by_cat: Dict = defaultdict(list)
        for cmd in all_cmds:
            help_obj = getattr(cmd, "help", None)
            cat      = getattr(help_obj, "category", HelpCategory.GENERAL)
            by_cat[cat].append(cmd)

        for cat in sorted(by_cat, key=lambda c: c.value):
            cmds = sorted(by_cat[cat], key=lambda c: getattr(c, "name", ""))
            lines.append(f"\n{cat.value.upper()}:")
            lines.append(rchar * (len(cat.value) + 1))
            entries = []
            for cmd in cmds:
                name = getattr(cmd, "name", "?")
                als  = [a for a in (getattr(cmd, "aliases", []) or []) if a != name]
                entries.append(name + (f" ({', '.join(als)})" if als else ""))

            col_w  = max(len(e) for e in entries) + 2
            n_cols = max(1, min(3, (width - 4) // (col_w + 2)))
            for i in range(0, len(entries), n_cols):
                lines.append("  " + "  ".join(e.ljust(col_w) for e in entries[i : i + n_cols]))

        lines += ["", "Type 'help <command>' for more detail."]
        await ctx.send(*lines)
        return CommandResult.ok("General help displayed.")

    async def _show_category_help(self, ctx, category_name: str, processor) -> Any:
        from commands.base_command import CommandResult

        matched = next(
            (c for c in HelpCategory
             if category_name in (c.value.lower(), c.name.lower())),
            None,
        )
        if not matched:
            await ctx.send(
                f"Unknown category '{category_name}'. Type 'help #cat' for a list."
            )
            return CommandResult.fail(error="unknown_category")

        current_mode = getattr(processor, "current_mode", None)
        all_cmds = [
            cmd for cmd in (processor.get_all_commands().values() if processor else [])
            if current_mode is None or cmd.is_available_in(current_mode)
        ]
        names = []
        for cmd in all_cmds:
            help_obj = getattr(cmd, "help", None)
            cat      = getattr(help_obj, "category", HelpCategory.GENERAL)
            if cat == matched:
                names.append(getattr(cmd, "name", "?"))

        if not names:
            await ctx.send(f"No commands in category '{matched.value}'.")
            return CommandResult.ok()

        await ctx.send(f"Commands in {matched.value}:\n  " + "\n  ".join(sorted(names)))
        return CommandResult.ok()

    async def _help_search(self, ctx, term: str, processor) -> Any:
        from commands.base_command import CommandResult

        matches = processor.search_commands(term) if processor else []
        if not matches:
            await ctx.send(f"No commands found matching '{term}'.")
            return CommandResult.ok()

        names = sorted(getattr(c, "name", "?") for c in matches)
        await ctx.send(f"Commands matching '{term}':\n  " + "\n  ".join(names))
        return CommandResult.ok()

    async def _show_command_help(self, ctx, command_name: str, processor) -> Any:
        from commands.base_command import CommandResult

        cmd = None
        if processor:
            cmd, _ = processor.find_command(command_name)

        if cmd is None:
            await ctx.send(
                f"No help found for '{command_name}'. "
                "Type 'help' for a list of commands."
            )
            return CommandResult.fail(error="no_help")

        width    = self._screen_width(ctx)
        rchar    = hrule_char(ctx)
        help_obj = getattr(cmd, "help", None)

        if help_obj and hasattr(help_obj, "summary"):
            formatted = format_help(help_obj, command_name=command_name, width=width,
                                    rule_char=rchar)
            if formatted:
                await ctx.send(*formatted)
                return CommandResult.ok("\n".join(formatted))

        # Fallback: docstring of execute()
        doc = getattr(getattr(cmd, "execute", None), "__doc__", None)
        if doc:
            await ctx.send(*doc.strip().splitlines())
            return CommandResult.ok(doc.strip())

        await ctx.send(f"No detailed help available for '{command_name}'.")
        return CommandResult.fail(error="no_help")
