"""commands/pm.py — PM: quick toggle for PlayerFlags.PROMPT_MODE.

Prompt Mode already round-trips through EditPlayer's Flags -> Option
Toggles menu (commands/editplayer.py), but that's several menu hops for
something a player composing/reading on the message board (commands/
board.py, commands/board_reply.py) would want to flip on the fly. This
is just a shortcut to player.toggle_flag(PlayerFlags.PROMPT_MODE) --
same underlying flag, no new state, matching commands/dbg.py's own
shortcut-to-EditPlayer pattern for PlayerFlags.DEBUG_MODE.
"""
from __future__ import annotations

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext


class PromptModeCommand(Command):
    name    = 'pm'
    aliases = ['promptmode']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Toggle Prompt Mode on/off.',
        description = (
            'When on, reading a thread on the message board (BOARD command) '
            'shows one message at a time with a [R]eply/[M]ail poster/<#>/'
            'Enter menu after each, instead of dumping the whole thread at '
            'once.'
        ),
        category = HelpCategory.GENERAL,
        usage    = [('pm', 'Toggle Prompt Mode on/off.')],
        admin_notes = [
            "PlayerFlags.PROMPT_MODE -- also toggleable (for any player, "
            "not just yourself) via EditPlayer's Flags -> Option Toggles "
            "menu.",
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        new_state, _ = player.toggle_flag(PlayerFlags.PROMPT_MODE)
        player.unsaved_changes = True
        await ctx.send(f"Prompt Mode: {'On' if new_state else 'Off'}.")
        return CommandResult.ok()
