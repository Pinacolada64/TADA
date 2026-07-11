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
import re
import textwrap
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from commands.base_command import Command, Mode
from formatting import hrule_char, _visible_len

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Color scheme -- |token| markup, resolved per-terminal by
# formatting.ansi_encode()/petscii_encode() downstream in ctx.send(). Same
# four tokens render correctly on both ANSI and PETSCII (see
# formatting.ANSI_COLOR_CODES / PETSCII_CONTROL_CODES).
# ---------------------------------------------------------------------------

def _heading(text: str) -> str:
    """Section headings and titles: 'Usage:', category names, etc."""
    return f'|yellow|{text}|reset|'


def _rule(text: str) -> str:
    """Horizontal rule lines."""
    return f'|dark_gray|{text}|reset|'


def _cmd(text: str) -> str:
    """A command (or topic) name."""
    return f'|cyan|{text}|reset|'


def _alias(text: str) -> str:
    """A command's alias(es) -- deliberately darker/dimmer than _cmd()."""
    return f'|dark_gray|{text}|reset|'


def _vis_ljust(text: str, width: int) -> str:
    """Left-justify *text* to *width* visible columns, ignoring |token| markup
    (str.ljust() would otherwise pad based on raw length, under-padding any
    colored text and breaking column alignment)."""
    pad = width - _visible_len(text)
    return text + (' ' * pad if pad > 0 else '')


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


# One-line description of each category, shown by "help categories"/"help #cat".
_CATEGORY_DESCRIPTIONS: Dict["HelpCategory", str] = {
    HelpCategory.ADMINISTRATIVE: "Admin-only tools: banning, editing players/monsters, server control.",
    HelpCategory.AUTHENTICATION: "Logging in, creating a character, and connecting to the game.",
    HelpCategory.COMBAT:         "Attacking, fleeing, and other fighting mechanics.",
    HelpCategory.COMMUNICATION:  "Talking to other players: say, shout, whisper, page, mail.",
    HelpCategory.CONCEPT:        "Explanations of game terms and ideas, not tied to one command.",
    HelpCategory.GENERAL:        "Everyday actions: inventory, items, equipment, food and drink.",
    HelpCategory.INTERACTION:    "Interacting with objects, allies, and the world around you.",
    HelpCategory.MISCELLANEOUS:  "Commands that don't fit neatly into another category.",
    HelpCategory.MOVEMENT:       "Moving around the world: compass directions, looking, teleporting.",
}


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
    # Extra notes appended only for viewers with PlayerFlags.ADMIN or
    # DUNGEON_MASTER set -- e.g. admin-only switches or behavior that would
    # just be noise (or an unwanted hint) for a regular player. See
    # format_help()'s is_privileged parameter / _is_privileged_viewer().
    admin_notes: List[str]             = field(default_factory=list)


# ---------------------------------------------------------------------------
# Standalone help topics — not tied to any Command, so they work anywhere
# 'help' does, including the LOGIN prompt (help itself is Mode.ANY) before a
# player has even connected. Use for background/concept explanations that
# don't belong to one specific command (HelpCategory.CONCEPT).
# ---------------------------------------------------------------------------

_TOPICS: Dict[str, Help] = {}


def register_topic(*names: str, help_obj: Help) -> None:
    """Register a standalone help topic under one or more names/aliases."""
    for n in names:
        _TOPICS[n.lower()] = help_obj


register_topic(
    "about", "tada", "mud", "whatisthis",
    help_obj=Help(
        summary="What is TADA?",
        description=(
            "TADA -- \"Totally Awesome Dungeon Adventure\" -- is a MUD "
            "(Multi-User Dungeon): a text-based, multi-player online game "
            "world you explore, fight monsters, and talk to other players "
            "in, all through typed commands.\n\n"
            "It's a modern re-implementation of \"The Land of Spur,\" a "
            "1980s Apple BBS door game, originally single-player and "
            "played one at a time over dial-up. TADA rebuilds it as a real "
            "multi-player game with a Python client/server (and, "
            "eventually, a native Commodore 64 client) so many "
            "adventurers can share the same dungeon at once."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("connect guest",              "Look around without an account."),
            ("new",                        "Create a character and dive in."),
            ("help",                       "See what commands are available."),
        ],
        notes=[
            "The original game is still playable: telnet://dura-bbs.net:6359",
        ],
    ),
)

register_topic(
    "commandline", "command-line", "switches", "parameters",
    help_obj=Help(
        summary="How command syntax works: switches vs. parameters",
        description=(
            "Most commands take plain words as parameters -- the actual "
            "thing you're acting on, like a player name, item name, or "
            "number: `page Alice=Hello`, `teleport 42`.\n\n"
            "A token starting with '#' is a switch instead: a flag or "
            "sub-option that changes how the command behaves, rather than "
            "data the command acts on. Switches are usually specific to "
            "the command they're used with -- `groups #add friends Alice`, "
            "`ban #view`, `wa #hide` -- so check a command's own `help "
            "<command>` for what its switches do."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("<command> <parameter>",  "Plain words: data the command acts on."),
            ("<command> #<switch>",    "A '#'-prefixed flag: changes command behavior."),
        ],
        examples=[
            ("page Alice=Hello",        "'Alice=Hello' is the parameter."),
            ("groups #add friends Bob", "'#add' is the switch; 'friends Bob' are its own parameters."),
        ],
        notes=[
            "A command-specific switch (like '#hide' or '#add') only makes "
            "sense to the command that defines it -- see that command's "
            "own help for details.",
        ],
        # Admin/DM-only -- #version/#ver is itself gated to those flags in
        # commands/command_processor.py, so regular players don't need (or
        # get shown) this detail. See format_help()'s is_privileged param.
        admin_notes=[
            "'#version'/'#ver' works the same way on every command (e.g. "
            "'attack #version') -- reports when that command's own code "
            "was last changed instead of running it. Handled centrally in "
            "command_processor.py, gated to Admin/Dungeon Master.",
        ],
    ),
)

register_topic(
    "rooms", "room",
    help_obj=Help(
        summary="What's a \"room\"?",
        description=(
            "In TADA (and MUDs generally), \"room\" is the traditional term "
            "for any single space you can occupy -- it doesn't mean an "
            "indoor space with four walls. A forest clearing, a mountain "
            "ledge, a stretch of open road, and an actual indoor chamber "
            "are all \"rooms\": each one is just a distinct location with "
            "its own description, exits, and contents.\n\n"
            "This comes from the genre's text-adventure roots, where the "
            "world is a network of discrete locations connected by exits "
            "(north, south, up, down, ...) rather than a continuous map. "
            "Don't take \"room\" too literally -- outdoors, underground, "
            "in a building, it's all the same concept under the hood."
        ),
        category=HelpCategory.CONCEPT,
        usage=[
            ("look",  "Show the room you're currently in again."),
            ("n/s/e/w/u/d", "Move to an adjacent room in that direction."),
        ],
    ),
)


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


def _is_privileged_viewer(ctx) -> bool:
    """Whether ctx's player has PlayerFlags.ADMIN or DUNGEON_MASTER set --
    gates Help.admin_notes (see format_help()'s is_privileged param).
    Safe to call with a ctx that has no real player (e.g. the LOGIN-mode
    fallback dict some tests pass): returns False rather than raising.
    """
    player     = getattr(ctx, "player", None)
    query_flag = getattr(player, "query_flag", None)
    if not callable(query_flag):
        return False
    from flags import PlayerFlags
    try:
        return bool(query_flag(PlayerFlags.ADMIN) or query_flag(PlayerFlags.DUNGEON_MASTER))
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Formatter  (pure — no I/O)
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """Escape [optional] syntax notation so highlight_brackets renders it literally."""
    return re.sub(r'\[([^\[\]]+)\]', r'[[\1]]', text)


def format_two_column(items: List[Tuple[str, str]], width: int) -> List[str]:
    """Render (left, right) pairs as an aligned two-column block.

    `left` is left-padded to a shared column width; `right` is word-wrapped
    to fit what's left of `width`, with continuation lines aligned under it.
    Every returned line already fits within `width`, so it's safe to send
    each one as its own ctx.send() argument -- the client-side formatter
    re-wraps by splitting on spaces, which would otherwise mangle manual
    alignment (and ignore embedded '\\n's) if lines were pre-joined into one
    string instead.

    Used for Usage/Examples-style (syntax, description) listings in
    format_help(), and for HelpCommand's category listing.
    """
    out: List[str] = []
    if not items:
        return out
    left_col  = min(max(len(s) for s, _ in items), int(width * 0.4), 30)
    left_col  = max(left_col, 10)
    right_col = max(width - 4 - left_col - 2, 10)

    for left, right in items:
        if right:
            wrapped = textwrap.wrap(right, width=right_col) or [""]
            out.append(f"  {left.ljust(left_col)}  {wrapped[0]}")
            for cont in wrapped[1:]:
                out.append(f"  {'':{left_col}}  {cont}")
        else:
            out.append(f"  {left}")
    return out


def format_help(help_obj: Help, command_name: str = "", width: int = 78,
                rule_char: str = "-", is_privileged: bool = False) -> Optional[str]:
    """Format a Help instance into a display string.

    :param help_obj: Help (or a str, or None)
    :param command_name: shown as a header when present
    :param width: total line width; defaults to 78 columns
    :param rule_char: character to use for a horizontal rule line
    :param is_privileged: when True, help_obj.admin_notes are appended to
        the Notes section (see Help.admin_notes) -- pass
        _is_privileged_viewer(ctx) from a call site that has a live ctx.
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
            # (gap computed from the plain, uncolored lengths -- color
            # markup is applied after, so it doesn't throw off the math)
            gap      = width - len(command_name) - len(cat_str)
            if gap >= 1:
                lines.append(_cmd(command_name) + " " * gap + _heading(cat_str))
            else:
                lines.append(_cmd(command_name))
                if cat_str:
                    lines.append(_heading(cat_str.rjust(width)))
        lines.extend(textwrap.wrap(str(summary).strip(), width=width))
        lines.append(_rule(rule_char * width))

    # Description — blank lines in the source string (\n\n) become paragraph
    # breaks; each paragraph is wrapped independently so multi-paragraph
    # descriptions (e.g. concept topics) don't collapse into one block.
    desc = getattr(help_obj, "description", None)
    if desc and desc != "No description available.":
        lines.append("")
        paragraphs = str(desc).strip().split("\n\n")
        for i, para in enumerate(paragraphs):
            if i:
                lines.append("")
            lines.extend(textwrap.wrap(" ".join(para.split()), width=wrap_width))

    # Usage
    usage = getattr(help_obj, "usage", None)
    if usage:
        lines.append("")
        lines.append(_heading("Usage:"))
        items = [(_esc(str(u[0])), str(u[1]) if len(u) > 1 and u[1] else "")
                 for u in usage]
        lines.extend(format_two_column(items, width))

    # Examples
    examples = getattr(help_obj, "examples", None)
    if examples:
        lines.append("")
        lines.append(_heading("Example:" if len(examples) == 1 else "Examples:"))
        for item in examples:
            lines.append(f"  {_esc(item[0])}")
            if len(item) > 1 and item[1]:
                lines.extend(textwrap.wrap(
                    str(item[1]),
                    width=wrap_width,
                    initial_indent=" " * 6,
                    subsequent_indent=" " * 6,
                ))

    # Notes (admin_notes appended only for privileged viewers -- see
    # Help.admin_notes / this function's is_privileged parameter)
    notes = list(getattr(help_obj, "notes", None) or [])
    if is_privileged:
        notes += list(getattr(help_obj, "admin_notes", None) or [])
    if notes:
        lines.append("")
        lines.append(_heading("Notes:"))
        for note in notes:
            if note == '':
                lines.append('')
            else:
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
            return await self._show_categories_list(ctx)

        # Search
        if token in ("search", "find") and rest:
            return await self._help_search(ctx, " ".join(rest), processor)

        # Category name used directly (e.g. "help movement")
        for cat in HelpCategory:
            if token in (cat.value.lower(), cat.name.lower()):
                return await self._show_category_help(ctx, token, processor)

        # Standalone concept topic (e.g. "help about") -- not tied to a
        # Command, so this works even at the LOGIN prompt before a player
        # has connected.
        if token in _TOPICS:
            return await self._show_topic_help(ctx, token)

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
        title = f"{'Available Commands by Category':^{width}}"
        lines = [f"\n{_heading(title)}",
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
            lines.append(f"\n{_heading(cat.value.upper() + ':')}")
            lines.append(_rule(rchar * (len(cat.value) + 1)))
            entries = []
            for cmd in cmds:
                name = getattr(cmd, "name", "?")
                als  = [a for a in (getattr(cmd, "aliases", []) or []) if a != name]
                alias_str = f" ({', '.join(als)})" if als else ""
                entries.append(_cmd(name) + (_alias(alias_str) if alias_str else ""))

            col_w  = max(_visible_len(e) for e in entries) + 2
            n_cols = max(1, min(3, (width - 4) // (col_w + 2)))
            for i in range(0, len(entries), n_cols):
                lines.append("  " + "  ".join(_vis_ljust(e, col_w) for e in entries[i : i + n_cols]))

        lines += ["", "Type 'help <command>' for more detail."]
        await ctx.send(*lines)
        return CommandResult.ok("General help displayed.")

    async def _show_categories_list(self, ctx) -> Any:
        from commands.base_command import CommandResult

        # format_two_column() returns lines already wrapped to fit width, so
        # sending each as its own ctx.send() argument (not pre-joined into
        # one string) reaches the player intact -- ctx.send() re-wraps every
        # item to the player's actual screen width by splitting on spaces,
        # which would otherwise mangle manual alignment and treat embedded
        # '\n' characters as just more text instead of line breaks.
        width = self._screen_width(ctx)
        items = [(cat.value, _CATEGORY_DESCRIPTIONS.get(cat, "")) for cat in HelpCategory]

        lines = [_heading("Available categories:"), ""]
        lines.extend(format_two_column(items, width))
        lines.append("")
        lines.append("Type 'help #cat <category>' to list its commands/topics.")
        await ctx.send(*lines)
        return CommandResult.ok()

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

        # Standalone topics (e.g. "about") registered under this category —
        # these aren't Commands, so they're listed separately from names above.
        topics = sorted({n for n, h in _TOPICS.items() if h.category == matched})

        if not names and not topics:
            await ctx.send(f"No commands in category '{matched.value}'.")
            return CommandResult.ok()

        lines = [_heading(f"Commands in {matched.value}:")]
        lines += [f"  {_cmd(n)}" for n in sorted(names)]
        if topics:
            lines.append(_heading("Topics:"))
            lines += [f"  {_cmd(n)}" for n in topics]
        await ctx.send(*lines)
        return CommandResult.ok()

    async def _help_search(self, ctx, term: str, processor) -> Any:
        from commands.base_command import CommandResult

        matches = processor.search_commands(term) if processor else []
        if not matches:
            await ctx.send(f"No commands found matching '{term}'.")
            return CommandResult.ok()

        names = sorted(getattr(c, "name", "?") for c in matches)
        lines = [_heading(f"Commands matching '{term}':")] + [f"  {_cmd(n)}" for n in names]
        await ctx.send(*lines)
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
                                    rule_char=rchar, is_privileged=_is_privileged_viewer(ctx))
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

    async def _show_topic_help(self, ctx, topic_name: str) -> Any:
        """Display a standalone concept topic (e.g. 'help about') -- not
        backed by a Command, so this works before login too."""
        from commands.base_command import CommandResult

        width     = self._screen_width(ctx)
        rchar     = hrule_char(ctx)
        help_obj  = _TOPICS[topic_name]
        formatted = format_help(help_obj, command_name=topic_name, width=width,
                                rule_char=rchar, is_privileged=_is_privileged_viewer(ctx))
        if formatted:
            await ctx.send(*formatted)
            return CommandResult.ok("\n".join(formatted))

        await ctx.send(f"No detailed help available for '{topic_name}'.")
        return CommandResult.fail(error="no_help")
