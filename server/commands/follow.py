"""commands/follow.py — FOLLOW (alias FL): quick toggle for
PlayerFlags.GUILD_FOLLOW_MODE.

SPUR.MISC5.S:240-245 "follow" (dispatched off the "FL" token,
SPUR.MISC5.S:14 `if i$="FL" goto follow` -- not to be confused with
the separate "FOLLOW ME" companion-tracking command, a different
mechanic entirely, dispatched off its own token on the same line):

    follow
     if vv<3 print \"For guild members only":goto advent
     zt=3:zw=10:zw$="0"
     input @2\"Do you wish to FOLLOW fellow guild members? y/[N]:"i$
     print "FOLLOW - ";:if i$="Y" zw$="1" print "ON":else print "OFF"
     gosub zu$:goto advent

Guild members only (SPUR's vv<3 excludes Civilian/Outlaw -- matches
commands/stats.py's own Guild Follow display gate). Same underlying
flag already surfaced read-only by commands/stats.py and toggleable
via EditPlayer's Flags -> Option Toggles menu (commands/editplayer.py)
-- this is just a direct shortcut, same pattern as commands/pm.py and
commands/dbg.py's toggle-shortcut commands.
"""
from __future__ import annotations

from base_classes import Guild
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext


class FollowCommand(Command):
    name    = 'follow'
    aliases = ['fl']
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Toggle Guild Follow on/off (guild members only).',
        description = (
            'When on, marks you as willing to follow fellow guild members. '
            'Guild members only -- Civilians and Outlaws have no guild to '
            'follow.'
        ),
        category = HelpCategory.GENERAL,
        usage    = [('follow', 'Toggle Guild Follow on/off.')],
        admin_notes = [
            "PlayerFlags.GUILD_FOLLOW_MODE -- also toggleable (for any "
            "player, not just yourself) via EditPlayer's Flags -> Option "
            "Toggles menu.",
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        guild = getattr(player, 'guild', Guild.CIVILIAN)
        if guild in (Guild.CIVILIAN, Guild.OUTLAW):
            await ctx.send('For guild members only.')
            return CommandResult.fail('Not a guild member.')

        new_state, _ = player.toggle_flag(PlayerFlags.GUILD_FOLLOW_MODE)
        player.unsaved_changes = True
        await ctx.send(f"Guild Follow: {'On' if new_state else 'Off'}")
        return CommandResult.ok()
