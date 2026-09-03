"""commands/logs.py — Admin/DM tool: browse server-side log sources.

    logs                — numbered menu of available log sources, then
                           prompts which one to view
    logs #system         — jump straight to the system log (run/server/log,
                            the file operators redirect stdout to via
                            run_server.py -- see its module docstring)
    logs #statues         — jump straight to the hall of statues (every
                            monster's memorial file, via
                            combat.engine.load_all_statues())
    logs #battle          — jump straight to the battle log
                            (net_common.append_battle_log()'s battle.log)

Each source, once chosen, prompts a second time for *which day* to view --
[T]oday plus the last seven weekdays. Log rotation isn't implemented yet,
so every day but Today currently reports "not available yet"; the
sub-menu exists now so the command's shape doesn't have to change once
rotation lands (each source's file is expected to grow a per-day/per-
weekday variant at that point, e.g. log.mon, log.tue, ...).

Once a day resolves to real content, one or two more prompts narrow the
results down:
  - System log: optional player filter (matches the `%(player)-16s`
    column simple_server.py's logging.Formatter writes -- see
    _PlayerFilter in simple_server.py) and optional module filter
    (matches the `%(module)s.%(funcName)s` prefix), each an
    Enter-for-all substring match.
  - Battle log / hall of statues: optional player filter -- for the
    battle log a substring match anywhere in the line (its entries are
    free text, not columnar, per net_common.append_battle_log()); for
    statues, only monsters with a matching victim name are kept.

Admin/Dungeon Master only, same gating as commands/list_locations.py.
"""
from __future__ import annotations

from pathlib import Path

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext

# Ordered so the numbered menu and the `logs #<key>` switch agree.
_SOURCE_ORDER = ['system', 'statues', 'battle']

_SOURCE_LABELS = {
    'system':  'System logs',
    'statues': 'Statue memorials',
    'battle':  'Battle log',
}

_SOURCE_ALIASES = {
    'sys': 'system', 'system': 'system',
    'statue': 'statues', 'statues': 'statues',
    'battle': 'battle', 'battlelog': 'battle',
}

# [T]oday plus the last seven weekdays -- a stub for future log rotation.
# Only 'today' actually resolves to real content right now.
_DAY_ORDER = ['today', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

_DAY_LABELS = {
    'today': '[T]oday',
    'mon':   '[Mon]day',
    'tue':   '[Tue]sday',
    'wed':   '[Wed]nesday',
    'thu':   '[Thu]rsday',
    'fri':   '[Fri]day',
    'sat':   '[Sat]urday',
    'sun':   '[Sun]day',
}

_DAY_ALIASES = {'t': 'today', 'today': 'today'}
for _day in _DAY_ORDER[1:]:
    _DAY_ALIASES[_day] = _day
    # setdefault: 't' is reserved for 'today' above, and tue/thu (also
    # sat/sun) share a first letter -- first one in _DAY_ORDER wins, the
    # other stays reachable only by its full name.
    _DAY_ALIASES.setdefault(_day[0], _day)

_TAIL_LINES = 40


def _is_privileged(player) -> bool:
    return (player.query_flag(PlayerFlags.ADMIN)
            or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def _run_dir(ctx: GameContext) -> Path:
    import net_common
    return Path(getattr(net_common, 'run_server_dir', None) or 'run/server')


def _tail(path: Path, n: int = _TAIL_LINES) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(errors='replace').splitlines()
    except OSError:
        return []
    return lines[-n:]


def _parse_system_line(line: str) -> tuple[str, str] | None:
    """Split a simple_server.py-formatted log line into (player, module).

    Format is `%(asctime)s | %(levelname)-8s | %(player)-16s |
    %(module)s.%(funcName)s: %(message)s` (simple_server.py's
    logging.basicConfig() call). Lines that don't match -- e.g. a
    traceback's continuation lines, which have no columns at all -- return
    None so filtering can drop them instead of misreading a fragment.
    """
    parts = line.split(' | ', 3)
    if len(parts) < 4:
        return None
    _ts, _level, player_field, rest = parts
    module_field = rest.split(':', 1)[0]
    return player_field.strip(), module_field.strip()


def _filter_system_lines(lines: list[str], *, player: str | None,
                          module: str | None) -> list[str]:
    if not player and not module:
        return lines
    out = []
    for line in lines:
        parsed = _parse_system_line(line)
        if parsed is None:
            continue
        line_player, line_module = parsed
        if player and player.lower() not in line_player.lower():
            continue
        if module and module.lower() not in line_module.lower():
            continue
        out.append(line)
    return out


def _filter_battle_lines(lines: list[str], *, player: str | None) -> list[str]:
    if not player:
        return lines
    needle = player.lower()
    return [line for line in lines if needle in line.lower()]


def _filter_statues(statues: dict, *, player: str | None) -> dict:
    if not player:
        return statues
    needle = player.lower()
    return {
        monster: victims for monster, victims in statues.items()
        if any(needle in victim.lower() for victim in victims)
    }


class LogsCommand(Command):
    """Admin/DM tool: view system logs, the hall of statues, or the battle log."""

    name    = 'logs'
    aliases = ['log']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Browse server-side logs: system log, statue memorials, battle log (admin/DM only).',
        description = (
            'Bare `logs` shows a numbered menu of available log sources. '
            'Each source then asks which day to view -- only Today works '
            'until log rotation is implemented -- then offers an optional '
            'player filter (and, for the system log, an optional module '
            'filter) before showing results.'
        ),
        category = HelpCategory.ADMINISTRATIVE,
        usage    = [
            ('logs',          'Show the log-source menu.'),
            ('logs #system',  'Jump straight to the system log.'),
            ('logs #statues', 'Jump straight to the hall of statues.'),
            ('logs #battle',  'Jump straight to the battle log.'),
        ],
        notes = ['Admin or Dungeon Master only.'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        if not _is_privileged(player):
            await ctx.send("You don't have permission to use that command.")
            return CommandResult.fail(error='permission_denied')

        _, switches = self.parse_args(*args)
        switches = [s.lstrip('#') for s in switches]

        source = None
        for token in switches:
            if token in _SOURCE_ALIASES:
                source = _SOURCE_ALIASES[token]
                break

        if source is None:
            source = await self._choose_source(ctx)
            if source is None:
                return CommandResult.ok()

        day = await self._choose_day(ctx)
        if day is None:
            return CommandResult.ok()

        if day != 'today':
            await ctx.send(
                f'{_DAY_LABELS[day]} isn\'t available yet -- log rotation '
                "isn't implemented, so only Today is on record."
            )
            return CommandResult.ok()

        player_filter, module_filter = await self._choose_filters(ctx, source)

        await self._show(ctx, source, player_filter, module_filter)
        return CommandResult.ok()

    async def _choose_filters(self, ctx: GameContext, source: str) -> tuple[str | None, str | None]:
        player_filter = await self._prompt_optional(ctx, 'Filter by player (Enter for all)')
        module_filter = None
        if source == 'system':
            module_filter = await self._prompt_optional(ctx, 'Filter by module (Enter for all)')
        return player_filter, module_filter

    async def _prompt_optional(self, ctx: GameContext, message: str) -> str | None:
        raw = await ctx.prompt('Filter', preamble_lines=[message])
        return raw.strip() if raw and raw.strip() else None

    async def _choose_source(self, ctx: GameContext) -> str | None:
        lines = ['Available logs:']
        for i, key in enumerate(_SOURCE_ORDER, 1):
            lines.append(f'{i}. {_SOURCE_LABELS[key]}')
        await ctx.send(lines)

        raw = await ctx.prompt(
            'Log #',
            preamble_lines=[f'View which log? (1-{len(_SOURCE_ORDER)}, blank to cancel)'])
        if not raw or not raw.strip():
            return None
        choice = raw.strip().lower()
        if choice in _SOURCE_ALIASES:
            return _SOURCE_ALIASES[choice]
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(_SOURCE_ORDER):
                return _SOURCE_ORDER[idx]
        except ValueError:
            pass
        await ctx.send('Invalid selection.')
        return None

    async def _choose_day(self, ctx: GameContext) -> str | None:
        menu = ' / '.join(_DAY_LABELS[d] for d in _DAY_ORDER)
        preamble = [menu]
        raw = await ctx.prompt('Which day? (blank = Today)', preamble_lines=preamble)
        if not raw or not raw.strip():
            return 'today'
        choice = raw.strip().lower()
        if choice in _DAY_ALIASES:
            return _DAY_ALIASES[choice]
        await ctx.send('Invalid selection.')
        return None

    async def _show(self, ctx: GameContext, source: str, player_filter: str | None,
                     module_filter: str | None) -> None:
        if source == 'system':
            await self._show_system(ctx, player_filter, module_filter)
        elif source == 'statues':
            await self._show_statues(ctx, player_filter)
        elif source == 'battle':
            await self._show_battle(ctx, player_filter)

    @staticmethod
    def _filter_suffix(player_filter: str | None, module_filter: str | None = None) -> str:
        bits = []
        if player_filter:
            bits.append(f'player={player_filter}')
        if module_filter:
            bits.append(f'module={module_filter}')
        return f' ({", ".join(bits)})' if bits else ''

    async def _show_system(self, ctx: GameContext, player_filter: str | None,
                            module_filter: str | None) -> None:
        path = _run_dir(ctx) / 'log'
        tail = _tail(path)
        if not tail:
            await ctx.send('No system log found.')
            return
        filtered = _filter_system_lines(tail, player=player_filter, module=module_filter)
        if not filtered:
            await ctx.send(f'No system log entries match{self._filter_suffix(player_filter, module_filter)}.')
            return
        suffix = self._filter_suffix(player_filter, module_filter)
        await ctx.send([f'-- System log: last {len(filtered)} matching line(s) of {path}{suffix} --', *filtered])

    async def _show_battle(self, ctx: GameContext, player_filter: str | None) -> None:
        path = _run_dir(ctx) / 'battle.log'
        tail = _tail(path)
        if not tail:
            await ctx.send('No battle log found.')
            return
        filtered = _filter_battle_lines(tail, player=player_filter)
        if not filtered:
            await ctx.send(f'No battle log entries match{self._filter_suffix(player_filter)}.')
            return
        suffix = self._filter_suffix(player_filter)
        await ctx.send([f'-- Battle log: last {len(filtered)} matching line(s) of {path}{suffix} --', *filtered])

    async def _show_statues(self, ctx: GameContext, player_filter: str | None) -> None:
        statues = getattr(ctx.server, 'statues', None)
        if statues is None:
            from combat.engine import load_all_statues
            statues = load_all_statues()

        if not statues:
            await ctx.send('No statues have been carved yet.')
            return

        statues = _filter_statues(statues, player=player_filter)
        if not statues:
            await ctx.send(f'No statues match{self._filter_suffix(player_filter)}.')
            return

        from formatting import border_style_for_ctx
        from table import Table

        t = Table(headers=['Monster', 'Victims (oldest first)'],
                  title=f'Hall of Statues ({len(statues)}){self._filter_suffix(player_filter)}',
                  border_style=border_style_for_ctx(ctx))
        for monster in sorted(statues):
            t.add_row([monster, ', '.join(statues[monster])])

        width = getattr(ctx.player.client_settings, 'screen_columns', 78)
        await ctx.send(t.render(width=width))
