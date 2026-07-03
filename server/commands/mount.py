"""commands/mount.py — MOUNT: climb onto your captured horse.

Phase 1 of the MOUNT/DISMOUNT/CHARGE plan (see MECHANICS.md "Horses").
Ported behavior: requires a MOUNT-flagged ally in the party (from LASSO,
see commands/lasso.py); refuses if already mounted, if the mount has died
or fled, or if the player is standing in a water room (SPUR.COMBAT.S:74 --
water rooms need a Boat, not a horse).

State is tracked via PlayerFlags.MOUNTED (flags.py), which already
round-trips through save/load generically -- no new Player field needed.
"""
from __future__ import annotations

from bar.allies import find_mount
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext

_WATER_FLAGS = {'water', 'water_with_rocks'}


def _current_room(ctx: GameContext):
    game_map = getattr(ctx.server, 'game_map', None)
    if game_map is None:
        return None
    level = getattr(ctx.player, 'map_level', 1) or 1
    room_no = getattr(ctx.client, 'room', 1) or 1
    return game_map.get_room(int(level), int(room_no))


def _in_water_room(ctx: GameContext) -> bool:
    room = _current_room(ctx)
    flags = getattr(room, 'flags', None) or [] if room else []
    return any(f in _WATER_FLAGS for f in flags)


class MountCommand(Command):
    name    = 'mount'
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Climb onto your horse.',
        category = HelpCategory.GENERAL,
        usage    = [('mount', 'Mount your horse, if you have one.')],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player

        if player.query_flag(PlayerFlags.MOUNTED):
            await ctx.send("You're already mounted.")
            return CommandResult.ok()

        mount = find_mount(player)
        if mount is None:
            await ctx.send('You have no horse to mount.')
            return CommandResult.fail(error='no_mount')

        if _in_water_room(ctx):
            await ctx.send(f"{mount.name} refuses to go in the water!")
            return CommandResult.fail(error='water_room')

        player.set_flag(PlayerFlags.MOUNTED)
        player.unsaved_changes = True
        await ctx.send(f'You climb onto {mount.name}.')
        return CommandResult.ok()
