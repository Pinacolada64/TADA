"""commands/list_locations.py — Admin/DM tool: list room locations of
items/weapons across the whole map.

    list #w[eapons]   — weapons.json entries, via each room's .weapon field
    list #a[rmor]     — objects.json entries with type == 'armor'
    list #s[hield]    — objects.json entries with type == 'shield'
    list #i[tems]     — every objects.json entry regardless of type
    list #<type>      — any other objects.json "type" string directly
                         (book, treasure, ammunition, compass, container,
                         cursed, power)
    list #w #tel      — after listing, prompt to pick one and teleport there

Not from SPUR -- a debugging/moderation convenience, not a ported
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
from network_context import GameContext

_CATEGORY_ALIASES = {
    'w': 'weapon', 'weapon': 'weapon', 'weapons': 'weapon',
    'a': 'armor',  'armor':  'armor',
    's': 'shield', 'shield': 'shield',
    'i': 'item',   'item':   'item',   'items': 'item',
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
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'List room locations of items/weapons across the map (admin/DM only).',
        description = (
            'Scans every room on every level and reports where a given '
            "category of object currently sits -- every weapon, every "
            'shield, every book, and so on. Admin/Dungeon Master only.'
        ),
        category = HelpCategory.ADMINISTRATIVE,
        usage    = [
            ('list #w[eapons]', 'List every weapon location.'),
            ('list #a[rmor]',   'List every armor location.'),
            ('list #s[hield]',  'List every shield location.'),
            ('list #i[tems]',   'List every item location (any type).'),
            ('list #<type>',    'List by a specific objects.json type (book, treasure, etc.).'),
        ],
        examples = [
            ('list #w',       'List all weapon locations.'),
            ('list #shield',  'List all shield locations.'),
            ('list #w #tel',  'List weapons, then optionally teleport to one.'),
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

        want_teleport    = 'tel' in switches
        category_tokens  = [s for s in switches if s != 'tel']

        if not category_tokens:
            await ctx.send(
                # Double brackets escape highlight_brackets() (formatting.py)
                # so these render as literal "[eapons]" etc. instead of
                # being swallowed as [highlight-me] markup -- same escape
                # commands/help.py's _esc() applies automatically to Help
                # usage fields, needed here by hand since this is a raw
                # ctx.send(), not a Help(usage=...) entry.
                'Usage: list #w[[eapons]] | #i[[tems]] | #a[[rmor]] | #s[[hield]] | '
                '#<type>  [[#tel]]'
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
        elif category == 'item':
            found = _find_items(game_map, server, None)
        else:
            found = _find_items(game_map, server, category)

        if not found:
            await ctx.send(f'No {category} locations found.')
            return CommandResult.ok()

        found.sort(key=lambda m: (m[0], m[1]))

        from formatting import border_style_for_ctx
        from table import Table

        t = Table(headers=['##', 'Name', 'Level', 'Room'],
                  title=f'{category.capitalize()} locations ({len(found)})',
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
        raw_choice = await ctx.prompt('Teleport to which number? (blank to cancel)')
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
