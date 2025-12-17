"""
Command processor for handling and dispatching commands.

This module defines the `CommandProcessor` class, which is responsible for
registering, managing, and executing commands. It provides functionality to
process raw input, dispatch commands to their respective handlers, and handle
errors gracefully. Commands are automatically discovered using the `@command` decorator.
"""

import asyncio
import importlib
import logging
from typing import Type, List, Dict, Any, Generic, Optional, TypeVar, Callable

# Required imports from the base file
from commands.base_command import BaseCommand, CommandResult, HelpCategory
from commands.context import Context

# Type variable for generics
T = TypeVar('T')

# ----------------------------------------------------
# DECORATOR AND AUTO-DISCOVERY MECHANISM (The Solution)
# ----------------------------------------------------

# Global storage for commands registered via the decorator
_DECORATED_COMMANDS: Dict[str, Type[BaseCommand]] = {}


def command(name: str,
            aliases: Optional[List[str]] = None,
            category: HelpCategory = HelpCategory.MISCELLANEOUS,
            summary: Optional[str] = None) -> Callable[[Type[BaseCommand]], Type[BaseCommand]]:
    """
    Decorator to automatically register a command class.

    It collects the command class and its metadata into a global dictionary
    for later retrieval by the CommandProcessor.

    :param name: The primary name of the command (e.g., "look").
    :param aliases: Optional list of aliases (e.g., ["l", "see"]).
    :param category: The help category for the command (see help.py: HelpCategory).
    :param summary: A brief summary for the command.
    """

    def decorator(cls: Type[BaseCommand]) -> Type[BaseCommand]:
        # 1. Attach metadata to the class object, overriding defaults in BaseCommand
        cls.name = name
        cls.aliases = aliases or []
        cls.category = category
        # Use existing class summary if present, otherwise the provided one
        cls.summary = summary or getattr(cls, 'summary', None)

        # 2. Store the class in the global dictionary
        _DECORATED_COMMANDS[name.lower()] = cls

        return cls

    return decorator


# ----------------------------------------------------
# COMMAND PROCESSOR CLASS
# ----------------------------------------------------

class CommandProcessor(Generic[T]):
    """Processes and dispatches commands to the appropriate handlers."""

    def __init__(self, client: Any, context: T = None):
        """Initialize the command processor with an optional context."""
        # Each CommandProcessor needs a concrete client instance here so
        # commands can access client methods like broadcast_to_all and tell_to_room
        self.client = client
        self.context: Dict[str, Any] = context or {}
        # Stores instantiated commands (for execution) mapped to their name/alias
        self._commands: Dict[str, BaseCommand] = {}
        self._aliases: Dict[str, str] = {}

    def _autodiscover_commands(self) -> None:
        """
        Pulls and instantiates all commands registered globally via the @command decorator.

        NOTE: This must be called *after* all decorated command files have been imported.
        """
        logging.info("Starting command auto-discovery...")

        # Try to import all modules in the `commands` package so their decorators run.
        # This approach is robust: it imports any module under commands/ so decorated
        # command classes register themselves in _DECORATED_COMMANDS.
        try:
            import pkgutil
            import commands as _commands_pkg
            for finder, name, ispkg in pkgutil.iter_modules(_commands_pkg.__path__):
                # Avoid importing test or private modules which may execute code at import-time
                if name.startswith('_') or name.startswith('test') or 'test' in name:
                    logging.debug(f"Skipping potentially unsafe module import: commands.{name}")
                    continue
                full_name = f"commands.{name}"
                try:
                    importlib.import_module(full_name)
                except Exception:
                    logging.debug(f"Failed to import {full_name}; skipping.")
        except Exception:
            logging.debug("Could not auto-import commands package modules; falling back to example_commands import.")
            try:
                importlib.import_module('commands.example_commands')
            except Exception:
                logging.debug("No example_commands module found or it failed to import; continuing.")

        # Iterate over the command classes stored by the decorator.
        # Avoid instantiating/registering multiple commands from the same class
        # (can happen if decorated entries were duplicated). Use a set of seen
        # classes to prevent duplicates.
        seen_classes = set()
        for name, CommandClass in _DECORATED_COMMANDS.items():
            if CommandClass in seen_classes:
                logging.debug(f"Skipping duplicate decorated command class for '{name}'")
                continue
            seen_classes.add(CommandClass)
            # Create an instance and register it
            try:
                command_instance = CommandClass()
                self.register_command(command_instance)
            except Exception as e:
                logging.error(f"Failed to instantiate and register command '{name}': {e}")

        logging.info(f"Finished auto-discovery. Total unique commands loaded: {len(self.get_all_commands())}")

    def register_command(self, command_instance: BaseCommand) -> None:
        """
        Register a command instance with the processor so it is available to use.

        :param command_instance: The command instance to register
        """
        if not getattr(command_instance, 'name', None):
            raise ValueError("Command instance must have a name set.")

        # Avoid registering another instance of the same command class.
        for existing in set(self._commands.values()):
            try:
                if existing.__class__ is command_instance.__class__:
                    logging.debug("Command class %s already registered; skipping duplicate instance.", command_instance.__class__.__name__)
                    return
            except Exception:
                continue

        # Register the main command name (do not overwrite an existing different command)
        cmd_name_lower = command_instance.name.lower()
        if cmd_name_lower in self._commands:
            existing = self._commands[cmd_name_lower]
            if existing.__class__ is command_instance.__class__:
                logging.debug("Command '%s' already registered (same class); skipping.", command_instance.name)
                return
            else:
                logging.warning("Command name '%s' already registered to %s; skipping registration of %s.", cmd_name_lower, getattr(existing,'name',None), command_instance.name)
                return

        self._commands[cmd_name_lower] = command_instance
        logging.info("Registered command: %s", command_instance.name)

        # Register all aliases; skip alias registration if it points to an existing command of the same class
        for alias in getattr(command_instance, 'aliases', []):
            try:
                alias_lower = alias.lower()
            except Exception:
                continue
            if alias_lower in self._commands:
                existing_cmd = self._commands[alias_lower]
                # If the alias maps to the same command class, it's harmless; skip silently
                try:
                    if existing_cmd.__class__ is command_instance.__class__:
                        logging.debug("Alias '%s' already registered for same command class %s; skipping.", alias_lower, command_instance.__class__.__name__)
                        continue
                except Exception:
                    pass
                logging.warning("Alias '%s' for command '%s' is already registered to '%s'; skipping alias.", alias, command_instance.name, existing_cmd.name)
                continue
            # Store the same command instance under the alias
            self._commands[alias_lower] = command_instance
            self._aliases[alias_lower] = cmd_name_lower
            logging.debug("Registered alias '%s' for command '%s'", alias, command_instance.name)

    def unregister_command(self, name: str) -> None:
        """Remove a command (by name or alias) and its aliases from the processor.

        This is safe to call even if the command isn't present.
        """
        if not name:
            return
        key = name.lower()
        # Find the primary instance for the name (may be alias)
        cmd_instance = self._commands.get(key)
        if not cmd_instance:
            return
        # Remove all entries in _commands that point to this instance
        keys_to_remove = [k for k, v in list(self._commands.items()) if v is cmd_instance]
        for k in keys_to_remove:
            try:
                del self._commands[k]
            except KeyError:
                pass
            # also remove alias mapping if present
            try:
                if k in self._aliases:
                    del self._aliases[k]
            except KeyError:
                pass
        logging.info("Unregistered command: %s", getattr(cmd_instance, 'name', name))

    def find_command(self, command_name: str) -> tuple[Optional[BaseCommand], bool]:
        """
        Find a command instance by name or alias.
        """
        if not command_name:
            return None, False

        command_name = command_name.lower()

        # Check the dictionary directly; it holds both names and aliases
        command_instance = self._commands.get(command_name)
        if command_instance:
            # Determine if it was accessed via an alias
            is_alias = command_name in self._aliases
            return command_instance, is_alias

        return None, False

    def get_commands_by_category(self, category: HelpCategory = None) -> dict[str, list[BaseCommand]]:
        """
        Get commands grouped by category.
        """
        categories: dict[HelpCategory, list[BaseCommand]] = {}

        # Use set(self._commands.values()) to get a list of unique command instances
        for cmd in set(self._commands.values()):
            cmd_category = getattr(cmd, 'category', HelpCategory.MISCELLANEOUS)
            if category and cmd_category != category:
                continue

            # use the enum itself as the dict key so callers can index by HelpCategory
            if cmd_category not in categories:
                categories[cmd_category] = []
            categories[cmd_category].append(cmd)

        return categories

    def search_commands(self, search_term: str) -> list[BaseCommand]:
        """
        Search for commands by name, alias, or summary.
        """
        if not search_term:
            return []

        search_term = search_term.lower()
        results = []

        for cmd in set(self._commands.values()):  # Use set to avoid duplicates from aliases
            # Check command name
            if search_term in cmd.name.lower():
                results.append(cmd)
                continue

            # Check aliases
            for alias in getattr(cmd, 'aliases', []):
                if search_term in alias.lower():
                    results.append(cmd)
                    break

            # Check summary if available
            summary = getattr(cmd, 'summary', '') or ''
            if summary and search_term in summary.lower():
                if cmd not in results:
                    results.append(cmd)

        return results

    async def process_command(self, command_parts: list[str]) -> CommandResult:
        """
        Process a command (and its arguments).
        """
        if not command_parts:
            return CommandResult(
                success=False,
                error='no_command',
                message="No command specified"
            )

        command_name = command_parts[0].lower()
        args = command_parts[1:] if len(command_parts) > 1 else []

        # Support shorthand admin teleport syntax: '#N' or '#NN' -> treat as command '#' with argument N
        if not self.find_command(command_name)[0]:
            # If token starts with '#' followed by digits, map to '#' command
            if command_name.startswith('#') and command_name[1:].isdigit():
                # Insert the '#' command as the command name and the number as an argument
                args = [command_name[1:]] + args
                command_name = '#'

        # Find the command instance
        command_instance, is_alias = self.find_command(command_name)
        if not command_instance:
            return CommandResult(
                success=False,
                error='unknown_command',
                message=f"Unknown command: {command_name}"
            )

        logging.debug("Executing %s command: %s (aliases: %s)",
                      'alias ' if is_alias else '',
                      command_instance.name,
                      ', '.join(getattr(command_instance, 'aliases', [])))

        try:
            # Execute the command with the processor's context and the arguments
            result = await command_instance.execute(self.context, args)
            return result
        except Exception as e:
            logging.exception(f"Error executing command {command_name}")
            # Include the exception message for better diagnostics/testing
            return CommandResult(
                success=False,
                error='command_error',
                message=f"An error occurred while executing the command: {type(e).__name__}: {e}"
            )

    async def process_input(self, input_text: str) -> CommandResult:
        """Process raw input text as a command.

        :param input_text: Raw input text from the user

        :return: CommandResult: The result of the command execution
        """
        # Keep context up-to-date with current client state (player may be attached/detached later)
        try:
            # Update the context entries that may change during the client's lifecycle
            self.context[Context.PLAYER] = getattr(self.client, 'player', None)
            self.context['player'] = self.context.get(Context.PLAYER)
            # Keep username in sync
            self.context[Context.USERNAME] = getattr(self.client, 'username', self.context.get(Context.USERNAME))
            self.context[Context.USERNAME.value] = self.context[Context.USERNAME]
        except Exception:
            pass

        input_text = (input_text or '').strip()
        if not input_text:
            return CommandResult(
                success=False,
                error='empty_input',
                message='Please enter a command.'
            )

        # Parse the command and arguments
        parts = input_text.split()

        # Update context with the raw input for command use; set both enum and string keys
        self.context[Context.RAW_INPUT] = input_text
        self.context['raw_input'] = input_text

        return await self.process_command(parts)

    def get_all_commands(self) -> List[BaseCommand]:
        """Return a list of all registered command instances."""
        return list(set(self._commands.values()))


def create_command_processor(client: Any, context: Optional[Dict[str, Any]] = None) -> CommandProcessor:
    """Create and initialize a command processor with a client and optional context."""
    # Create a new context with the client and any additional context
    processor_context = {
        Context.CLIENT: client,
        Context.USERNAME: 'Guest',
        Context.IS_AUTHENTICATED: False,
        Context.USER_LEVEL: 'guest',
        **(context or {})
    }
    # Keep string keys for backward compatibility
    processor_context.update({
        Context.CLIENT.value: processor_context.get(Context.CLIENT),
        Context.USERNAME.value: processor_context.get(Context.USERNAME),
        Context.IS_AUTHENTICATED.value: processor_context.get(Context.IS_AUTHENTICATED),
        Context.USER_LEVEL.value: processor_context.get(Context.USER_LEVEL),
        # If the client has a reference to its server, include it for commands that need it
        'server': getattr(client, 'server', None)
    })
    # Also include the Player object (if present) in the context for convenient access
    try:
        player_obj = getattr(client, 'player', None) or getattr(client, 'handler', None) and getattr(getattr(client, 'handler', None), 'player', None)
    except Exception:
        player_obj = None
    processor_context[Context.PLAYER] = player_obj
    # Backward-compatible string key
    processor_context['player'] = player_obj

    # Create the command processor with the client and context
    processor = CommandProcessor(client=client, context=processor_context)
    # Expose the processor itself in the context for helpers (e.g., HelpCommand)
    # This allows help implementations to lookup and list commands via the context
    # under keys commonly expected ('command_processor', 'command_manager').
    try:
        processor.context['command_processor'] = processor
        processor.context['command_manager'] = processor
    except Exception:
        pass

    # 1. Automatically register all decorated commands
    processor._autodiscover_commands()

    # Ensure a minimal 'help' command is always present. Some environments
    # may not register a dedicated HelpCommand class, so provide a small
    # fallback that lists available commands from this processor.
    try:
        logging.info("Attempting to register inline help command")

        class _InlineHelp(BaseCommand):
            name = 'help'
            aliases = ['h', '?']

            async def execute(self, context, args=None):
                # Normalize token
                if args:
                    cmd_name = args[0] if isinstance(args, (list, tuple)) else args
                    cmd_name = str(cmd_name).strip().lower()
                else:
                    cmd_name = None

                # If no token, show general help
                if not cmd_name:
                    lines = ['Available commands:']
                    grouped = processor.get_commands_by_category()
                    for cat, cmds in grouped.items():
                        lines.append(f"\n{getattr(cat, 'name', str(cat))}:")
                        for c in sorted(cmds, key=lambda x: x.name):
                            summary = getattr(c, 'summary', '') or ''
                            lines.append(f"  {c.name:<12} - {summary}")
                    return CommandResult(success=True, message=lines)

                # Try to find a registered command instance first
                cmd_inst, _is_alias = processor.find_command(cmd_name)
                if cmd_inst:
                    logging.debug("InlineHelp: found registered command instance for '%s' -> %r", cmd_name, getattr(cmd_inst, 'name', None))

                    # 1) help_text() method or attribute
                    try:
                        ht_attr = getattr(cmd_inst, 'help_text', None)
                        if callable(ht_attr):
                            logging.debug("InlineHelp: calling help_text() on %s", getattr(cmd_inst, 'name', None))
                            ht = ht_attr()
                            if asyncio.iscoroutine(ht):
                                ht = await ht
                            logging.debug("InlineHelp: help_text returned: %r", ht)
                            return CommandResult(success=True, message=ht)
                        elif ht_attr is not None:
                            # non-callable help_text (string/list)
                            logging.debug("InlineHelp: using non-callable help_text attribute on %s", getattr(cmd_inst,'name',None))
                            return CommandResult(success=True, message=ht_attr)
                    except Exception:
                        logging.exception("InlineHelp: exception when retrieving help_text for %s", getattr(cmd_inst, 'name', None))

                    # 2) structured help_info
                    hi = getattr(cmd_inst, 'help_info', None)
                    logging.debug("InlineHelp: help_info for %s = %r", getattr(cmd_inst, 'name', None), hi)
                    if hi:
                        parts = []
                        if getattr(hi, 'summary', None):
                            parts.append(str(hi.summary))
                        if getattr(hi, 'description', None):
                            parts.append(str(hi.description))
                        if getattr(hi, 'usage', None):
                            parts.append('\nUsage:')
                            for u in hi.usage:
                                parts.append(str(u))
                        logging.debug("InlineHelp: help_info produced parts: %r", parts)
                        return CommandResult(success=True, message='\n'.join(parts))

                    # 3) docstring of execute
                    doc = getattr(getattr(cmd_inst, 'execute', None), '__doc__', None)
                    logging.debug("InlineHelp: execute doc for %s = %r", getattr(cmd_inst, 'name', None), doc)
                    if doc:
                        return CommandResult(success=True, message=doc.strip())

                    # 4) module-level Help providers in the command's module
                    try:
                        modname = getattr(cmd_inst.__class__, '__module__', None)
                        if modname:
                            logging.debug("InlineHelp: looking for Help providers in module %s", modname)
                            mod = importlib.import_module(modname)
                            for attr_name in dir(mod):
                                if not attr_name.lower().endswith('help'):
                                    continue
                                attr = getattr(mod, attr_name)
                                if not isinstance(attr, type):
                                    continue
                                try:
                                    helper = attr()
                                except Exception:
                                    logging.exception("InlineHelp: could not instantiate helper %s", attr_name)
                                    continue
                                # prefer helper.help_text()
                                try:
                                    # Only call help_text if the class actually defines/overrides it; avoid BaseHelpText.help_text default
                                    if callable(getattr(helper, 'help_text', None)) and ('help_text' in getattr(helper.__class__, '__dict__', {})):
                                        logging.debug("InlineHelp: calling helper %s.help_text()", attr_name)
                                        ht = helper.help_text()
                                        if asyncio.iscoroutine(ht):
                                            ht = await ht
                                        logging.debug("InlineHelp: helper.help_text returned: %r", ht)
                                        return CommandResult(success=True, message=ht)
                                except Exception:
                                    logging.exception("InlineHelp: error calling help_text on helper %s", attr_name)
                                # fallback to structured fields
                                parts = []
                                if getattr(helper, 'summary', None):
                                    parts.append(str(helper.summary))
                                if getattr(helper, 'description', None):
                                    parts.append(str(helper.description))
                                if getattr(helper, 'usage', None):
                                    usage = helper.usage
                                    if isinstance(usage, str):
                                        parts.append(str(usage))
                                    else:
                                        parts.append('\nUsage:')
                                        for u in usage:
                                            parts.append(str(u))
                                if parts:
                                    logging.debug("InlineHelp: helper %s produced structured parts: %r", attr_name, parts)
                                    return CommandResult(success=True, message='\n'.join(parts))
                    except Exception:
                        logging.exception("InlineHelp: module-level help lookup failed for %s", getattr(cmd_inst, 'name', None))

                    # nothing found on the registered instance
                    return CommandResult(success=False, message=f'No detailed help available for {cmd_name}')

                # If we didn't find helpers in the command's module, also check commands.<cmd_name> explicitly
                # If no registered command instance, try importing commands.<cmd_name> module and looking for helpers
                try:
                    modname = f"commands.{cmd_name}"
                    logging.debug("InlineHelp: attempting to import module %s for help (fallback)", modname)
                    cmd_module = importlib.import_module(modname)
                    for attr_name in dir(cmd_module):
                        if not attr_name.lower().endswith('help'):
                            continue
                        attr = getattr(cmd_module, attr_name)
                        if not isinstance(attr, type):
                            continue
                        try:
                            help_inst = attr()
                        except Exception:
                            logging.exception("InlineHelp: failed to instantiate %s from %s", attr_name, modname)
                            continue
                        # Only call help_text if class defines it explicitly
                        try:
                            if callable(getattr(help_inst, 'help_text', None)) and ('help_text' in getattr(help_inst.__class__, '__dict__', {})):
                                ht = help_inst.help_text()
                                if asyncio.iscoroutine(ht):
                                    ht = await ht
                                return CommandResult(success=True, message=ht)
                        except Exception:
                            logging.exception("InlineHelp: error calling help_text on %s from %s", attr_name, modname)
                        parts = []
                        if getattr(help_inst, 'summary', None):
                            parts.append(str(help_inst.summary))
                        if getattr(help_inst, 'description', None):
                            parts.append(str(help_inst.description))
                        if getattr(help_inst, 'usage', None):
                            parts.append('\nUsage:')
                            for u in help_inst.usage:
                                parts.append(str(u))
                        if parts:
                            return CommandResult(success=True, message='\n'.join(parts))
                except Exception:
                    logging.exception("InlineHelp: failed to import or find helpers in %s", cmd_name)

                # final fallback: no help found, show general list
                lines = ['Available commands:']
                grouped = processor.get_commands_by_category()
                for cat, cmds in grouped.items():
                    lines.append(f"\n{getattr(cat, 'name', str(cat))}:")
                    for c in sorted(cmds, key=lambda x: x.name):
                        summary = getattr(c, 'summary', '') or ''
                        lines.append(f"  {c.name:<12} - {summary}")
                return CommandResult(success=True, message=lines)

        # Register the inline help (if not already present)
        existing_help_names = [c.name.lower() for c in processor.get_all_commands()]
        if 'help' in existing_help_names:
            logging.info("Unregistering existing 'help' command so inline help can take precedence")
            try:
                processor.unregister_command('help')
            except Exception:
                logging.exception("Failed to unregister existing help command")

        # Register inline help
        processor.register_command(_InlineHelp())
        logging.info("Inline help command registered on processor (overriding any previous help)")
    except Exception:
        logging.exception("Could not register inline help command; continuing.")

    # 2. Ensure core login-related commands are available even if not decorated.
    #    Import them safely and register if their classes exist. This guarantees
    #    that 'login'/'connect', 'new', and 'guest' commands are present for
    #    clients during the login flow.
    core_cmds = [
        ("commands.connect", "ConnectCommand"),
        ("commands.connect", "QuitCommand"),
        ("commands.editplayer", "EditPlayerCommand"),
        ("commands.new_player", "NewPlayerCommand"),
        ("commands.guest", "GuestCommand"),
        ("commands.guest_commands", "HelpCommand"),
        ("commands.help", "HelpCommand"),
        ("commands.teleport", "TeleportCommand"),
    ]
    for mod_name, cls_name in core_cmds:
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name, None)
            if cls:
                try:
                    # Skip if a command with this name is already present
                    existing, _ = processor.find_command(getattr(cls, 'name', cls_name).lower())
                    if existing:
                        logging.debug(f"Core command {cls_name} from {mod_name} skipped because '{getattr(cls,'name',cls_name)}' is already registered")
                        continue
                    instance = cls()
                    processor.register_command(instance)
                except Exception as e:
                    logging.debug(f"Could not instantiate/register {cls_name} from {mod_name}: {e}")
        except Exception:
            logging.debug(f"Core command module {mod_name} not available; skipping.")

    # 3. Prune commands based on per-command attributes
    # Commands may set `login_only = True` to indicate they should only be
    # available during the login flow (e.g. guest/new). Likewise, commands
    # may set `auth_only = True` to indicate they should only be available
    # to authenticated users. We remove the inappropriate commands here.
    try:
        is_auth = bool(processor_context.get(Context.IS_AUTHENTICATED) or processor_context.get('is_authenticated'))
        # take a snapshot of command instances (unique) to examine attributes
        for cmd in list(set(processor.get_all_commands())):
            try:
                if is_auth and getattr(cmd, 'login_only', False):
                    processor.unregister_command(cmd.name)
                elif (not is_auth) and getattr(cmd, 'auth_only', False):
                    processor.unregister_command(cmd.name)
            except Exception:
                logging.debug(f"Could not prune command {getattr(cmd, 'name', None)} based on auth state")
    except Exception:
        logging.exception("Error while pruning commands from processor based on attributes")

    # 3. Add any other commands that aren't decorated here if needed

    return processor
