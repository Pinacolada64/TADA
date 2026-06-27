#!/usr/bin/env python3
"""command_processor.py

Registers, looks up, and dispatches Command objects.

Auto-discovery
--------------
Call `create_command_processor()` (or `CommandProcessor.discover()`) to
scan the `commands/` package for every Command subclass that has a non-empty
`name` attribute and wire them all in automatically.

Manual registration
-------------------
    processor = CommandProcessor()
    processor.register_command(SayCommand())

Dispatching
-----------
    result = await processor.process_input("say hello world")
    result = await processor.process_command(["say", "hello", "world"])

Mode gating
-----------
Set `processor.current_mode` to the player's current Mode.  Commands whose
`modes` set does not include that mode (or Mode.ANY) will be rejected with
error="wrong_mode" before execute() is called.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Dict, List, Optional, Tuple

from commands.base_command import Command, CommandResult, Mode

log = logging.getLogger(__name__)


class CommandProcessor:
    """Holds a registry of Command instances and dispatches input to them.

    Attributes
    ----------
    current_mode : Mode
        The mode the player is currently in.  Checked against each
        Command.modes set before dispatch.
    context : dict
        Arbitrary context dict passed through to execute() — useful for
        tests; real code uses GameContext / TerminalContext instead.
    """

    def __init__(self, client=None, current_mode: Mode = Mode.GAME):
        self.client       = client
        self.current_mode = current_mode
        self.context: dict = {}

        # Primary registry: canonical name → Command instance.
        # Aliases are stored separately so we can distinguish them.
        self._commands: Dict[str, Command] = {}   # name  → Command
        self._aliases:  Dict[str, str]     = {}   # alias → canonical name

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_command(self, cmd: Command) -> None:
        """Register a command and all its aliases.

        Duplicate aliases are skipped with a WARNING; duplicate primary
        names raise ValueError.
        """
        name = cmd.name.lower()
        if not name:
            raise ValueError(f"Command {cmd!r} has no name.")

        if name in self._commands:
            raise ValueError(
                f"A command named {name!r} is already registered "
                f"({self._commands[name]!r})."
            )
        self._commands[name] = cmd

        modes = getattr(cmd, "modes", None)
        if modes is not None and not isinstance(modes, set):
            log.warning(
                "Command %r has modes=%r — should be a set like {Mode.GAME}. "
                "Wrapping automatically.",
                cmd.name, modes,
            )
            cmd.modes = {modes}

        for alias in (cmd.aliases or []):
            alias = alias.lower()
            if alias in self._commands or alias in self._aliases:
                log.warning(
                    "Alias %r for command %r already registered — skipping.",
                    alias, name,
                )
                continue
            self._aliases[alias] = name

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def find_command(self, token: str) -> Tuple[Optional[Command], bool]:
        """Return *(command, is_alias)* for *token*, or *(None, False)*.

        Lookup is case-insensitive.  *is_alias* is True when the token
        matched via an alias rather than the canonical name.
        """
        key = token.lower()
        if key in self._commands:
            return self._commands[key], False
        canonical = self._aliases.get(key)
        if canonical:
            return self._commands[canonical], True
        return None, False

    def get_all_commands(self) -> Dict[str, Command]:
        """Return a dict of canonical-name → Command for every registered command."""
        return dict(self._commands)

    def get_commands_by_category(self, category=None) -> Dict:
        """Return commands grouped by HelpCategory.

        Parameters
        ----------
        category : HelpCategory | None
            When given, only that category's group is returned.

        Returns
        -------
        dict[HelpCategory, list[Command]]
        """
        # Import here to avoid a circular import (help.py imports from here)
        try:
            from help import HelpCategory
        except ImportError:
            HelpCategory = None  # type: ignore

        groups: Dict = {}
        for cmd in self._commands.values():
            help_obj = getattr(cmd, "help", None)
            cat = getattr(help_obj, "category", None)
            if HelpCategory is not None and cat is None:
                cat = HelpCategory.GENERAL
            groups.setdefault(cat, []).append(cmd)

        if category is not None:
            return {category: groups.get(category, [])}
        return groups

    def search_commands(self, term: str) -> List[Command]:
        """Return commands whose name, aliases, or help text contains *term*.

        Search is case-insensitive and returns deduplicated Command instances.
        """
        term  = term.lower()
        seen:   set      = set()
        result: List[Command] = []

        for cmd in self._commands.values():
            if id(cmd) in seen:
                continue

            # Name match
            if term in cmd.name.lower():
                seen.add(id(cmd))
                result.append(cmd)
                continue

            # Alias match
            if any(term in alias.lower() for alias in (cmd.aliases or [])):
                seen.add(id(cmd))
                result.append(cmd)
                continue

            # Help text match (summary / description)
            help_obj = getattr(cmd, "help", None)
            summary  = getattr(help_obj, "summary",     "") or ""
            desc     = getattr(help_obj, "description", "") or ""
            if term in summary.lower() or term in desc.lower():
                seen.add(id(cmd))
                result.append(cmd)

        return result

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def process_input(self, raw: str, ctx=None) -> CommandResult:
        """Parse *raw* input and dispatch to the matching command.

        Parameters
        ----------
        raw : str
            The raw input string from the player.
        ctx : GameContext | TerminalContext | None
            The live connection context.  When provided it is passed directly
            to execute(); when omitted self.context (a plain dict) is used
            as a fallback so existing tests continue to work.
        """
        parts = raw.strip().split()
        return await self.process_command(parts, ctx=ctx)

    async def process_command(self, parts: List[str], ctx=None) -> CommandResult:
        """Dispatch a pre-split token list.

        Parameters
        ----------
        parts : list[str]
            parts[0] is the command name/alias; parts[1:] are arguments.
        ctx : GameContext | TerminalContext | None
            The live connection context.  Falls back to self.context when None.
        """
        if not parts:
            return CommandResult.fail("No command given.", error="no_command")

        # Split '#37' into ['#', '37'] so TeleportCommand receives the room
        # number as its first argument regardless of whether the player typed
        # '#37' (no space) or '# 37' (with space).
        if len(parts[0]) > 1 and parts[0].startswith('#'):
            parts = ['#', parts[0][1:]] + parts[1:]

        # Split '"Hello' into ['"', 'Hello'] so SayCommand receives the
        # message text when the player uses the bare " shortcut without a space.
        if len(parts[0]) > 1 and parts[0].startswith('"'):
            parts = ['"', parts[0][1:]] + parts[1:]

        cmd, _ = self.find_command(parts[0])
        args   = parts[1:]
        if cmd is None:
            return CommandResult.fail(
                f"Unknown command '{parts[0]}'.",
                error="unknown_command",
            )

        # Mode gate
        if not cmd.is_available_in(self.current_mode):
            return CommandResult.fail(
                f"Command '{cmd.name}' is not available right now.",
                error="wrong_mode",
            )

        username    = getattr(getattr(ctx, 'player', None), 'name', None) if ctx else None
        translation = getattr(getattr(getattr(ctx, 'player', None), 'client_settings', None), 'translation', None)
        log.debug("dispatch: %r -> %s.%s (mode=%s, args=%r, user=%r, translation=%s)",
                  parts[0], cmd.__class__.__module__, cmd.__class__.__name__,
                  self.current_mode.name, args, username, translation)

        # Use the live ctx when available; fall back to the stored dict for tests.
        effective_ctx = ctx if ctx is not None else self.context

        # Record the token the player actually typed so commands like MoveCommand
        # can distinguish which direction alias was used when args are empty.
        if hasattr(effective_ctx, '__dict__'):
            effective_ctx._invoked_as = parts[0].lower()

        try:
            result = await cmd.execute(effective_ctx, *args)
            # Tolerate commands that forget to return a CommandResult
            if result is None:
                result = CommandResult.ok()
            return result
        except Exception as exc:
            log.exception("Error executing command %r", cmd.name)
            return CommandResult.fail(
                f"Command error: {exc}",
                error="command_error",
            )

    # ------------------------------------------------------------------
    # Auto-discovery
    # ------------------------------------------------------------------

    def discover(self, package_name: str = "commands") -> None:
        """Scan *package_name* for Command subclasses and register them.

        Walks every module in the package (recursively), finds all concrete
        Command subclasses, and registers them.  Every failure mode is caught
        and logged individually so one bad module never prevents the rest from
        loading.

        Common failure modes handled:
          - package not importable (missing directory or syntax error in __init__)
          - missing __init__.py  (namespace package — no __path__)
          - individual module import error (bad import, syntax error, etc.)
          - getattr() raising on a module attribute (rare but possible)
          - command class that raises in __init__
          - duplicate name / alias (logged at WARNING, skipped)
        """
        # --- import the package itself ---
        try:
            package = importlib.import_module(package_name)
        except ImportError as exc:
            log.error(
                "Could not import command package %r: %s. "
                "Check that the directory exists and is on sys.path.",
                package_name, exc,
            )
            return
        except Exception:
            log.exception("Unexpected error importing command package %r", package_name)
            return

        # --- guard against namespace packages (missing __init__.py) ---
        if not hasattr(package, "__path__"):
            log.error(
                "Command package %r has no __path__. "
                "It is probably a namespace package because %s/__init__.py "
                "is missing. Create an empty __init__.py and restart.",
                package_name, package_name,
            )
            return

        registered:  list[str] = []
        skipped_mod: list[str] = []
        skipped_cls: list[str] = []

        prefix = package.__name__ + "."
        for _finder, module_name, _is_pkg in pkgutil.walk_packages(
            package.__path__, prefix=prefix
        ):
            # --- skip the processor module itself to avoid self-registration ---
            if module_name == __name__:
                continue

            # --- import the module ---
            try:
                module = importlib.import_module(module_name)
            except Exception:
                log.exception("Failed to import command module %r — skipping", module_name)
                skipped_mod.append(module_name)
                continue

            # --- walk every name in the module ---
            for attr_name in dir(module):
                # getattr can raise on dynamic descriptors
                try:
                    obj = getattr(module, attr_name)
                except Exception:
                    log.debug("getattr(%r, %r) raised — skipping", module_name, attr_name)
                    continue

                # filter: must be a concrete Command subclass with a name,
                # defined in *this* module (not just imported into it)
                if not (
                    isinstance(obj, type)
                    and issubclass(obj, Command)
                    and obj is not Command
                    and not getattr(obj, "__abstractmethods__", None)
                    and getattr(obj, "name", "")
                ):
                    continue

                # skip classes that were merely imported into this module
                if getattr(obj, "__module__", None) != module_name:
                    continue

                # --- instantiate and register ---
                try:
                    instance = obj()
                except Exception:
                    log.exception(
                        "Failed to instantiate command class %r from %r — skipping",
                        attr_name, module_name,
                    )
                    skipped_cls.append(f"{module_name}.{attr_name}")
                    continue

                try:
                    self.register_command(instance)
                    registered.append(instance.name)
                except ValueError:
                    # duplicate name/alias — already registered from another module
                    log.debug("Command %r already registered — skipping duplicate in %r",
                              instance.name, module_name)
                except Exception:
                    log.exception("Failed to register %r from %r", attr_name, module_name)
                    skipped_cls.append(f"{module_name}.{attr_name}")

        # --- summary log so startup is easy to diagnose ---
        log.info(
            "discover(%r): registered %d command(s): %s",
            package_name, len(registered), registered or "(none)",
        )
        if skipped_mod:
            log.warning("discover(%r): skipped %d module(s) due to import errors: %s",
                        package_name, len(skipped_mod), skipped_mod)
        if skipped_cls:
            log.warning("discover(%r): skipped %d class(es) due to errors: %s",
                        package_name, len(skipped_cls), skipped_cls)


# ---------------------------------------------------------------------------
# Factory used by simple_server.py
# ---------------------------------------------------------------------------

def create_command_processor(client=None, context: dict | None = None,
                              mode: Mode = Mode.GAME) -> CommandProcessor:
    """Create a CommandProcessor, run auto-discovery, and return it."""
    processor = CommandProcessor(client=client, current_mode=mode)
    if context:
        processor.context = context
    processor.discover()
    return processor