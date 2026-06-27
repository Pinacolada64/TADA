"""commands/teleport.py

TeleportCommand — instantly move to any room by number.

Usage:  #<room>       e.g. #37  (no space required)
        # <room>      space-separated
        teleport <room>

The command processor splits '#37' into ['#', '37'] automatically.
Admin-only.
"""

import logging

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext

log = logging.getLogger(__name__)


class TeleportCommand(Command):
    """Instantly move to any room on the map."""

    name    = '#'
    aliases = ['teleport']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Teleport to a room by number.',
        description = 'Instantly move to any room on the map. Admin only.',
        category    = HelpCategory.MOVEMENT,
        usage       = [
            ('#<room>',        'Teleport to that room number.'),
            ('teleport <room>', 'Alternate form.'),
        ],
        examples = [
            ('#37',        'Go to room 37.'),
            ('teleport 1', 'Go to room 1.'),
        ],
        notes = ['Admin only.'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)

        if not ctx.player.query_flag(PlayerFlags.ADMIN):
            await ctx.send('You lack the power to teleport.')
            return CommandResult.fail('Permission denied.', error='permission_denied')

        if not positional:
            await ctx.send('Usage: #<room number>')
            return CommandResult.fail('No room specified.', error='missing_args')

        try:
            dest = int(positional[0])
        except ValueError:
            await ctx.send(f'"{positional[0]}" is not a valid room number.')
            return CommandResult.fail('Bad room number.', error='bad_args')

        game_map = getattr(ctx.server, 'game_map', None)
        if game_map and dest not in game_map.rooms:
            await ctx.send(f'Room {dest} does not exist.')
            return CommandResult.fail(f'Room {dest} not found.', error='bad_room')

        old_room        = getattr(ctx.client, 'room', None)
        name            = ctx.player.name
        await ctx.send(f'{name} disappears in a flash of light.')
        await ctx.send_room(f'{name} disappears in a flash of light.', exclude_self=True)
        ctx.client.room = dest
        log.info('%s teleported from room %s to room %s', name, old_room, dest)
        await ctx.send(f'{name} appears in a flash of light.')
        await ctx.send_room(f'{name} appears in a flash of light.', exclude_self=True)
        await ctx.server._show_room(ctx)
        return CommandResult.ok()
