"""commands/config.py — Admin-only server configuration viewer/editor.

Wraps config.py's ServerConfig (server_config.json) -- see that module for
the full rationale behind each setting (SETTINGS_METADATA), including
which come from SPUR.CONTROL.S (game_name, session_time_limit_minutes,
victory_type, victory_gold_amount, victory_item_number) versus
TADA-specific additions (require_invites, invite_expiry_days, max_players,
port, host, dwarf_silver).

Two ways in, same underlying settings table:
  - `config` with no arguments opens a live menu (menu_system.py, same
    Menu/MenuItem/dot-leader pattern commands/editplayer.py already uses)
    -- pick a setting, see its current value, type a new one.
  - `config <key> <value>` is a one-line shortcut for a quick edit without
    navigating the menu.

setup/server_setup.py's offline sysop tool reads the exact same
config.SETTINGS_METADATA, so both places always list/validate the same
settings -- nothing is duplicated between the live in-game command and
the standalone setup script.
"""
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from config import SETTINGS_METADATA, config as server_config, format_value, parse_value, resolve_key
from flags import PlayerFlags
from menu_system import Menu, MenuItem, run_menu
from network_context import GameContext


async def _prompt_new_value(ctx, key: str, desc: str) -> None:
    """Prompt for a new value for *key*, validate/apply it, and report
    back. Shared by every menu item's action callback."""
    current = format_value(server_config.get(key))
    raw = await ctx.prompt(
        f'New value for {key}',
        preamble_lines=['', desc, f'Current: {current}  —  blank to cancel'],
    )
    if raw is None or not raw.strip():
        return
    try:
        value = parse_value(key, raw.strip())
        server_config.set_validated(key, value)
    except ValueError as exc:
        await ctx.send(str(exc))
        return
    await ctx.send(f'{key} set to {format_value(server_config.get(key))}.')


def _build_config_menu() -> Menu:
    menu = Menu(title='Server Configuration')
    for key, (_type, desc) in SETTINGS_METADATA.items():

        def make_action(k=key, d=desc):
            async def action(ctx):
                await _prompt_new_value(ctx, k, d)
            return action

        menu.add_item(MenuItem(
            key,
            dot_leader_handler=lambda ctx, k=key: format_value(server_config.get(k)),
            action=make_action(),
        ))
    return menu


class ConfigCommand(Command):
    name    = 'config'
    aliases = ['cfg']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'View or change server-wide configuration. Admin only.',
        category = HelpCategory.ADMINISTRATIVE,
        usage    = [
            ('config',              'Open a menu of every setting and its current value.'),
            ('config <key>',        "Show one setting's value and description. <key> can be "
                                      "an abbreviation, as long as it's unambiguous."),
            ('config <key> <value>', 'Change a setting directly, without the menu.'),
        ],
        examples = [
            ('config',                    'Open the settings menu.'),
            ('config victory_type',       'Show just the victory_type setting.'),
            ('config victory_t both',     "Same as above but abbreviated -- 'victory_t' only "
                                            "matches victory_type, so it expands automatically."),
            ('config session 45',        "'session' uniquely matches session_time_limit_minutes."),
            ('config require_invites off', 'Stop requiring invites for new players.'),
        ],
        description = (
            'Reads and writes server_config.json (config.py\'s ServerConfig). '
            'Several settings come from SPUR.CONTROL.S\'s SysOp config screen '
            '-- game_name, session_time_limit_minutes, and the victory_* '
            'trio (what it takes to "win" by escaping via the ladder up). '
            'Others (require_invites, invite_expiry_days, max_players, '
            'ansi_port, petscii_port, host, dwarf_silver) are TADA-specific '
            'additions. The same settings are also editable offline via '
            'setup/server_setup.py.'
        ),
        notes = [
            'Admin only.',
            "<key> can be a unique prefix of the full setting name (e.g. "
            "'victory_g' for victory_gold_amount) -- an ambiguous prefix "
            "(matching more than one setting) lists the candidates instead "
            "of guessing.",
            'port/host changes only take effect on the next server restart.',
            'session_time_limit_minutes is stored but not yet enforced -- '
            'nothing currently disconnects a player at the limit.',
            'victory_type/victory_gold_amount/victory_item_number are '
            'stored but not yet acted on -- no win/escape detection exists '
            'in this port yet.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        if not ctx.player.query_flag(PlayerFlags.ADMIN):
            await ctx.send('You lack the authority to do that.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        positional, _switches = self.parse_args(*args)

        if not positional:
            await run_menu(ctx, _build_config_menu())
            return CommandResult.ok('Config menu closed.')

        typed = positional[0]
        key, candidates = resolve_key(typed)
        if key is None:
            if candidates:
                await ctx.send(
                    f"'{typed}' matches more than one setting: {', '.join(candidates)}. "
                    "Type more of the name to narrow it down."
                )
                return CommandResult.fail('Ambiguous setting.', error='ambiguous_key')
            await ctx.send(f"Unknown setting '{typed}'. Use CONFIG with no arguments to list them all.")
            return CommandResult.fail('Unknown setting.', error='unknown_key')

        if len(positional) == 1:
            return await self._show_one(ctx, key)

        raw_value = ' '.join(positional[1:])
        return await self._set_one(ctx, key, raw_value)

    async def _show_one(self, ctx: GameContext, key: str) -> CommandResult:
        _type, desc = SETTINGS_METADATA[key]
        value = format_value(server_config.get(key))
        await ctx.send('', f'|yellow|{key}|reset| = {value}', desc, '')
        return CommandResult.ok(f'Showed {key}.')

    async def _set_one(self, ctx: GameContext, key: str, raw_value: str) -> CommandResult:
        try:
            value = parse_value(key, raw_value)
            server_config.set_validated(key, value)
        except ValueError as exc:
            await ctx.send(str(exc))
            return CommandResult.fail(str(exc), error='invalid_value')

        new_value = format_value(server_config.get(key))
        await ctx.send(f'{key} set to {new_value}.')
        return CommandResult.ok(f'{key} set to {new_value}.')
