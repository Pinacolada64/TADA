#!/bin/env python3
"""Help command implementation.

Provides help metadata formatting and a HelpCommand that works with
the project's command processor.

Depends on:
  - commands/base_command.py  (BaseCommand, CommandResult)
  - commands/command_processor.py  (CommandProcessor)
"""

import logging
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple


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
# Help metadata container  (attach one of these to every BaseCommand)
# ---------------------------------------------------------------------------

@dataclass
class CommandHelp:
    """Structured help metadata for a single command.

    Attach as a class variable on Command subclasses:

        class SayCommand(Command):
            name = 'say'
            help = CommandHelp(
                summary="Say something to players in your room.",
                category=HelpCategory.COMMUNICATION,
                usage=[("say <message>", "Speak aloud to everyone here")]
            )
    """
    summary:     str                        = "No summary available."
    description: str                        = ""
    category:    HelpCategory               = HelpCategory.GENERAL
    usage:       List[Tuple[str, str]]      = field(default_factory=list)
    examples:    List[Tuple[str, str]]      = field(default_factory=list)
    notes:       List[str]                  = field(default_factory=list)


# ---------------------------------------------------------------------------
# Formatter  (pure function – no server needed)
# ---------------------------------------------------------------------------

def format_help(
    help_obj,
    command_name: str = '',
    width: int = 80,
    max_width: Optional[int] = None,
) -> Optional[str]:
    """Format a CommandHelp (or compatible object) into a readable string.

    Also accepts:
    - a plain string  → word-wrapped and returned
    - a list of usage tuples  → normalised then formatted
    """
    if help_obj is None:
        return None

    max_w      = max_width or width or 80
    wrap_width = max_w - 4

    # Plain string
    if isinstance(help_obj, str):
        return textwrap.fill(help_obj.strip(), width=max_w)

    # List/tuple of usage tuples → normalise into a temporary namespace
    if isinstance(help_obj, (list, tuple)):
        try:
            if all(isinstance(item, (list, tuple)) for item in help_obj):
                tmp          = SimpleNamespace()
                tmp.summary  = None
                tmp.description = None
                tmp.usage    = [tuple(i) for i in help_obj]
                tmp.examples = []
                tmp.notes    = []
                help_obj     = tmp
            else:
                return "\n".join(str(x) for x in help_obj)
        except Exception:
            return "\n".join(str(x) for x in help_obj)

    lines: List[str] = []

    summary = getattr(help_obj, 'summary', None)
    if summary:
        if command_name:
            lines.append(command_name)
        lines.append(textwrap.fill(str(summary).strip(), width=max_w))
        lines.append("-" * max_w)

    desc = getattr(help_obj, 'description', None)
    if desc:
        lines.append("")
        lines.append(textwrap.fill(str(desc).strip(), width=wrap_width))

    usage = getattr(help_obj, 'usage', None)
    if usage:
        lines.append("")
        lines.append("Usage:")
        items: List[Tuple[str, str]] = [
            (str(i[0]), str(i[1]) if len(i) > 1 and i[1] else "")
            for i in usage
        ]
        left_col = min(max(len(s) for s, _ in items), int(max_w * 0.4), 30)
        left_col = max(left_col, 10)
        right_col = max_w - 4 - left_col - 2

        for syntax, desc_text in items:
            if desc_text:
                wrapped = textwrap.wrap(desc_text, width=right_col) or ['']
                lines.append(f"  {syntax.ljust(left_col)}  {wrapped[0]}")
                for cont in wrapped[1:]:
                    lines.append(f"  {'':{left_col}}  {cont}")
            else:
                lines.append(f"  {syntax}")

    examples = getattr(help_obj, 'examples', None)
    if examples:
        lines.append("")
        lines.append("Examples:")
        for item in examples:
            example   = str(item[0])
            desc_text = str(item[1]) if len(item) > 1 and item[1] else ""
            lines.append(f"  {example}")
            if desc_text:
                lines.append(textwrap.fill(
                    desc_text,
                    width=wrap_width,
                    initial_indent=' ' * 6,
                    subsequent_indent=' ' * 6,
                ))

    notes = getattr(help_obj, 'notes', None)
    if notes:
        lines.append("")
        lines.append("Notes:")
        for note in notes:
            lines.append(textwrap.fill(
                str(note), width=wrap_width,
                initial_indent=' ' * 4,
                subsequent_indent=' ' * 4,
            ))

    return "\n".join(lines) if lines else None


def _format_value(value, command_name: str, width: int = 80) -> str:
    """Normalise whatever a command returns from help_text() into a string."""
    if hasattr(value, 'summary') or hasattr(value, 'description') or hasattr(value, 'usage'):
        formatted = format_help(value, command_name, width=width)
        if formatted:
            return formatted
    if isinstance(value, (list, tuple)):
        return "\n".join(str(x) for x in value)
    if isinstance(value, str):
        return textwrap.fill(value, width=width)
    return str(value)


def _headline(text: str, width: int = 60, char: str = '=') -> str:
    return f"\n{text.center(width, char)}"


# ---------------------------------------------------------------------------
# Command-manager lookup helper
# ---------------------------------------------------------------------------

def _resolve_command_manager(context):
    """Return the command manager/processor from a context dict or object.

    Returns None if nothing useful is found.
    """
    keys = ('command_processor', 'command_manager', 'processor')

    if isinstance(context, dict):
        for key in keys:
            val = context.get(key)
            if val:
                return val
        # Enum-keyed or oddly-keyed dicts
        for k, v in context.items():
            if any(key in str(k).lower() for key in keys) and v:
                return v
    else:
        for attr in keys:
            val = getattr(context, attr, None)
            if val:
                return val

    # Last resort: global singletons
    try:
        from commands.command_processor import command_processor
        return command_processor
    except Exception:
        pass
    try:
        from commands.command_processor import command_manager
        return command_manager
    except Exception:
        pass
    return None


def _find_command(token: str, command_manager):
    """Locate a command by name or alias using whatever API the manager exposes."""
    # Strategy 1: get_command(name)
    if hasattr(command_manager, 'get_command'):
        try:
            cmd = command_manager.get_command(token)
            if cmd:
                return cmd
        except Exception:
            pass

    # Strategy 2: find_command(name) -> (instance, args)
    if hasattr(command_manager, 'find_command'):
        try:
            inst, _ = command_manager.find_command(token)
            if inst:
                return inst
        except Exception:
            pass

    # Strategy 3: walk get_all_commands()
    if hasattr(command_manager, 'get_all_commands'):
        try:
            all_cmds = command_manager.get_all_commands()
            if isinstance(all_cmds, dict):
                cmd = all_cmds.get(token)
                if cmd:
                    return cmd
                all_cmds = all_cmds.values()
            for c in all_cmds:
                name    = getattr(c, 'name',    '').lower()
                aliases = [a.lower() for a in getattr(c, 'aliases', [])]
                if token == name or token in aliases:
                    return c
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# BaseHelpText  (mix-in for HelpCommand)
# ---------------------------------------------------------------------------

class BaseHelpText:
    """Mix-in that provides the execute() logic and internal helpers for
    the HelpCommand.  Individual commands should use CommandHelp instead."""

    # HelpCommand's own metadata (used when someone types "help help")
    _help_meta = CommandHelp(
        summary     = "Display help for commands.",
        description = (
            "The 'help' command lists available commands and shows detailed "
            "information about each one. Commands are organised by category."
        ),
        category = HelpCategory.GENERAL,
        usage = [
            ("help",                         "List all available commands"),
            ("help <command>",               "Detailed help for a command"),
            ("help <category>",              "Commands in a category"),
            ("help #cat",                    "List all categories"),
            ("help search <term>",           "Search command names and descriptions"),
        ],
        examples = [
            ("help",         "Show all commands"),
            ("help say",     "Help for the 'say' command"),
            ("h go",         "Help for movement commands"),
            ("help #cat",    "List categories"),
        ],
        notes = [
            "You can use 'help', 'h', or '?' interchangeably.",
            "Command names are case-insensitive.",
        ],
    )

    async def execute(self, ctx, *args) -> Dict[str, Any]:
        """Entry point: resolve the command manager then dispatch."""
        # Accept either a GameContext object or a plain dict for context
        raw_ctx = ctx if isinstance(ctx, dict) else getattr(ctx, '__dict__', {})
        # Also try ctx itself as the source for _resolve_command_manager
        command_manager = _resolve_command_manager(ctx)

        if command_manager is None:
            from commands.base_command import CommandResult
            return CommandResult(
                success=False,
                message="Help unavailable: command manager not found",
            ).to_dict()

        if not args:
            return await self._show_general_help(command_manager)

        token = args[0].lower()
        rest  = args[1:]

        # Category listing / lookup
        if token in ("categories", "category", "cat", "#cat", "#c"):
            if rest:
                return await self._show_category_help(rest[0].lower(), command_manager)
            cats = [c.value for c in HelpCategory]
            from commands.base_command import CommandResult
            return CommandResult(
                success=True,
                message="Available categories:\n" + "\n".join(f"  {c}" for c in cats),
            ).to_dict()

        # Search
        if token in ("search", "find") and rest:
            return await self._help_search(" ".join(rest), command_manager)

        # Category name used directly (e.g. "help movement")
        for cat in HelpCategory:
            if token in (cat.value.lower(), cat.name.lower()):
                return await self._show_category_help(token, command_manager)

        # Specific command
        return await self._show_command_help(token, command_manager)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _show_general_help(self, command_manager) -> Dict[str, Any]:
        from commands.base_command import CommandResult
        lines = [_headline("Available Commands by Category")]
        lines.append("  help <command>    detailed help   |   help #cat   list categories\n")

        by_cat: Dict[HelpCategory, list] = defaultdict(list)
        all_cmds = command_manager.get_all_commands() or []
        for cmd in (all_cmds.values() if isinstance(all_cmds, dict) else all_cmds):
            cat = HelpCategory.GENERAL
            # Prefer new-style CommandHelp attribute
            ch = getattr(cmd, 'help', None)
            if ch and hasattr(ch, 'category'):
                cat = ch.category
            # Fall back to legacy help_info
            elif hasattr(cmd, 'help_info') and hasattr(cmd.help_info, 'category'):
                cat = cmd.help_info.category
            by_cat[cat].append(cmd)

        for cat in sorted(by_cat, key=lambda c: c.value):
            cmds = sorted(by_cat[cat], key=lambda c: getattr(c, 'name', ''))
            lines.append(f"\n{cat.value.upper()}:")
            lines.append("-" * (len(cat.value) + 1))
            entries = []
            for cmd in cmds:
                name    = getattr(cmd, 'name', '?')
                aliases = [a for a in getattr(cmd, 'aliases', []) if a != name]
                entries.append(f"{name}" + (f" ({', '.join(aliases)})" if aliases else ""))

            col_w   = max(len(e) for e in entries) + 2
            n_cols  = max(1, min(3, 76 // (col_w + 2)))
            for i in range(0, len(entries), n_cols):
                lines.append("  " + "  ".join(e.ljust(col_w) for e in entries[i:i + n_cols]))

        lines += ["", "Type 'help <command>' for more detail."]
        return CommandResult(success=True, message="\n".join(lines)).to_dict()

    async def _show_category_help(self, category_name: str, command_manager) -> Dict[str, Any]:
        from commands.base_command import CommandResult
        matched = next(
            (c for c in HelpCategory
             if category_name in (c.value.lower(), c.name.lower())),
            None,
        )
        if not matched:
            return CommandResult(
                success=False,
                message=f"Unknown category '{category_name}'. "
                        f"Type 'help #cat' for a list.",
            ).to_dict()

        all_cmds = command_manager.get_all_commands() or []
        names = []
        for cmd in (all_cmds.values() if isinstance(all_cmds, dict) else all_cmds):
            ch  = getattr(cmd, 'help', None)
            hi  = getattr(cmd, 'help_info', None)
            cat = (ch.category if ch and hasattr(ch, 'category')
                   else getattr(hi, 'category', None))
            if cat == matched:
                names.append(getattr(cmd, 'name', '?'))

        if not names:
            return CommandResult(
                success=True,
                message=f"No commands in category '{matched.value}'.",
            ).to_dict()

        return CommandResult(
            success=True,
            message=f"Commands in {matched.value}:\n  " + "\n  ".join(sorted(names)),
        ).to_dict()

    async def _help_search(self, term: str, command_manager) -> Dict[str, Any]:
        from commands.base_command import CommandResult
        term = term.lower()
        all_cmds = command_manager.get_all_commands() or []
        items    = (all_cmds.items() if isinstance(all_cmds, dict)
                    else [(getattr(c, 'name', ''), c) for c in all_cmds])
        matches  = []
        for cmd_name, cmd in items:
            name = (cmd_name or '').lower()
            if term in name:
                matches.append(cmd_name)
                continue
            # search summary / description text
            ch   = getattr(cmd, 'help', None)
            hi   = getattr(cmd, 'help_info', None)
            text = (getattr(ch, 'description', '') or getattr(hi, 'description', '') or
                    getattr(ch, 'summary', '')     or getattr(hi, 'summary', '') or '')
            if term in text.lower():
                matches.append(getattr(cmd, 'name', cmd_name))

        if not matches:
            return CommandResult(
                success=False,
                message=f"No commands found matching '{term}'.",
            ).to_dict()
        return CommandResult(
            success=True,
            message=f"Commands matching '{term}':\n  " + "\n  ".join(sorted(matches)),
        ).to_dict()

    async def _show_command_help(self, command_name: str, command_manager) -> Dict[str, Any]:
        from commands.base_command import CommandResult
        cmd = _find_command(command_name, command_manager)
        if cmd is None:
            return CommandResult(
                success=False,
                message=f"No help found for '{command_name}'. "
                        f"Type 'help' for a list of commands.",
            ).to_dict()

        # 1. New-style: CommandHelp dataclass on cmd.help
        ch = getattr(cmd, 'help', None)
        if ch and hasattr(ch, 'summary'):
            formatted = format_help(ch, command_name=command_name)
            if formatted:
                return CommandResult(success=True, message=formatted).to_dict()

        # 2. help_detail() method (produced by BaseCommand convenience method)
        if callable(getattr(cmd, 'help_detail', None)):
            return CommandResult(
                success=True, message=cmd.help_detail(),
            ).to_dict()

        # 3. Legacy: help_text() method or attribute
        ht_attr = getattr(cmd, 'help_text', None)
        if ht_attr is not None:
            ht = ht_attr() if callable(ht_attr) else ht_attr
            return CommandResult(
                success=True,
                message=_format_value(ht, command_name),
            ).to_dict()

        # 4. Legacy: structured help_info attribute
        hi = getattr(cmd, 'help_info', None)
        if hi:
            formatted = format_help(hi, command_name)
            if formatted:
                return CommandResult(success=True, message=formatted).to_dict()

        # 5. Last resort: execute() docstring
        doc = getattr(getattr(cmd, 'execute', None), '__doc__', None)
        if doc:
            return CommandResult(success=True, message=doc.strip()).to_dict()

        return CommandResult(
            success=False,
            message=f"No detailed help available for '{command_name}'.",
        ).to_dict()


# ---------------------------------------------------------------------------
# Concrete HelpCommand
# ---------------------------------------------------------------------------

class HelpCommand(BaseHelpText):
    """The 'help' command. Registered with the command processor like any
    other command; dispatches to BaseHelpText helpers."""

    name    = 'help'
    aliases = ['h', '?']
    help    = BaseHelpText._help_meta   # so "help help" works via the normal path

    def help_text(self) -> str:
        return self.help.summary

    def help_detail(self, width: int = 80) -> str:
        return format_help(self.help, command_name=self.name, max_width=width) or self.help.summary

    @staticmethod
    def register():
        return HelpCommand()
