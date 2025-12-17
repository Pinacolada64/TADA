#!/bin/env python3
"""Help command implementation.

This module provides helpers to format detailed help for commands and a
HelpCommand implementation that integrates with the project's Command
interface.
"""

import sys
import os
from enum import Enum
from typing import Dict, Any, List, Tuple, Optional
import logging
import textwrap
from collections import defaultdict
import asyncio

from commands.command_processor import CommandProcessor

# Add the project root to the Python path (if necessary)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import core command types
from commands.base_command import CommandResult, Command


# Provide a local HelpCategory with string values so formatting code can call .value.upper()
class HelpCategory(Enum):
    CONCEPT = "Concept"
    GENERAL = "General"
    MOVEMENT = "Movement"
    COMMUNICATION = "Communication"
    INTERACTION = "Interaction"
    COMBAT = "Combat"
    MISCELLANEOUS = "Miscellaneous"


# File: `commands/help.py`
from typing import List, Tuple, Optional
import textwrap
import logging
from types import SimpleNamespace

def format_help(help_obj, command_name: str = '', width: int = 80, max_width: Optional[int] = None) -> Optional[str]:
    """
    Format a help object (has summary/description/usage/examples/notes) or a
    usage-style list of tuples into a readable string wrapped at max_width.

    Accepts either `width=` (used by tests) or `max_width=` (used elsewhere).
    If `help_obj` is a string it will be wrapped and returned.
    """
    if help_obj is None:
        return None

    max_w = max_width or width or 80
    indent = 4
    wrap_width = max_w - indent
    lines: List[str] = []

    # If a plain string was passed, just wrap and return
    if isinstance(help_obj, str):
        return textwrap.fill(help_obj.strip(), width=max_w)

    # If a list/tuple of usage tuples was passed directly, normalize into a tmp object
    if isinstance(help_obj, (list, tuple)):
        try:
            if all(isinstance(item, (list, tuple)) and len(item) >= 1 for item in help_obj):
                tmp = SimpleNamespace()
                tmp.summary = None
                tmp.description = None
                tmp.usage = [tuple(item) for item in help_obj]
                tmp.examples = []
                tmp.notes = []
                help_obj = tmp
            else:
                # fallback: join simple list as lines
                return "\n".join(str(x) for x in help_obj)
        except Exception:
            return "\n".join(str(x) for x in help_obj)

    # From here on help_obj is expected to be an object with attributes
    summary = getattr(help_obj, 'summary', None)
    if summary:
        lines.append(f"{command_name}\n" if command_name else "")
        lines.append(textwrap.fill(str(summary).strip(), width=max_w))
        lines.append("" + ("-" * max_w))

    desc = getattr(help_obj, 'description', None)
    if desc:
        wrapped = textwrap.fill(str(desc).strip(), width=wrap_width)
        lines.append("")
        lines.append(wrapped)

    usage = getattr(help_obj, 'usage', None)
    if usage:
        lines.append("")
        lines.append("Usage:")
        items: List[Tuple[str, str]] = []
        for item in usage:
            if isinstance(item, (list, tuple)) and len(item) >= 1:
                syntax = str(item[0])
                desc_text = str(item[1]) if len(item) > 1 and item[1] is not None else ""
            else:
                syntax = str(item)
                desc_text = ""
            items.append((syntax, desc_text))

        max_syntax_len = max((len(s) for s, _ in items), default=0)
        cap_left = max(12, int(max_w * 0.4))
        left_col = min(max_syntax_len, cap_left)
        left_col = max(left_col, 10)

        right_col = max_w - indent - left_col - 2
        if right_col < 20:
            extra_needed = 20 - right_col
            left_col = max(10, left_col - extra_needed)
            right_col = max_w - indent - left_col - 2

        for syntax, desc_text in items:
            if desc_text:
                wrapped_desc = textwrap.wrap(desc_text, width=right_col) or ['']
                first_line = wrapped_desc[0]
                lines.append(f"  {syntax.ljust(left_col)}  {first_line}")
                for cont in wrapped_desc[1:]:
                    lines.append(f"  {'':{left_col}}  {cont}")
            else:
                lines.append(f"  {syntax}")

    examples = getattr(help_obj, 'examples', None)
    if examples:
        lines.append("")
        lines.append("Examples:")
        for item in examples:
            if isinstance(item, (list, tuple)) and len(item) >= 1:
                example = str(item[0])
                desc_text = str(item[1]) if len(item) > 1 and item[1] is not None else ""
            else:
                example = str(item)
                desc_text = ""
            lines.append(f"  {example}")
            if desc_text:
                wrapped = textwrap.fill(
                    desc_text,
                    width=wrap_width,
                    initial_indent=' ' * (indent + 2),
                    subsequent_indent=' ' * (indent + 2)
                )
                lines.append(wrapped)

    notes = getattr(help_obj, 'notes', None)
    if notes:
        lines.append("")
        lines.append("Notes:")
        for note in notes:
            wrapped = textwrap.fill(str(note), width=wrap_width, initial_indent=' ' * indent, subsequent_indent=' ' * indent)
            lines.append(wrapped)

    if not lines:
        return None
    else:
        return "\n".join([l for l in lines if l is not None and l != ""])

def _format_help_output(self, value, command_name: str):
    """
    Normalize and format help output from help_text() or help_info.

    Accepts string, list of lines, or structured object with summary/description/usage.
    Returns a single string suitable for Message/CommandResult.
    """
    try:
        # Structured object: hand to format_help
        if hasattr(value, 'summary') or hasattr(value, 'description') or hasattr(value, 'usage'):
            formatted = format_help(value, command_name)
            if formatted:
                return formatted
    except Exception:
        pass

    # If value is a list/tuple of tuples (usage/examples style), try to format it
    if isinstance(value, (list, tuple)):
        try:
            if all(isinstance(item, (list, tuple)) and len(item) >= 1 for item in value):
                Tmp = SimpleNamespace()
                Tmp.summary = None
                Tmp.description = None
                Tmp.usage = [tuple(item) for item in value]
                Tmp.examples = []
                Tmp.notes = []
                formatted = format_help(Tmp, command_name)
                if formatted:
                    return formatted
        except Exception:
            pass

        logging.info("tuple: %s" % str(value))
        return "\n".join(str(x) for x in value)

    if isinstance(value, str):
        return textwrap.fill(value, width=80)

    return str(value)


class BaseHelpText:
    """
    Base container for command help metadata and a small executor wrapper.

    Design goals:
    - Provide safe defaults stored on underscored backing fields (e.g. _name).
    - Expose public properties (name, aliases, summary, description, usage, examples, notes)
      with simple getters and setters so subclasses may override behavior safely.
    - Keep execute() small and robust: resolve a command manager/processor from the
      provided context (or fall back to common module-level singletons), then delegate
      to internal helpers to produce the CommandResult dictionary.
    """

    def __init__(self):
        # punctuation helpers
        self.quotation = '"'
        self.apostrophe = "'"

        # Backing fields (always set) -- callers should use the public properties below.
        self._name: str = getattr(self, '_name', 'help')
        self._aliases: List[str] = getattr(self, '_aliases', ['h', '?'])
        self._category = getattr(self, '_category', HelpCategory.MISCELLANEOUS)
        self._summary: str = getattr(self, '_summary', 'A short summary of what the command is for.')
        self._description: str = getattr(self, '_description', (
            "The 'help' command provides information about available commands and their usage. "
            "Commands are organized into categories for ease of finding different types of commands."
        ))

        self._usage: List[Tuple[str, Optional[str]]] = getattr(self, '_usage', [
            ("help", "Show list of all available commands"),
            ("help <command>", "Show detailed help for a specific command"),
            ("help categories", "Show a list of all available categories"),
            ("help <category>", "Show all commands in category <category>"),
            ("help [search | find] <term>", "Search command names and descriptions for the text <term>")
        ])

        self._examples: List[Tuple[str, Optional[str]]] = getattr(self, '_examples', [
            ("help", "Show all available commands by category"),
            ("help page", "Show help for the 'page' command"),
            ("h go", "Show all movement-related commands"),
            ("? look", "Alternative way to get help for the 'look' command"),
            ("help comm", "Show all commands in the category starting with 'comm'")
        ])

        self._notes: List[str] = getattr(self, '_notes', [
            "You can use either 'help', 'h' or '?' to access help.",
            "Command names are case-insensitive.",
            "Some commands may have aliases (shown in parentheses)."
        ])

    # Properties (read/write) -------------------------------------------------
    @property
    def name(self) -> str:
        """Command name used in listings and lookups."""
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = str(value)

    @property
    def aliases(self) -> List[str]:
        return list(self._aliases)

    @aliases.setter
    def aliases(self, value: List[str]):
        self._aliases = list(value) if value is not None else []

    @property
    def category(self):
        return self._category

    @category.setter
    def category(self, value):
        self._category = value

    @property
    def summary(self) -> str:
        return self._summary

    @summary.setter
    def summary(self, value: str):
        self._summary = str(value)

    @property
    def description(self) -> str:
        return self._description

    @description.setter
    def description(self, value: str):
        self._description = str(value)

    @property
    def usage(self) -> List[Tuple[str, Optional[str]]]:
        return list(self._usage)

    @usage.setter
    def usage(self, value: List[Tuple[str, Optional[str]]]):
        self._usage = list(value) if value is not None else []

    @property
    def examples(self) -> List[Tuple[str, Optional[str]]]:
        return list(self._examples)

    @examples.setter
    def examples(self, value: List[Tuple[str, Optional[str]]]):
        self._examples = list(value) if value is not None else []

    @property
    def notes(self) -> List[str]:
        return list(self._notes)

    @notes.setter
    def notes(self, value: List[str]):
        self._notes = list(value) if value is not None else []

    # Execution entry point --------------------------------------------------
    async def execute(self, context: Dict[str, Any], args: List[str]) -> Dict[str, Any]:
        """
        Execute the help command: resolve the command manager/processor and
        dispatch to the appropriate helper based on arguments.
        """
        # Resolve command manager/processor from context or fallback imports.
        command_manager = None
        # Accept mapping-like contexts and object-like contexts.
        try:
            from collections.abc import Mapping
        except Exception:
            Mapping = dict

        if isinstance(context, Mapping):
            # 1) prefer explicit string keys
            for key in ('command_processor', 'command_manager', 'processor'):
                try:
                    val = context.get(key)
                except Exception:
                    val = None
                if val:
                    command_manager = val
                    break

            # 2) if not found, try keys that may be Enum members or other objects; check their str()
            if command_manager is None:
                for k, v in context.items():
                    try:
                        ks = str(k).lower()
                    except Exception:
                        ks = ''
                    if ks.endswith('command_processor') or ks.endswith('command_manager') or ks.endswith('processor'):
                        command_manager = v
                        break
        else:
            # non-mapping: try attribute access
            for attr in ('command_processor', 'command_manager', 'processor'):
                try:
                    val = getattr(context, attr)
                except Exception:
                    val = None
                if val:
                    command_manager = val
                    break

        if command_manager is None:
            # try common module-level singletons used by the project
            try:
                from commands.command_processor import command_processor as global_cp
                command_manager = global_cp
            except Exception:
                try:
                    from commands.command_processor import command_manager as global_cm
                    command_manager = global_cm
                except Exception:
                    command_manager = None

        if command_manager is None:
            return CommandResult(success=False, message="Help unavailable: command manager not found").to_dict()

        # No args -> general help
        if not args:
            return await self._show_general_help(command_manager, context)

        # Handle special tokens
        token = args[0].lower()
        rest = args[1:]

        if token in ("categories", "category", "cat", "#cat", "#c"):
            if rest:
                return await self._show_category_help(rest[0].lower(), command_manager)
            cats = [c.value for c in HelpCategory]
            return CommandResult(success=True, message="Available help categories:\n" + "\n".join(f"- {c}" for c in cats)).to_dict()

        if token in ("search", "find") and rest:
            term = " ".join(rest)
            return await self._help_search(term, command_manager)

        for cat in HelpCategory:
            if token == cat.value.lower() or token == cat.name.lower():
                return await self._show_category_help(cat.value.lower(), command_manager)

        # Otherwise treat token as command name/alias
        # We delegate the heavy lifting to the existing helper that looks up and formats help
        return await self._dispatch_command_help(token, command_manager)

    # Small helper to centralize command help dispatch
    async def _dispatch_command_help(self, token: str, command_manager) -> Dict[str, Any]:
        # Try different lookup strategies - helper methods in the module will handle formatting
        cmd = None
        try:
            if hasattr(command_manager, 'get_command'):
                cmd = command_manager.get_command(token)
        except Exception:
            cmd = None

        if cmd is None and hasattr(command_manager, 'find_command'):
            try:
                inst, _ = command_manager.find_command(token)
                if inst:
                    cmd = inst
            except Exception:
                pass

        if cmd is None and hasattr(command_manager, 'get_all_commands'):
            try:
                all_cmds = command_manager.get_all_commands()
                if isinstance(all_cmds, dict):
                    cmd = all_cmds.get(token)
                else:
                    for c in all_cmds:
                        try:
                            if getattr(c, 'name', '').lower() == token or token in [a.lower() for a in getattr(c, 'aliases', [])]:
                                cmd = c
                                break
                        except Exception:
                            continue
            except Exception:
                pass

        if cmd is None:
            return CommandResult(success=False, message=f"No help found for '{token}'. Type 'help' for a list of commands.").to_dict()

        # Use the module-level helper _show_command_help (already present below in file)
        return await self._show_command_help(token, command_manager)

    async def _help_search(self, term: str, command_manager) -> Dict[str, Any]:
        term = term.lower()
        matches = []
        all_cmds = {}
        try:
            all_cmds = command_manager.get_all_commands() or {}
        except Exception:
            try:
                # try attribute name used by different processors
                all_cmds = command_manager.commands or {}
            except Exception:
                all_cmds = {}

        # all_cmds may be a dict (name->cmd) or a list of command instances
        if isinstance(all_cmds, dict):
            iterable = list(all_cmds.items())
        else:
            iterable = [(getattr(cmd, 'name', '').lower(), cmd) for cmd in (all_cmds or [])]

        for cmd_name, cmd in iterable:
            try:
                if term in (cmd_name or '').lower():
                    matches.append(cmd_name)
                    continue
            except Exception:
                pass
            try:
                desc = getattr(cmd, 'help_info', None)
                if desc and hasattr(desc, 'description') and term in desc.description.lower():
                    matches.append(getattr(cmd, 'name', cmd_name))
            except Exception:
                pass

        if not matches:
            return CommandResult(success=False, message=f"No commands found matching '{term}'.").to_dict()

        return CommandResult(success=True, message=[f"Commands matching '{term}':", "\n- " + "\n- ".join(matches)]).to_dict()

    async def _show_category_help(self, category_name: str, command_manager) -> Dict[str, Any]:
        matched = None
        for cat in HelpCategory:
            if category_name == cat.value.lower() or category_name == cat.name.lower():
                matched = cat
                break
        if not matched:
            return CommandResult(success=False, message=f"No help category: {category_name}").to_dict()

        cmd_names = []
        all_cmds = command_manager.get_all_commands() or {}
        if isinstance(all_cmds, dict):
            iterable = list(all_cmds.items())
        else:
            iterable = [(getattr(cmd, 'name', '').lower(), cmd) for cmd in all_cmds]

        for name, cmd in iterable:
            try:
                cat = getattr(cmd, 'help_info', None)
                if cat and getattr(cat, 'category', None) == matched:
                    cmd_names.append(getattr(cmd, 'name', name))
            except Exception:
                continue

        if not cmd_names:
            return CommandResult(success=True, message=f"No commands in category {matched.value}.").to_dict()

        cmd_names.sort()
        return CommandResult(success=True, message=[f"Commands in {matched.value}:"] + cmd_names).to_dict()

    def _format_help_output(self, value, command_name: str):
        """Normalize and format help output from help_text() or help_info.

        Accepts string, list of lines, or structured object with summary/description/usage.
        Returns a single string suitable for Message/CommandResult.
        """
        try:
            # Structured object: hand to format_help
            if hasattr(value, 'summary') or hasattr(value, 'description') or hasattr(value, 'usage'):
                formatted = format_help(value, command_name)
                if formatted:
                    return formatted
        except Exception:
            pass

        if isinstance(value, (list, tuple)):
            logging.info("tuple: %s" % str(value))
            return "\n".join(str(x) for x in value)

        if isinstance(value, str):
            return textwrap.fill(value, width=80)

        return str(value)

    async def _show_command_help(self, command_name: str, command_manager) -> Dict[str, Any]:
        cmd = None
        try:
            if hasattr(command_manager, 'get_command'):
                cmd = command_manager.get_command(command_name)
        except Exception:
            cmd = None

        if cmd is None and hasattr(command_manager, 'find_command'):
            try:
                inst, _ = command_manager.find_command(command_name)
                if inst:
                    cmd = inst
            except Exception:
                pass

        if cmd is None and hasattr(command_manager, 'get_all_commands'):
            try:
                all_cmds = command_manager.get_all_commands()
                if isinstance(all_cmds, dict):
                    cmd = all_cmds.get(command_name)
                else:
                    for c in all_cmds:
                        try:
                            if getattr(c, 'name', '').lower() == command_name:
                                cmd = c
                                break
                            if command_name in [a.lower() for a in getattr(c, 'aliases', [])]:
                                cmd = c
                                break
                        except Exception:
                            continue
            except Exception:
                pass

        if not cmd:
            return CommandResult(success=False, error="command_not_found", message=f"No help found for command: {command_name}").to_dict()

        # Prefer a help_text() method/attribute if provided
        try:
            ht_attr = getattr(cmd, 'help_text', None)
            # If the request was 'help help' prefer a manpage-style output
            # from the module HelpCommand rather than relying on the registered
            # inline help instance which may not provide rich help_text().
            if command_name.lower() == 'help':
                try:
                    # Use this instance's help_text method to produce the recursive/manpage output.
                    manpage = self.help_text(is_recursive=True)
                    return CommandResult(success=True, message=manpage).to_dict()
                except Exception:
                    # fall back to existing strategies
                    pass

            if callable(ht_attr):
                ht = ht_attr()
                if asyncio.iscoroutine(ht):
                    ht = await ht
                formatted = self._format_help_output(ht, command_name)
                return CommandResult(success=True, message=formatted).to_dict()
            if ht_attr is not None:
                formatted = self._format_help_output(ht_attr, command_name)
                return CommandResult(success=True, message=formatted).to_dict()
        except Exception:
            pass

        # Try structured help_info
        hi = getattr(cmd, 'help_info', None)
        if hi:
            try:
                formatted = format_help(hi, command_name)
                if formatted:
                    return CommandResult(success=True, message=formatted).to_dict()
            except Exception:
                parts = []
                if getattr(hi, 'summary', None):
                    parts.append(str(hi.summary))
                if getattr(hi, 'description', None):
                    parts.append(str(hi.description))
                if getattr(hi, 'usage', None):
                    parts.append('\nUsage:')
                    for u in hi.usage:
                        # format usage as example, explanation
                        if isinstance(u, tuple):
                            parts.append(f"{u[0]} {u[1]}") # parts.append(str(u))
                return CommandResult(success=True, message="\n".join(parts)).to_dict()

        # Try to find a module-local Help provider class
        try:
            import importlib
            modname = getattr(cmd.__class__, '__module__', None)
            if modname:
                try:
                    module = importlib.import_module(modname)
                    for attr_name in dir(module):
                        if not attr_name.lower().endswith('help'):
                            continue
                        attr = getattr(module, attr_name)
                        try:
                            if isinstance(attr, type):
                                inst = None
                                try:
                                    inst = attr()
                                except Exception:
                                    continue
                                if hasattr(inst, 'summary') or hasattr(inst, 'description') or hasattr(inst, 'usage') or callable(getattr(inst, 'help_text', None)):
                                    ht = None
                                    try:
                                        if callable(getattr(inst, 'help_text', None)):
                                            ht = inst.help_text()
                                            if asyncio.iscoroutine(ht):
                                                ht = await ht
                                        else:
                                            ht = inst
                                            if ht:
                                                # format and return inside the try so any formatting errors are caught
                                                formatted = self._format_help_output(ht, command_name)
                                                return CommandResult(success=True, message=formatted).to_dict()

                                    except Exception:
                                        continue
                        except Exception:
                            continue
                except Exception:
                    pass
        except Exception:
            pass

        # Fallback to execute docstring
        doc = getattr(getattr(cmd, 'execute', None), '__doc__', None)
        if doc:
            return CommandResult(success=True, message=doc.strip()).to_dict()

        return CommandResult(success=False, message=f"No detailed help available for {command_name}").to_dict()

    async def _show_general_help(self, command_manager, context):
        help_texts: List[str] = []
        help_texts.append(headline("Available Commands by Category"))
        help_texts.append("Type 'help <category>' to see commands in a specific category.")
        help_texts.append("Type 'help <command>' for detailed help about a specific command.\n")

        commands_by_category = defaultdict(list)

        all_cmds = command_manager.get_all_commands() or []
        # all_cmds may be a dict or list
        if isinstance(all_cmds, dict):
            cmds_iter = list(all_cmds.values())
        else:
            cmds_iter = list(all_cmds)

        for cmd in cmds_iter:
            try:
                if hasattr(cmd, 'help_info') and hasattr(cmd.help_info, 'category'):
                    category = cmd.help_info.category
                else:
                    category = HelpCategory.GENERAL
                commands_by_category[category].append(cmd)
            except Exception:
                continue

        sorted_categories = sorted(commands_by_category.keys(), key=lambda c: c.value)

        for category in sorted_categories:
            commands = sorted(commands_by_category[category], key=lambda c: c.name)
            help_texts.append(f"\n{category.value.upper()} (help {category.value.lower()}):")
            help_texts.append("-" * (len(category.value) + 14))

            cmd_list = []
            for cmd in commands:
                aliases = [a for a in getattr(cmd, 'aliases', []) if a != getattr(cmd, 'name', None)]
                alias_text = f" ({', '.join(aliases)})" if aliases else ""
                cmd_list.append(f"{cmd.name}{alias_text}")

            if cmd_list:
                col_width = max(len(cmd) for cmd in cmd_list) + 2
            else:
                col_width = 20
            num_cols = max(1, min(3, 80 // (col_width + 2)))

            for i in range(0, len(cmd_list), num_cols):
                row = cmd_list[i:i + num_cols]
                formatted_row = "  ".join(cmd.ljust(col_width) for cmd in row)
                help_texts.append(f"  {formatted_row}")

        help_texts.extend(["", "For more information on a specific command, type 'help <command>'.", "For commands in a specific category, type 'help <category>'.", "Example: 'help login' or 'help movement'"])

        return CommandResult(success=True, message="\n".join(help_texts)).to_dict()

    def help_text(self, is_recursive: bool = False) -> str:
        """Return a one-line summary list used for the top-level 'help' output.

        If is_recursive is True, return a formatted manpage-style output for the help command itself.
        """
        if is_recursive:
            formatted = format_help(self, self.name, max_width=80)
            if formatted:
                return formatted
            return "\n".join([headline("Help Command"), "Usage: help", "Displays help information."])

        command_manager = getattr(self, 'context', {}).get('command_processor') if hasattr(self, 'context') else None
        if not command_manager:
            help_texts = []
            return "\n".join(help_texts + ["Error: Command manager not available in context"])

        try:
            logging.debug("Getting all commands from command manager...")
            commands_dict = command_manager.get_all_commands()

            if not commands_dict:
                return "No commands currently registered."

            unique_commands = []
            seen = set()
            for cmd in commands_dict.values():
                if id(cmd) not in seen:
                    seen.add(id(cmd))
                    unique_commands.append(cmd)

            commands = sorted(unique_commands, key=lambda c: c.name)
            max_name_length = max((len(cmd.name) for cmd in commands), default=0)

            help_texts = []
            for cmd in commands:
                if cmd.name == 'help':
                    help_texts.append(f"  {cmd.name.ljust(max_name_length)}  Shows this help message")
                    continue
                try:
                    help_text = cmd.help_text()
                    if isinstance(help_text, (list, tuple)) and len(help_text) > 0:
                        help_text = help_text[0]
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
            return "Error: " + str(e)


# Minimal concrete HelpCommand that plugs into the project's Command API
class HelpCommand(Command, BaseHelpText):
    def __init__(self):
        BaseHelpText.__init__(self)
        self._name = 'help'

    @property
    def name(self) -> str:
        return self._name

    @property
    def aliases(self) -> List[str]:
        # Return the backing _aliases list defined by BaseHelpText to avoid
        # infinite recursion from calling getattr(self, 'aliases', ...).
        return list(getattr(self, '_aliases', ['h', '?']))

    async def execute(self, *call_args, **call_kwargs):
        """
        Robustly accept either:
        - command_instance.execute(context_dict, args_list)
        - command_instance.execute(reader, writer, context_dict, args_list)
        - command_instance.execute(context=context_dict, args=args_list)

        Normalize to (context, args) and delegate to BaseHelpText.execute.
        """
        ctx = None
        a = None

        # Positional handling
        if len(call_args) == 0:
            ctx = call_kwargs.get('context') or call_kwargs.get('command_processor') or call_kwargs.get('command_manager')
            a = call_kwargs.get('args')
        elif len(call_args) == 1:
            # called as (context,)
            if isinstance(call_args[0], dict):
                ctx = call_args[0]
                a = call_kwargs.get('args')
            else:
                # unknown single arg; fall back to kwargs
                ctx = call_kwargs.get('context')
                a = call_kwargs.get('args')
        else:
            # If first positional is a dict assume (context, args)
            if isinstance(call_args[0], dict):
                ctx = call_args[0]
                a = call_args[1] if len(call_args) > 1 else call_kwargs.get('args')
            else:
                # legacy: reader, writer, context, args -> find dict and list in call_args
                for item in call_args:
                    if isinstance(item, dict) and ctx is None:
                        ctx = item
                    if isinstance(item, (list, tuple)) and a is None:
                        a = list(item)

        # Final fallback to kwargs
        ctx = ctx or call_kwargs.get('context') or call_kwargs.get('command_processor') or call_kwargs.get('command_manager') or {}
        a = a or call_kwargs.get('args') or []

        # Ensure types
        if not isinstance(ctx, dict):
            ctx = dict(ctx) if ctx is not None else {}
        if not isinstance(a, (list, tuple)):
            a = [a] if a is not None else []

        result = await BaseHelpText.execute(self, ctx, list(a))
        if isinstance(result, dict):
            return result
        if isinstance(result, CommandResult):
            return result.to_dict()
        try:
            return {'success': True, 'message': str(result)}
        except Exception:
            return {'success': True, 'message': ''}

    @staticmethod
    def register():
        return HelpCommand()


def headline(text, width=60, char='='):
    return f"\n{text.center(width, char)}"

if __name__ == '__main__':
    hc = HelpCommand()
    print(hc.help_text(is_recursive=True))
