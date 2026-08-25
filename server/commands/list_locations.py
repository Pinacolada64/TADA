"""commands/list_locations.py — Admin/DM tool: list room locations of
items/weapons across the whole map. Also aliased as 'find'.

    list #w[eapons]   — weapons.json entries, via each room's .weapon field
    list #a[rmor]     — objects.json entries with type == 'armor'
    list #s[hield]    — objects.json entries with type == 'shield'
    list #i[tems]     — every objects.json entry regardless of type
    list #<type>      — any other objects.json "type" string directly
                         (book, treasure, ammunition, compass, container,
                         cursed, power)
    list #m[onsters]  — monsters.json entries, via each room's .monster field
    list #r[ations]   — rations.json entries (food/drink), via each room's
                         .food field
    list #w #tel      — after listing, prompt to pick one and teleport there
    list #m <name>    — any category also takes an optional substring (case
                         -insensitive, matched against the entry's "name")
                         to narrow the results, e.g. "list #m goblin" or
                         "find #w rusty sword"

New in TADA -- a debugging/moderation convenience, not a ported
mechanic. Scans every room on every level (game_map.levels), not just
the player's current room, so it can answer "where are all the copies
of X on the whole map" at a glance instead of digging through
commands/editplayer.py's catalog browser (which lists weapons.json/
objects.json definitions themselves, not where they're actually placed).

The #tel picker calls commands/teleport.py's TeleportCommand with an
explicit (level, room) pair -- teleport.py originally only accepted a
bare room number and assumed the player's *current* level, which would
have silently sent you to the wrong room whenever a match was on a
different level than the one you're standing on. Ryan's request:
TeleportCommand.execute() now accepts an optional second numeric arg
("#<level> <room>", e.g. "#5 18") for exactly this case.

Gated to Administrator/Dungeon Master, same as commands/whereat.py and
(also per Ryan's request) commands/teleport.py, which used to be
Administrator-only.
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from monsters import get_monster
from network_context import GameContext

_CATEGORY_ALIASES = {
    'w': 'weapon',  'weapon':  'weapon', 'weapons':  'weapon',
    'a': 'armor',   'armor':   'armor',
    's': 'shield',  'shield':  'shield',
    'i': 'item',    'item':    'item',   'items':    'item',
    'm': 'monster', 'monster': 'monster', 'monsters': 'monster',
    'r': 'ration',  'ration':  'ration',  'rations':  'ration',
}


def _is_privileged(player) -> bool:
    return (player.query_flag(PlayerFlags.ADMIN)
            or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def _find_weapons(game_map, server) -> list[tuple[int, int, object, dict]]:
    """Return (level, room_no, room, weapon_dict) for every room whose
    .weapon field resolves to a real weapons.json entry."""
    matches = []
    for level, rooms in game_map.levels.items():
        for room_no, room in rooms.items():
            idx = int(getattr(room, 'weapon', 0) or 0) - 1
            if 0 <= idx < len(server.weapons):
                matches.append((level, room_no, room, server.weapons[idx]))
    return matches


def _find_monsters(game_map, server) -> list[tuple[int, int, object, dict]]:
    """Return (level, room_no, room, monster_dict) for every room whose
    .monster field resolves to a real monsters.json entry.

    Unlike .weapon/.item, .monster is looked up by get_monster()'s
    'number' field, not list position -- monsters.json's numbering has
    gaps, so indexing the list positionally would grab the wrong entry
    (see monsters.py's get_monster() docstring)."""
    matches = []
    for level, rooms in game_map.levels.items():
        for room_no, room in rooms.items():
            number = int(getattr(room, 'monster', 0) or 0)
            if not number:
                continue
            monster = get_monster(server.monsters, number)
            if monster:
                matches.append((level, room_no, room, monster))
    return matches


def _find_rations(game_map, server) -> list[tuple[int, int, object, dict]]:
    """Return (level, room_no, room, ration_dict) for every room whose .food
    field resolves to a real rations.json entry (food or drink kind).

    room.food is a 1-based index into server.rations, same convention as
    .weapon/server.weapons -- see commands/get.py's _room_available_items()."""
    matches = []
    for level, rooms in game_map.levels.items():
        for room_no, room in rooms.items():
            idx = int(getattr(room, 'food', 0) or 0) - 1
            if 0 <= idx < len(server.rations):
                matches.append((level, room_no, room, server.rations[idx]))
    return matches


def _find_items(game_map, server, type_filter: str | None) -> list[tuple[int, int, object, dict]]:
    """Return (level, room_no, room, item_dict) for every room whose .item
    field resolves to a real objects.json entry, optionally filtered by
    the entry's "type" field ('armor', 'shield', etc; None = any type)."""
    matches = []
    for level, rooms in game_map.levels.items():
        for room_no, room in rooms.items():
            idx = int(getattr(room, 'item', 0) or 0) - 1
            if not (0 <= idx < len(server.items)):
                continue
            raw = server.items[idx]
            if type_filter and raw.get('type') != type_filter:
                continue
            matches.append((level, room_no, room, raw))
    return matches


class ListLocationsCommand(Command):
    """Admin/DM tool: find every room holding a given item/weapon type."""

    name    = 'list'
    aliases = ['find']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'List room locations of items/weapons across the map (admin/DM only).',
        description = (
            'Scans every room on every level and reports where a given '
            "category of object currently sits -- every weapon, every "
            'shield, every book, and so on. Admin/Dungeon Master only. '
            "Also available as 'find'."
        ),
        category = HelpCategory.ADMINISTRATIVE,
        usage    = [
            ('list #w[eapons]', 'List every weapon location.'),
            ('list #a[rmor]',   'List every armor location.'),
            ('list #s[hield]',  'List every shield location.'),
            ('list #i[tems]',   'List every item location (any type).'),
            ('list #<type>',    'List by a specific item type (book, treasure, etc.).'),
            ('list #m[onsters]', 'List every monster location.'),
            ('list #r[ations]', 'List every ration (food/drink) location.'),
            ('list #<cat> <name>', 'Narrow to entries whose name contains <name>.'),
        ],
        examples = [
            ('list #w',       'LIST scans every room on every level and reports where a '
                               "category of object currently sits -- a way to answer "
                               '"where are all the copies of X" without digging through '
                               "the raw data files. \"list #w\" reports every weapon's "
                               "current room."),
            ('list #shield',  'Any item "type" works as a switch, not just the '
                               'shorthand ones -- "list #shield" lists every shield the '
                               'same way.'),
            ('list #m goblin', 'A category also takes an optional substring to search for '
                               "a specific entry by name -- \"list #m goblin\" lists only "
                               'monster locations whose name contains "goblin".'),
            ('list #w #tel',  "Adding '#tel' after the listing prompts you to pick one of "
                               "the results and teleport straight to it -- handy for "
                               "actually going to check on a specific copy."),
            ('find #r ale',   "'find' is an alias for 'list' -- \"find #r ale\" searches "
                               'ration locations for names containing "ale".'),
        ],
        notes = ['Admin or Dungeon Master only.'],
        admin_notes = [
            '<type> is any objects.json "type" field value, not just the '
            'shorthand categories listed above.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        if not _is_privileged(player):
            await ctx.send("You don't have permission to use that command.")
            return CommandResult.fail(error='permission_denied')

        positional, switches = self.parse_args(*args)
        switches = [s.lstrip('#') for s in switches]

        want_teleport    = 'tel' in switches
        category_tokens  = [s for s in switches if s != 'tel']
        name_filter      = ' '.join(positional).strip().lower()

        if not category_tokens:
            await ctx.send(
                # Double brackets escape highlight_brackets() (formatting.py)
                # so these render as literal "[eapons]" etc. instead of
                # being swallowed as [highlight-me] markup -- same escape
                # commands/help.py's _esc() applies automatically to Help
                # usage fields, needed here by hand since this is a raw
                # ctx.send(), not a Help(usage=...) entry.
                'Usage: list #w[[eapons]] | #i[[tems]] | #a[[rmor]] | #s[[hield]] | '
                '#m[[onsters]] | #r[[ations]] | #<type>  [<name>]  [[#tel]]'
            )
            return CommandResult.fail('No category specified.', error='missing_args')

        category = _CATEGORY_ALIASES.get(category_tokens[0], category_tokens[0])

        game_map = getattr(ctx.server, 'game_map', None)
        if not game_map:
            await ctx.send('Map not loaded.')
            return CommandResult.fail('No map.', error='no_map')

        server = ctx.server
        if category == 'weapon':
            found = _find_weapons(game_map, server)
        elif category == 'monster':
            found = _find_monsters(game_map, server)
        elif category == 'ration':
            found = _find_rations(game_map, server)
        elif category == 'item':
            found = _find_items(game_map, server, None)
        else:
            found = _find_items(game_map, server, category)

        if name_filter:
            found = [m for m in found if name_filter in m[3].get('name', '').lower()]

        if not found:
            if name_filter:
                await ctx.send(f'No {category} locations found matching "{name_filter}".')
            else:
                await ctx.send(f'No {category} locations found.')
            return CommandResult.ok()

        found.sort(key=lambda m: (m[0], m[1]))

        from formatting import border_style_for_ctx
        from table import Table

        title = f'{category.capitalize()} locations ({len(found)})'
        if name_filter:
            title += f' matching "{name_filter}"'
        t = Table(headers=['##', 'Name', 'Level', 'Room'],
                  title=title,
                  border_style=border_style_for_ctx(ctx))
        for i, (level, room_no, room, raw) in enumerate(found, 1):
            name = raw.get('name', '?')
            t.add_row([str(i), name, str(level), f'{room_no:>3} {room.name}'])

        width = getattr(ctx.player.client_settings, 'screen_columns', 78)
        await ctx.send(t.render(width=width))

        if want_teleport:
            await self._offer_teleport(ctx, found)

        return CommandResult.ok()

    async def _offer_teleport(self, ctx: GameContext, found: list) -> None:
        return_key = ctx.player.return_key
        raw_choice = await ctx.prompt(
            f'Teleport to which number? (or {return_key} to abort)'
        )
        if not raw_choice or not raw_choice.strip():
            return
        try:
            idx = int(raw_choice.strip()) - 1
            if not (0 <= idx < len(found)):
                raise ValueError
        except ValueError:
            await ctx.send('Invalid selection.')
            return

        level, room_no, _room, _raw = found[idx]
        from commands.teleport import TeleportCommand
        await TeleportCommand().execute(ctx, str(level), str(room_no))
