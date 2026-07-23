"""commands/teleport.py

TeleportCommand — instantly move to any room by number or name.

Usage:  #<room>            e.g. #37  (no space required) -- room on your
                            current level
        #<level> <room>    e.g. #5 18 -- room 18 on level 5
        # <room>           space-separated
        teleport <room>    room number
        teleport <level> <room>  level + room number
        teleport <name>    substring search — lists matches or teleports if unique
        teleport #learn [<name>] save the current room under <name>, or
                            under the room's own name if <name> is omitted
        teleport <name>    exact (case-insensitive) match against a saved
                            name teleports there directly, ahead of the
                            substring search above
        teleport #list      list saved destinations ('#show' also works)
        teleport #find <text>    substring-search room names across every
                            level (not just your current one) and report
                            where matches are -- doesn't teleport there
        teleport #forget [<alias>]  remove a saved destination, or the one
                            saved under the current room's own name if
                            <alias> is omitted

The command processor splits '#37' into ['#', '37'] automatically -- and
also strips the leading '#' from '#learn'/'#list'/'#show'/'#find'/
'#forget' the same way when invoked via the bare '#' alias, so those are
detected by their bare word rather than by a leading '#' (see execute()'s
first-token check). With two numeric args, the first is a level (1-7)
rather than a room number -- '#5' alone stays on your current level, but
'#5 18' jumps to level 5's room 18, even if that's a different level
than the one you're on. Administrator or Dungeon Master.
"""

import logging
import re

from base_classes import RoomAlignment
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext

log = logging.getLogger(__name__)


def _normalize_search_text(s: str) -> str:
    """Lowercase and strip everything but letters/digits, so a query like
    "jakes" still matches "Jake's Stable" despite the apostrophe (and
    "wall bar grill" still matches "WALL BAR & GRILL" despite the '&')."""
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _special_locations() -> dict[str, tuple[int, int]]:
    """A few notable areas are hardcoded room-exit interceptions in
    commands/movement.py rather than plain data-driven rooms, so their
    real room name in level_*.json (e.g. room 157's is "The Ocean")
    doesn't mention them at all -- '#find' would otherwise never surface
    them. Listed here by their commonly-known name so a search like
    "#find jakes" still finds Jake's Stable. Imported lazily (like
    _teleport()'s guild-HQ import below) to avoid a module-load-order
    dependency on commands.movement."""
    from commands.movement import (
        _ALLY_GUILD_LEVEL, _ALLY_GUILD_ROOM, _JAKES_LEVEL, _JAKES_ROOM,
    )
    return {
        "Jake's Stable":        (_JAKES_LEVEL, _JAKES_ROOM),
        "Bubba's Allys Guild":  (_ALLY_GUILD_LEVEL, _ALLY_GUILD_ROOM),
    }


def _lookup_destination(ctx: GameContext, query_name: str) -> tuple[int, int] | None:
    """Return the (level, room) saved under *query_name* (exact match,
    case-insensitive), or None if nothing matches."""
    cs = getattr(ctx.player, 'command_settings', None)
    destinations = getattr(getattr(cs, 'teleport', None), 'destinations', None) or {}
    for saved_name, dest in destinations.items():
        if saved_name.lower() == query_name.lower():
            return tuple(dest)
    return None


def _room_monster(ctx: GameContext, level: int, room_no: int | None) -> dict | None:
    """Return the live monster dict in (level, room_no), or None -- no
    monster there, or it's already dead/charmed-away for this player
    (same gating as encounters/monster.py's try_monster_encounter)."""
    if room_no is None:
        return None
    game_map = getattr(ctx.server, 'game_map', None)
    room = game_map.get_room(level, room_no) if game_map else None
    monster_no = int(getattr(room, 'monster', 0) or 0) if room else 0
    if not monster_no:
        return None
    player = ctx.player
    if (monster_no in (getattr(player, 'dead_monsters', None) or [])
            or monster_no in (getattr(player, 'charmed_monsters', None) or [])):
        return None
    from monsters import get_monster
    return get_monster(getattr(ctx.server, 'monsters', None) or [], monster_no)


class TeleportCommand(Command):
    """Instantly move to any room on the map."""

    name    = '#'
    aliases = ['teleport', 't']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Teleport to a room by number or name.',
        description = (
            'Instantly move to any room on the map. Administrator or '
            'Dungeon Master only. Pass a room number to go there directly, '
            'or a name fragment to search — lists all matches, or '
            'teleports immediately if unique.'
        ),
        category    = HelpCategory.MOVEMENT,
        usage       = [
            ('#<room>',          'Teleport to that room number on your current level.'),
            ('#<level> <room>',  'Teleport to that room number on a specific level.'),
            ('teleport <room>',  'Alternate form.'),
            ('teleport <level> <room>', 'Alternate form, with a level.'),
            ('teleport <name>',  'Search rooms by name fragment.'),
            ('teleport #learn [<name>]', "Save the current room under <name>, or its own room name."),
            ('teleport <name>',  'Jump to a saved destination by exact name.'),
            ('teleport #list',   'List saved destinations (\'#show\' also works).'),
            ('teleport #find <text>', 'Search room names across every level.'),
            ('teleport #forget [<alias>]', 'Remove a saved destination, or the current room\'s.'),
        ],
        examples = [
            ('#37',           'Go to room 37 on your current level.'),
            ('#5 18',         'Go to room 18 on level 5.'),
            ('teleport 1',    'Go to room 1.'),
            ('teleport guild', 'List all rooms whose name contains "guild".'),
            ('#learn armory', 'Save the current room as "armory".'),
            ('#learn',        'Save the current room under its own name.'),
            ('teleport armory', 'Jump to the saved "armory" destination.'),
            ('teleport #list', 'List all saved destinations.'),
            ('#forget armory', 'Remove the saved "armory" destination.'),
            ('t #find jakes', "Find every room whose name contains \"jakes\", on any level."),
        ],
        notes = ['Administrator or Dungeon Master only.'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        if not (ctx.player.query_flag(PlayerFlags.ADMIN)
                or ctx.player.query_flag(PlayerFlags.DUNGEON_MASTER)):
            await ctx.send('You lack the power to teleport.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        # 'teleport #learn <name>' arrives as args=('#learn', <name...>);
        # '#learn <name>' via the bare '#' alias loses its leading '#' in
        # command_processor.process_command()'s '#<word>' splitting, so it
        # arrives as args=('learn', <name...>) instead -- check the bare
        # word either way rather than relying on parse_args' '#'-prefix
        # switch detection. Same deal for '#list'/'#show'/'#find'/'#forget'.
        first = args[0].lstrip('#').lower() if args else ''
        if first == 'learn':
            return await self._learn(ctx, args[1:])
        if first in ('list', 'show'):
            return await self._list_destinations(ctx)
        if first == 'find':
            return await self._find(ctx, args[1:])
        if first == 'forget':
            return await self._forget(ctx, args[1:])

        positional, _ = self.parse_args(*args)

        if not positional:
            await ctx.send('Usage: #<room number>  or  #<level> <room>  or  teleport <name fragment>')
            return CommandResult.fail('No room specified.', error='missing_args')

        game_map     = getattr(ctx.server, 'game_map', None)
        current_level = int(getattr(ctx.player, 'map_level', 1) or 1)

        # A saved destination name (exact match, case-insensitive) wins
        # over both the numeric room parse and the substring name search
        # below.
        dest = _lookup_destination(ctx, ' '.join(positional))
        if dest is not None:
            dest_level, dest_room = dest
            if game_map and game_map.get_room(dest_level, dest_room) is None:
                await ctx.send(f'Saved destination no longer exists (level {dest_level}, room {dest_room}).')
                return CommandResult.fail('Stale destination.', error='bad_room')
            return await self._teleport(ctx, dest_room, level=dest_level)

        # Two numeric args -> #<level> <room>; one numeric arg -> #<room>
        # on the current level (existing behaviour).
        try:
            nums = [int(p) for p in positional[:2]]
        except ValueError:
            nums = None

        if nums is not None:
            if len(nums) == 2:
                level, dest = nums
            else:
                level, dest = current_level, nums[0]

            if game_map and game_map.get_room(level, dest) is None:
                await ctx.send(f'Room {dest} does not exist on level {level}.')
                return CommandResult.fail(f'Room {dest} not found.', error='bad_room')
            return await self._teleport(ctx, dest, level=level)

        # Non-numeric → search room names.
        query = ' '.join(positional).lower()
        if not game_map:
            await ctx.send('Map not loaded.')
            return CommandResult.fail('No map.', error='no_map')

        level_rooms = game_map.levels.get(current_level, {})
        matches = [
            (num, room)
            for num, room in sorted(level_rooms.items())
            if query in getattr(room, 'name', '').lower()
        ]

        if not matches:
            await ctx.send(f'No rooms found matching "{query}".')
            return CommandResult.fail('No matches.', error='no_match')

        if len(matches) == 1:
            num, room = matches[0]
            await ctx.send(f'One match: [{num}] {room.name}')
            return await self._teleport(ctx, num)

        # Multiple matches — list them.
        lines = [f'Rooms matching "{query}":', '']
        for num, room in matches:
            lines.append(f'  [{num:>4}] {room.name}')
        lines += ['', f'{len(matches)} rooms found.  Use #<number> to teleport.']
        await ctx.send(lines)
        return CommandResult.ok()

    async def _learn(self, ctx: GameContext, name_parts: tuple[str, ...]) -> CommandResult:
        name = ' '.join(name_parts).strip()

        room = getattr(ctx.client, 'room', None)
        if room is None:
            await ctx.send('Cannot learn a destination -- current room is unknown.')
            return CommandResult.fail('No current room.', error='no_room')
        level = int(getattr(ctx.player, 'map_level', 1) or 1)

        if not name:
            # No <name> given -- default to the current room's own name.
            game_map = getattr(ctx.server, 'game_map', None)
            room_obj = game_map.get_room(level, room) if game_map else None
            name = getattr(room_obj, 'name', None) or ''
            if not name:
                await ctx.send('Usage: teleport #learn [<name>] -- current room has no name to fall back on.')
                return CommandResult.fail('No name given.', error='missing_args')

        cs = getattr(ctx.player, 'command_settings', None)
        if cs is None:
            await ctx.send('Command settings not available.')
            return CommandResult.fail('No command settings.', error='no_command_settings')

        cs.teleport.destinations[name] = (level, room)
        ctx.player.unsaved_changes = True
        await ctx.send(f'Learned teleport destination "{name}" -> level {level}, room {room}.')
        return CommandResult.ok()

    async def _forget(self, ctx: GameContext, name_parts: tuple[str, ...]) -> CommandResult:
        """'#forget [<alias>]' -- remove a saved destination (exact match,
        case-insensitive). With no <alias>, defaults to the current
        room's own name, mirroring #learn's fallback."""
        name = ' '.join(name_parts).strip()

        cs = getattr(ctx.player, 'command_settings', None)
        if cs is None:
            await ctx.send('Command settings not available.')
            return CommandResult.fail('No command settings.', error='no_command_settings')
        destinations = cs.teleport.destinations

        if not name:
            room = getattr(ctx.client, 'room', None)
            level = int(getattr(ctx.player, 'map_level', 1) or 1)
            game_map = getattr(ctx.server, 'game_map', None)
            room_obj = game_map.get_room(level, room) if game_map and room is not None else None
            name = getattr(room_obj, 'name', None) or ''
            if not name:
                await ctx.send('Usage: teleport #forget [<alias>] -- current room has no name to fall back on.')
                return CommandResult.fail('No alias given.', error='missing_args')

        for saved_name in destinations:
            if saved_name.lower() == name.lower():
                del destinations[saved_name]
                ctx.player.unsaved_changes = True
                await ctx.send(f'Forgot teleport destination "{saved_name}".')
                return CommandResult.ok()

        await ctx.send(f'No saved teleport destination named "{name}".')
        return CommandResult.fail('Destination not found.', error='no_match')

    async def _list_destinations(self, ctx: GameContext) -> CommandResult:
        cs = getattr(ctx.player, 'command_settings', None)
        destinations = getattr(getattr(cs, 'teleport', None), 'destinations', None) or {}

        if not destinations:
            await ctx.send('No teleport destinations saved. Use #learn <name> to save one.')
            return CommandResult.ok()

        lines = ['Saved teleport destinations:', '']
        for dest_name, (level, room) in sorted(destinations.items(), key=lambda kv: kv[0].lower()):
            lines.append(f'  {dest_name} -> level {level}, room {room}')
        lines += ['', 'Use teleport <name> to jump there, #learn <name> to save the '
                       'current room, or #<room number>.']
        await ctx.send(lines)
        return CommandResult.ok()

    async def _find(self, ctx: GameContext, query_parts: tuple[str, ...]) -> CommandResult:
        """'#find <text>' -- substring-search room names across *every*
        level, unlike the bare 'teleport <name>' search which is scoped
        to the player's current level only. Purely informational -- it
        reports where matches are, it doesn't teleport there."""
        query = ' '.join(query_parts).strip()
        if not query:
            await ctx.send('Usage: teleport #find <text>')
            return CommandResult.fail('No search text.', error='missing_args')

        game_map = getattr(ctx.server, 'game_map', None)
        if not game_map:
            await ctx.send('Map not loaded.')
            return CommandResult.fail('No map.', error='no_map')

        q = _normalize_search_text(query)
        matches = [
            (level, num, room.name)
            for level, rooms in sorted(getattr(game_map, 'levels', {}).items())
            for num, room in sorted(rooms.items())
            if q in _normalize_search_text(getattr(room, 'name', ''))
        ]
        # Hardcoded-interception areas (Jake's Stable etc.) whose actual
        # room name doesn't mention them at all -- see _special_locations().
        matches += [
            (level, room_no, special_name)
            for special_name, (level, room_no) in _special_locations().items()
            if q in _normalize_search_text(special_name)
        ]
        matches.sort(key=lambda m: (m[0], m[1]))

        if not matches:
            await ctx.send(f'No rooms found matching "{query}".')
            return CommandResult.fail('No matches.', error='no_match')

        lines = [f'Rooms matching "{query}":', '']
        for level, num, display_name in matches:
            lines.append(f'  Level {level}, room {num}: {display_name}')
        lines += ['', f'{len(matches)} room(s) found.  Use #<level> <room> to teleport there.']
        await ctx.send(lines)
        return CommandResult.ok()

    async def _teleport(self, ctx: GameContext, dest: int, *, level: int | None = None) -> CommandResult:
        old_room  = getattr(ctx.client, 'room', None)
        old_level = int(getattr(ctx.player, 'map_level', 1) or 1)
        name      = ctx.player.name

        # SPUR.MISC3.S's cst.shop label: a live monster in the room being
        # left reacts to a teleport-away instead of a plain "flash of
        # light." A 'tough' one (SPUR's '.' wy$ marker -- see
        # monsters.py's flag table) casts a Freeze Adventurer spell and
        # blocks the teleport outright, *unless* it's also 'mechanical'
        # (SPUR's ':' marker), which gets its own "sensors on" flavor
        # line instead and doesn't block anything -- an ordinary monster
        # just looks puzzled. SPUR's own flavor text is ALL-CAPS
        # (screen-hardware artifact); sentence-cased here to match this
        # port's style.
        monster = _room_monster(ctx, old_level, old_room)
        if monster is not None:
            flags = monster.get('flags') or {}
            mname = monster.get('name', 'The monster')
            if flags.get('tough') and not flags.get('mechanical'):
                await ctx.send(f"{mname} casts a 'Freeze Adventurer' spell!")
                return CommandResult.fail('The teleport is blocked!', error='teleport_blocked')
            if flags.get('mechanical'):
                await ctx.send(f'Sensors on {mname} goes nuts as you dematerialize!')
            else:
                await ctx.send(f'{mname} looks puzzled as you fade from view.')

        await ctx.send('You disappear in a flash of light.')
        await ctx.send_room(f'{name} disappears in a flash of light.', exclude_self=True)
        ctx.client.room        = dest
        ctx.player.map_room    = dest
        if level is not None and level != old_level:
            ctx.player.map_level = level
            try:
                ctx.client.map_level = level
            except Exception:
                pass
        ctx.player.unsaved_changes = True
        log.info('%s teleported from level %s room %s to level %s room %s',
                  name, old_level, old_room, level if level is not None else old_level, dest)
        await ctx.send('You appear in a flash of light.')
        await ctx.send_room(f'{name} appears in a flash of light.', exclude_self=True)

        # If the destination is a guild-aligned room, trigger the HQ session
        # the same way movement.py does when walking into it.
        game_map = getattr(ctx.server, 'game_map', None)
        level = int(getattr(ctx.player, 'map_level', 1) or 1)
        dest_room = game_map.get_room(level, dest) if game_map else None
        align = getattr(dest_room, 'alignment', None)
        _GUILD_KEY = {
            RoomAlignment.CLAW:  'CLAW',
            RoomAlignment.SWORD: 'SWORD',
            RoomAlignment.FIST:  'FIST',
        }
        gkey = _GUILD_KEY.get(align)
        if gkey:
            from commands.movement import _enter_guild_hq
            await _enter_guild_hq(ctx, gkey)
        else:
            await ctx.server._show_room(ctx)
        return CommandResult.ok()
