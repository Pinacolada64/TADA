"""commands/config.py — Admin/Dungeon Master server configuration viewer/editor.

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
from item_system import (
    format_victory_item_choices, format_victory_item_value,
    is_victory_item_number_valid, victory_eligible_treasures,
)
from menu_system import Menu, MenuItem, run_menu
from network_context import GameContext

_VICTORY_ITEM_KEY = 'victory_item_number'


def _display_value(key: str, value) -> str:
    """format_value(), except victory_item_number also shows the
    treasure's name once victory_type is 'item'/'both' -- Ryan: '(35)
    Sand Dollar' instead of a bare 35, which means nothing on sight."""
    if key == _VICTORY_ITEM_KEY:
        return format_victory_item_value(value, server_config.victory_type)
    return format_value(value)


def _is_privileged(player) -> bool:
    """Admin OR Dungeon Master -- same definition commands/whereat.py's
    _is_privileged() uses. (ban.py/reload.py/teleport.py check ADMIN
    only, since those are direct server-control actions; CONFIG is
    read/write like those, but Ryan expects DM to work here too.)"""
    return (player.query_flag(PlayerFlags.ADMIN)
            or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def _validate_victory_item(value: int) -> None:
    """Raise ValueError (same convention as config.parse_value()) if
    *value* isn't 0 or a real, victory-eligible Treasure item number."""
    if not is_victory_item_number_valid(value):
        raise ValueError(
            f"{value} isn't a valid Treasure item number (or too generic a "
            "name -- SPUR.CONTROL.S's chk.obj rule). Type '?' to list eligible items."
        )


async def _prompt_new_value(ctx, key: str, label: str, desc: str) -> None:
    """Prompt for a new value for *key*, validate/apply it, and report
    back. Shared by every menu item's action callback.

    victory_item_number gets a special '?' listing of eligible Treasure
    items (item_system.victory_eligible_treasures()) -- picking a random
    item number by hand isn't practical with 100+ Treasure items in
    objects.json.
    """
    while True:
        current = _display_value(key, server_config.get(key))
        hint = " Type '?' to list eligible items." if key == _VICTORY_ITEM_KEY else ''
        raw = await ctx.prompt(
            f'New value for {label}',
            preamble_lines=['', desc, f'Current: {current}  —  blank to cancel{hint}'],
        )
        if raw is None or not raw.strip():
            return
        raw = raw.strip()

        if key == _VICTORY_ITEM_KEY and raw == '?':
            items = victory_eligible_treasures()
            await ctx.send(
                '', 'Treasure items eligible for Victory Item:', '',
                *format_victory_item_choices(items), '',
            )
            continue

        try:
            value = parse_value(key, raw)
            if key == _VICTORY_ITEM_KEY:
                _validate_victory_item(value)
            server_config.set_validated(key, value)
        except ValueError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f'{label} set to {_display_value(key, server_config.get(key))}.')
        return


def _build_config_menu() -> Menu:
    menu = Menu(title='Server Configuration')
    for key, info in SETTINGS_METADATA.items():

        def make_action(k=key, lbl=info.label, d=info.description):
            async def action(ctx):
                await _prompt_new_value(ctx, k, lbl, d)
            return action

        menu.add_item(MenuItem(
            info.label,
            dot_leader_handler=lambda ctx, k=key: _display_value(k, server_config.get(k)),
            action=make_action(),
        ))
    return menu


class ConfigCommand(Command):
    name    = 'config'
    aliases = ['cfg']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'View or change server-wide configuration. Admin/Dungeon Master only.',
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
            'Admin or Dungeon Master only.',
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
        if not _is_privileged(ctx.player):
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
        info = SETTINGS_METADATA[key]
        value = _display_value(key, server_config.get(key))
        await ctx.send('', f'|yellow|{info.label}|reset| ({key}) = {value}', info.description, '')
        return CommandResult.ok(f'Showed {key}.')

    async def _set_one(self, ctx: GameContext, key: str, raw_value: str) -> CommandResult:
        label = SETTINGS_METADATA[key].label
        if key == _VICTORY_ITEM_KEY and raw_value.strip() == '?':
            items = victory_eligible_treasures()
            await ctx.send(
                '', 'Treasure items eligible for Victory Item:', '',
                *format_victory_item_choices(items), '',
            )
            return CommandResult.ok('Listed eligible treasures.')

        try:
            value = parse_value(key, raw_value)
            if key == _VICTORY_ITEM_KEY:
                _validate_victory_item(value)
            server_config.set_validated(key, value)
        except ValueError as exc:
            await ctx.send(str(exc))
            return CommandResult.fail(str(exc), error='invalid_value')

        new_value = _display_value(key, server_config.get(key))
        await ctx.send(f'{label} set to {new_value}.')
        return CommandResult.ok(f'{key} set to {new_value}.')
