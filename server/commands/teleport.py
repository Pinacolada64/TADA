"""commands/teleport.py

TeleportCommand — instantly move to any room by number or name.

Usage:  #<room>            e.g. #37  (no space required) -- room on your
                            current level
        #<level> <room>    e.g. #5 18 -- room 18 on level 5
        # <room>           space-separated
        teleport <room>    room number
        teleport <level> <room>  level + room number
        teleport <name>    substring search — lists matches or teleports if unique

The command processor splits '#37' into ['#', '37'] automatically. With
two numeric args, the first is a level (1-7) rather than a room number
-- '#5' alone stays on your current level, but '#5 18' jumps to level
5's room 18, even if that's a different level than the one you're on.
Administrator or Dungeon Master.
"""

import logging

from base_classes import RoomAlignment
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext

log = logging.getLogger(__name__)


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
        ],
        examples = [
            ('#37',           'Go to room 37 on your current level.'),
            ('#5 18',         'Go to room 18 on level 5.'),
            ('teleport 1',    'Go to room 1.'),
            ('teleport guild', 'List all rooms whose name contains "guild".'),
        ],
        notes = ['Administrator or Dungeon Master only.'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)

        if not (ctx.player.query_flag(PlayerFlags.ADMIN)
                or ctx.player.query_flag(PlayerFlags.DUNGEON_MASTER)):
            await ctx.send('You lack the power to teleport.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        if not positional:
            await ctx.send('Usage: #<room number>  or  #<level> <room>  or  teleport <name fragment>')
            return CommandResult.fail('No room specified.', error='missing_args')

        game_map     = getattr(ctx.server, 'game_map', None)
        current_level = int(getattr(ctx.player, 'map_level', 1) or 1)

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

    async def _teleport(self, ctx: GameContext, dest: int, *, level: int | None = None) -> CommandResult:
        old_room  = getattr(ctx.client, 'room', None)
        old_level = int(getattr(ctx.player, 'map_level', 1) or 1)
        name      = ctx.player.name
        await ctx.send(f'{name} disappears in a flash of light.')
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
        await ctx.send(f'{name} appears in a flash of light.')
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
