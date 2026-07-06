"""commands/reload.py — Admin: hot-reload command/support modules without
restarting the server.

CommandProcessor.discover() (commands/command_processor.py) re-imports
every command module via importlib.import_module() -- but Python caches
imported modules in sys.modules, so that call returns the *cached* module
object unmodified, even after the .py file on disk has changed. A fresh
connection creating a new CommandProcessor doesn't help either, for the
same reason. Only importlib.reload() actually re-executes a module's code
from disk.

This command forces that reload for the named module(s), then re-runs
discover() on every currently-connected client's *existing*
CommandProcessor so the change takes effect immediately -- no one needs
to reconnect, let alone the server restart.

Important: each client's CommandProcessor must be mutated in place
(clear() + discover()), not replaced with a new instance. The per
-connection game loop (simple_server.py's _game_loop()/login loop) reads
`ctx.client.command_processor` into a local variable once, at loop start
-- reassigning that attribute on an already-running session has no
effect, since the loop keeps using its own stale local reference. Only
mutating the object every session already holds a reference to is
actually visible to it.

Caveat: only the module(s) actually named are re-executed. If a command
module imports something else that also changed (e.g. base_classes.py),
that dependency keeps its old, cached definitions unless it's named too --
pass multiple module names in one call: `reload movement base_classes`.
"""
import importlib
import logging
import pkgutil
import sys
from pathlib import Path

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext

log = logging.getLogger(__name__)

_SERVER_DIR = Path(__file__).resolve().parent.parent
_VENV_DIR   = _SERVER_DIR / '.venv'


def _resolve_module_name(token: str) -> str:
    """'movement' -> 'commands.movement'; a dotted name, or an already
    -imported top-level module name, is used as-is."""
    if '.' in token or token in sys.modules:
        return token
    return f'commands.{token}'


def _list_command_modules() -> tuple[list[str], list[str]]:
    """Return (loaded, not_loaded) dotted names for every module under
    commands/, same walk discover() itself does."""
    import commands as commands_pkg
    available = sorted(
        name for _finder, name, _is_pkg
        in pkgutil.walk_packages(commands_pkg.__path__, prefix='commands.')
    )
    loaded     = [n for n in available if n in sys.modules]
    not_loaded = [n for n in available if n not in sys.modules]
    return loaded, not_loaded


def _list_other_loaded_modules() -> list[str]:
    """Other first-party project modules already loaded -- valid reload
    targets besides commands/*, e.g. base_classes, simple_server,
    combat.engine. Filtered to files under the server directory so stdlib
    and venv packages don't flood the list."""
    names = []
    for name, mod in sys.modules.items():
        if mod is None or name.startswith('commands.') or name == 'commands':
            continue
        path = getattr(mod, '__file__', None)
        if not path:
            continue
        try:
            resolved = Path(path).resolve()
            if resolved.is_relative_to(_SERVER_DIR) and not resolved.is_relative_to(_VENV_DIR):
                names.append(name)
        except (OSError, ValueError):
            continue
    return sorted(names)


class ReloadCommand(Command):
    name  = 'reload'
    modes = {Mode.GAME}

    help = Help(
        summary  = 'Hot-reload command/support modules without restarting the server.',
        category = HelpCategory.ADMINISTRATIVE,
        usage    = [
            ('reload <module> [module...]',  'Reload one or more modules by name.'),
            ('reload movement base_classes', 'Bare names expand to commands.<name>; '
                                              'dotted names are used as-is.'),
            ('reload #list',                 'List loaded/available modules.'),
        ],
        notes = [
            'Admin only.',
            'Only the named module(s) are re-executed -- if a command module',
            'imports something else that changed too (e.g. base_classes.py),',
            'name that module as well or the stale version stays in effect.',
            'Rebuilds every connected client\'s command table afterward, so',
            'no one needs to reconnect.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        if not ctx.player.query_flag(PlayerFlags.ADMIN):
            await ctx.send('You lack the authority to do that.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        positional, switches = self.parse_args(*args)

        if '#list' in switches:
            return await self._list(ctx)

        if not positional:
            await ctx.send('Usage: reload <module> [module...]  |  reload #list')
            return CommandResult.fail('No module given.', error='missing_args')

        reloaded, failed = [], []
        for token in positional:
            module_name = _resolve_module_name(token)
            try:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                else:
                    importlib.import_module(module_name)
                reloaded.append(module_name)
            except Exception as e:
                log.exception('reload: failed to reload %r', module_name)
                failed.append(f'{module_name} ({e})')

        # Mutate every connected client's *existing* CommandProcessor in
        # place (see module docstring for why reassigning the attribute
        # instead would silently not take effect for already-running
        # sessions) so the change takes effect immediately, without
        # anyone reconnecting.
        rebuilt = 0
        for client in getattr(ctx.server, 'clients', {}).values():
            processor = getattr(client, 'command_processor', None)
            if processor is None:
                continue
            try:
                processor.clear()
                processor.discover()
                rebuilt += 1
            except Exception:
                log.exception('reload: failed to rebuild command processor for a client')

        if reloaded:
            await ctx.send(f'Reloaded: {", ".join(reloaded)}')
        if failed:
            await ctx.send(f'Failed: {"; ".join(failed)}')
        await ctx.send(f'Rebuilt command tables for {rebuilt} connected client(s).')
        log.warning('ADMIN RELOAD: %s reloaded %s (failed: %s)',
                    ctx.player.name, reloaded, failed)

        if failed:
            return CommandResult.fail('Some modules failed to reload.', error='reload_failed')
        return CommandResult.ok()

    async def _list(self, ctx: GameContext) -> CommandResult:
        loaded, not_loaded = _list_command_modules()
        other = _list_other_loaded_modules()

        lines = ['', f'Command modules ({len(loaded)}/{len(loaded) + len(not_loaded)} loaded):']
        lines += [f'  {n}' for n in loaded] or ['  (none)']
        if not_loaded:
            lines += ['', 'Not yet loaded (no connection has imported them yet):']
            lines += [f'  {n}' for n in not_loaded]
        lines += ['', f'Other loaded project modules ({len(other)}):']
        lines += [f'  {n}' for n in other] or ['  (none)']
        await ctx.send(lines)
        return CommandResult.ok()
