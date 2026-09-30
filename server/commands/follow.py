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

FOLLOW ME (SPUR.MISC5.S:105-165 "come", the other token on :12) is the
leader's side: recruit guildmates standing in your room who have Guild
Follow on, SPUR's "TAKE <name>? [Y]/n" per candidate. Arrives here as
'follow' with a single 'me' argument. See guild_follow.py for the hybrid
live/offline model and what STAY (commands/stay.py) does with them.

    come
     if vv<3 print \"ONLY GUILD MEMBERS MAY USE THIS COMMAND.":goto advent
     ...
     if zm=0 print "NOBODY WANTS TO FOLLOW!"
    come.a  (per character in the room)
     dy$=mid$(zz$,2):if instr(zy$,zx$) gosub come.d:goto come.b
     if instr(zy$,"ABCDE") print dy$" BEING UNCONCIOUS, DOESN'T MOVE.":goto come.b
     print dy$" STARES AT YOU, AND DOESN'T MOVE."
    come.d  (same guild)
     if len(yt$)>210 print "NO MORE CAN FOLLOW!":return
     if instr(zz$,yt$) print dy$" IS ALREADY FOLLOWING..":return
     print "TAKE "dy$"? [Y]/n :";:input @2 xz$:if xz$="N" return
     if instr(zy$,"CDE") goto come.e   (unconscious carry -- not ported yet)
     ...
     if mid$(xx$,10,1)="0" print dy$" DOESN'T WANT TO FOLLOW.." :return
     print dy$" AGREES TO FOLLOW YOU..":goto come.f
"""
from __future__ import annotations

import guild_follow
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
        summary  = 'Toggle Guild Follow, or FOLLOW ME to lead guildmates.',
        description = (
            '|command|FOLLOW|reset| on its own toggles Guild Follow: when on, you are willing '
            'to follow fellow guild members when one of them says |command|FOLLOW ME|reset|.\n\n'
            '|command|FOLLOW ME|reset| gathers guildmates standing in your room who have Guild '
            'Follow on -- you are asked about each one in turn. Guildmates who '
            'are playing right now walk with you whenever you take an exit, '
            'until they move off on their own or switch Guild Follow off. '
            'Guildmates who have logged off are carried along with you until '
            'you |command|STAY|reset| (or log off yourself), which leaves them where you stand; '
            'they are told who they followed the next time they log in.\n\n'
            'Guild members only -- Civilians and Outlaws have no guild to '
            'follow.'
        ),
        category = HelpCategory.GENERAL,
        usage    = [
            ('follow',    'Toggle Guild Follow on/off.'),
            ('follow me', 'Lead the willing guildmates in your room.'),
        ],
        admin_notes = [
            "PlayerFlags.GUILD_FOLLOW_MODE -- also toggleable (for any "
            "player, not just yourself) via EditPlayer's Flags -> Option "
            "Toggles menu.",
            "Live followers: session-only Player.guild_following (leader's "
            "id), moved by guild_follow.bring_followers() from "
            "simple_server.py's _move(). Carried offline followers: "
            "session-only Player.carried_followers on the leader, written "
            "back by STAY / logoff (guild_follow.drop_off_carried()).",
        ],
        see_also = ['stay', 'guilds'],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player
        if args and str(args[0]).lower() == 'me':
            return await self._follow_me(ctx)

        guild = getattr(player, 'guild', Guild.CIVILIAN)
        if guild in (Guild.CIVILIAN, Guild.OUTLAW):
            await ctx.send('For guild members only.')
            return CommandResult.fail('Not a guild member.')

        new_state, _ = player.toggle_flag(PlayerFlags.GUILD_FOLLOW_MODE)
        player.unsaved_changes = True
        await ctx.send(f"Guild Follow: {'On' if new_state else 'Off'}")
        if not new_state:
            await guild_follow.stop_following(ctx)
        return CommandResult.ok()

    async def _follow_me(self, ctx: GameContext) -> CommandResult:
        player = ctx.player
        if not guild_follow.is_guild_member(player):
            await ctx.send('Only guild members may use this command.')
            return CommandResult.fail('Not a guild member.')
        if guild_follow.following_id(player):
            leader_ctx = guild_follow.leader_ctx_for(ctx.server, player)
            leader_name = getattr(getattr(leader_ctx, 'player', None), 'name', 'someone')
            await ctx.send(f"You're following {leader_name} yourself!")
            return CommandResult.fail('Already following.')

        level = int(getattr(player, 'map_level', 1) or 1)
        room = int(getattr(ctx.client, 'room', None) or getattr(player, 'map_room', 1) or 1)

        live = [c.ctx for c in list(ctx.server.clients.values())
                if getattr(c, 'ctx', None) is not None
                and c is not ctx.client
                and getattr(c.ctx, 'player', None) is not None
                and self._in_room(c.ctx, level, room)]
        offline = guild_follow.offline_in_room(ctx.server, level, room, exclude_id=player.id)
        if not live and not offline:
            await ctx.send('Nobody here!')
            return CommandResult.ok()

        recruited = 0
        for cand in [('live', c) for c in live] + [('offline', o) for o in offline]:
            if guild_follow.follower_count(ctx.server, player) >= guild_follow.MAX_FOLLOWERS:
                await ctx.send('No more can follow!')
                break
            if await self._offer(ctx, level, room, *cand):
                recruited += 1

        if not recruited:
            await ctx.send('Nobody wants to follow!')
        return CommandResult.ok()

    @staticmethod
    def _in_room(other_ctx, level: int, room: int) -> bool:
        return (int(getattr(other_ctx.player, 'map_level', 1) or 1) == level
                and int(getattr(other_ctx.client, 'room', 0) or 0) == room
                and not getattr(other_ctx.client, 'virtual_location', None))

    async def _offer(self, ctx: GameContext, level: int, room: int, kind: str, cand) -> bool:
        """One pass of SPUR's come.a/come.d for a single character in the
        room. Returns True if they agreed to follow."""
        leader = ctx.player
        if kind == 'live':
            other = cand.player
            name = other.name
            try:
                guild = Guild(getattr(other, 'guild', Guild.CIVILIAN))
            except ValueError:
                guild = Guild.CIVILIAN
            unconscious = bool(other.query_flag(PlayerFlags.UNCONSCIOUS))
            follow_mode = bool(other.query_flag(PlayerFlags.GUILD_FOLLOW_MODE))
        else:
            name = cand['name']
            try:
                guild = Guild(cand.get('guild'))
            except ValueError:
                guild = Guild.CIVILIAN
            unconscious = cand['unconscious']
            follow_mode = cand['follow_mode']

        if guild != leader.guild:
            if unconscious:
                await ctx.send(f"{name}, being unconscious, doesn't move.")
            else:
                await ctx.send(f"{name} stares at you, and doesn't move.")
            return False

        if kind == 'live':
            if guild_follow.following_id(other) == str(leader.id):
                await ctx.send(f'{name} is already following..')
                return False
            if guild_follow.following_id(other):
                await ctx.send(f'{name} is already following someone else.')
                return False
            if guild_follow.follower_count(ctx.server, other):
                await ctx.send(f'{name} is leading a band of their own.')
                return False

        raw = await ctx.prompt(f'Take {name}? [Y]/n')
        if raw and raw.strip().upper().startswith('N'):
            return False

        if unconscious:
            # SPUR's come.e carry case (needs a helper to carry the body) --
            # not ported yet, see guild_follow.py.
            await ctx.send(f"{name} is unconscious! You can't carry them yet.")
            return False
        if not follow_mode:
            await ctx.send(f"{name} doesn't want to follow..")
            return False

        if kind == 'live':
            # They may have wandered off while the leader was answering.
            if not self._in_room(cand, level, room) or getattr(other, 'active_duel', None) is not None:
                await ctx.send(f"{name} isn't here any more.")
                return False
            other.guild_following = str(leader.id)
            await cand.send([
                f'{leader.name} leads the way -- you fall in behind.',
                '(Move on your own, or type |command|FOLLOW|reset| to switch Guild Follow off, to break away.)',
            ])
        else:
            leader.carried_followers = guild_follow.carried(leader) + [{'id': cand['id'], 'name': name}]

        await ctx.send(f'{name} agrees to follow you..')
        return True
