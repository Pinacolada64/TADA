"""commands/stay.py — STAY: drop off the guild members following you.

SPUR.MISC4.S:278-316 "stay"/"stay.a"/"stay.b" (MAIN.STAY; the same
stay.a also runs automatically as LOGON.STAY on logoff -- see
guild_follow.drop_off_on_logoff()):

    stay
     if vv<3 print \\"ONLY GUILD MEMBERS CAN HAVE FOLLOWERS.":goto advent
     if yt$="*" print \\"NOBODY IS FOLLOWING!":goto advent
     ...
    stay.a
     if instr("\\|/",ww$) then if not instr(i$,"67") zt=1
     if instr("-}-",ww$) then if not instr(i$,"34") zt=1
     if instr("=[]",ww$) then if not instr(i$,"89") zt=1
     if (instr("#!",lo$)) or (instr("+",ww$)) then zt=1
     if (instr("@@",lo$)) or (instr("<<",lo$)) then zt=1
     if instr("OK",lo$) zt=0
     if zt=1 print \\"A STRANGE FORCE PREVENTS YOU FROM DROPPING OFF FOLLOWERS!":return
     print \\"DROPPING OFF FOLLOWERS."
    stay.b  (per follower: rewrite spur.users level/room, leader name -> misc.data)

Carried (logged-off) followers get their saved location rewritten to
this room; live followers are simply released. See guild_follow.py.
"""
from __future__ import annotations

import guild_follow
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext


class StayCommand(Command):
    name    = 'stay'
    aliases = []
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Leave the guild members following you here.',
        description = (
            'Drops off everyone who answered your |command|FOLLOW ME|reset|. Guildmates who '
            'are logged off stay in this room, and are told who they '
            'followed the next time they log in; guildmates who are playing '
            'stop following you. Logging off does the same thing '
            'automatically.\n\n'
            "A strange force won't let you drop followers off in another "
            "guild's territory, a free-fire room, or on the water."
        ),
        category = HelpCategory.GENERAL,
        usage    = [('stay', 'Drop off your followers here.')],
        see_also = ['follow'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        if not guild_follow.is_guild_member(player):
            await ctx.send('Only guild members can have followers.')
            return CommandResult.fail('Not a guild member.')
        if not guild_follow.follower_count(ctx.server, player):
            await ctx.send('Nobody is following!')
            return CommandResult.ok()

        game_map = getattr(ctx.server, 'game_map', None)
        level = int(getattr(player, 'map_level', 1) or 1)
        room_no = int(getattr(ctx.client, 'room', None) or getattr(player, 'map_room', 1) or 1)
        room = game_map.get_room(level, room_no) if game_map else None
        if guild_follow.drop_off_blocked(player, room):
            await ctx.send('A strange force prevents you from dropping off followers!')
            return CommandResult.fail('Drop-off blocked.')

        lines = ['Dropping off followers.']
        released = await guild_follow.release_live_followers(ctx, '{leader} tells you to stay here.')
        dropped = guild_follow.drop_off_carried(ctx)
        for name in released + dropped:
            lines.append(f'{name} stays here.')
        await ctx.send(lines)
        return CommandResult.ok()
