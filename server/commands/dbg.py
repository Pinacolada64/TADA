"""commands/dbg.py — DBG: quick toggle for PlayerFlags.DEBUG_MODE.

Debug mode already round-trips through EditPlayer's flags menu
(commands/editplayer.py), but that's several menu hops for something
toggled often during testing. This is just a shortcut to
player.toggle_flag(PlayerFlags.DEBUG_MODE) -- same underlying flag, no
new state.
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext


class DbgCommand(Command):
    name    = 'dbg'
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Toggle debug mode on/off.',
        category = HelpCategory.GENERAL,
        usage    = [('dbg', 'Toggle debug mode (same flag as EditPlayer\'s Debug Mode).')],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        new_state, _ = player.toggle_flag(PlayerFlags.DEBUG_MODE)
        player.unsaved_changes = True
        await ctx.send(f"Debug mode: {'On' if new_state else 'Off'}.")
        return CommandResult.ok()
