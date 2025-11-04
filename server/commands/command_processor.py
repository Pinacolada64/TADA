"""
Command processor for handling and dispatching commands.

This module defines the `CommandProcessor` class, which is responsible for
registering, managing, and executing commands. It provides functionality to
process raw input, dispatch commands to their respective handlers, and handle
errors gracefully. Commands are automatically discovered using the `@command` decorator.
"""

import importlib
import logging
from typing import Type, List, Dict, Any, Generic, Optional, TypeVar, Callable
from commands.context import Context

# Required imports from the base file
from commands.base_command import BaseCommand, CommandResult, HelpCategory

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

        # Iterate over the command classes stored by the decorator
        for name, CommandClass in _DECORATED_COMMANDS.items():
            # Create an instance and register it
            try:
                # We register the instance, not the class
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

        # Register the main command name
        cmd_name_lower = command_instance.name.lower()
        self._commands[cmd_name_lower] = command_instance
        logging.info("Registered command: %s", command_instance.name)

        # Register all aliases
        for alias in getattr(command_instance, 'aliases', []):
            alias_lower = alias.lower()
            if alias_lower in self._commands:
                existing_cmd = self._commands[alias_lower]
                logging.warning("Alias '%s' for command '%s' is already registered to '%s'",
                             alias, command_instance.name, existing_cmd.name)
                continue
            # Store the same command instance under the alias
            self._commands[alias_lower] = command_instance
            self._aliases[alias_lower] = cmd_name_lower
            logging.debug("Registered alias '%s' for command '%s'", alias, command_instance.name)

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

        # Find the command instance
        command_instance, is_alias = self.find_command(command_name)
        if not command_instance:
            return CommandResult(
                success=False,
                error='unknown_command',
                message=f"Unknown command: {command_name}"
            )

        logging.debug("Executing %scommand: %s (aliases: %s)",
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
        """
        Process raw input text as a command.

        :param input_text: Raw input text from the user

        :return: CommandResult: The result of the command execution
        """
        input_text = input_text.strip()
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
        'client': processor_context.get(Context.CLIENT),
        'username': processor_context.get(Context.USERNAME),
        'is_authenticated': processor_context.get(Context.IS_AUTHENTICATED),
        'user_level': processor_context.get(Context.USER_LEVEL),
    })

    # Create the command processor with the client and context
    processor = CommandProcessor(client=client, context=processor_context)

    # 1. Automatically register all decorated commands
    processor._autodiscover_commands()

    # 2. Ensure core login-related commands are available even if not decorated.
    #    Import them safely and register if their classes exist. This guarantees
    #    that 'login'/'connect', 'new', and 'guest' commands are present for
    #    clients during the login flow.
    core_cmds = [
        ("commands.connect", "ConnectCommand"),
        ("commands.new_player", "NewPlayerCommand"),
        ("commands.guest", "GuestCommand"),
        ("commands.guest_commands", "HelpCommand"),
    ]
    for mod_name, cls_name in core_cmds:
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name, None)
            if cls:
                try:
                    instance = cls()
                    processor.register_command(instance)
                except Exception as e:
                    logging.debug(f"Could not instantiate/register {cls_name} from {mod_name}: {e}")
        except Exception:
            logging.debug(f"Core command module {mod_name} not available; skipping.")

    # 3. Add any other commands that aren't decorated here if needed

    return processor
