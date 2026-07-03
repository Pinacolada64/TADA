"""commands/dismount.py — DISMOUNT: get off your horse.

Phase 1 of the MOUNT/DISMOUNT/CHARGE plan (see MECHANICS.md "Horses").
Unconditional while mounted -- no guards beyond "are you actually mounted".
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext


class DismountCommand(Command):
    name    = 'dismount'
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Get off your horse.',
        category = HelpCategory.GENERAL,
        usage    = [('dismount', 'Dismount, if you are riding your horse.')],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player

        if not player.query_flag(PlayerFlags.MOUNTED):
            await ctx.send("You're not mounted.")
            return CommandResult.ok()

        player.clear_flag(PlayerFlags.MOUNTED)
        player.unsaved_changes = True
        await ctx.send('You dismount.')
        return CommandResult.ok()
