#!/bin/env python3
"""
stats command implementation.

Shows player statustics, quests, and achievements.
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from base_classes import PlayerMoneyTypes
from commands.base_command import Command, CommandResult, HelpCategory
from commands.command_processor import command

import net_common

from commands.help import BaseHelpText
from commands.utils import get_player_from_context
from flags import PlayerFlags
from terminal_context import GameContext


class StatsHelp(BaseHelpText):
    name = 'stats'
    aliases = []

    def __init__(self):
        super().__init__()
        self.category = HelpCategory.COMMUNICATION
        self.summary = 'List current player\'s stats'
        self.description = (
            "List player's stats with optional breakdown into sections."
            "Admins may see additional details like extended flags."
        )
        self.usage = [
            ("stat", "Show statistics of connected player"),
            ("stat <player>", "(Optional) View statistics for <player>")
        ]
        self.examples = [
            ("stat", "List stats for currently connected player"),
        ]

@command(name='stat', category=HelpCategory.GENERAL,
         summary='List player\'s stats')
class StatCommand(BaseCommand):
    """List player's stats
    """
    async def execute(self, reader, writer, player) -> CommandResult:
        try:
            # Determine if caller is admin
            caller = player.query_flag(PlayerFlags.ADMIN)
            # show player info: map level, room, stats, dwarf alive
            silver_total = sum(player.silver.values())
            combinations = ', '.join(player.combinations) if player.combinations else 'None'
            _ = f"""
            {'Name:'.rjust(20)} {player.name}
            {'Age:'.rjust(20)} {player.age}
            {'Gender:'.rjust(20)} {self.gender.title()}
            {'Birthday:'.rjust(20)} {player.birthday}
            {'Silver: In hand:'.rjust(20)} {player.silver[PlayerMoneyTypes.IN_HAND]: >12,}
            {'In bank:'.rjust(20)} {player.silver[PlayerMoneyTypes.IN_BANK]: >12,}
            {'In bar :'.rjust(20)} {player.silver[PlayerMoneyTypes.IN_BAR]: >12,}
            {'Total:'.rjust(20)} {player.silver_total: >12,}

            {'Guild:'.rjust(20)} {self.guild.title()}
            {'Monster kills:'.rjust(20)} {self.monster_kills}
            {'Experience points:'.rjust(20)} {self.experience_points}
            {'Map level:'.rjust(20)} {self.map_level}
            {'Hit points:'.rjust(20)} {self.hit_points}
            
            {'Combinations:'.rjust(20)} {combinations}

            {'Last played:'.rjust(20)} {self.last_play_date}
            """

            # Placeholder for actual stats retrieval logic
            # This would typically involve querying the player's stats from the database or in-memory structures

            return CommandResult(success=True, message=lines, data={'type': 'stats', 'count': len(lines)})


@command(category=HelpCategory.GENERAL,
         summary='List currently online players')
class StatsCommand(Command):
    """List player's stats
    """

    async def execute(self, ctx: GameContext, args: List[str]) -> CommandResult:
        player = ctx.player
        # Determine if caller is admin
        caller = context.get('client') or context.get('caller') or None
        player = get_player_from_context(context, caller)
        is_admin = False
        try:
            is_admin = bool(getattr(caller, 'is_admin', False) or context.get('is_admin', False) or context.get('user_level') == 'admin')
        except Exception:
            is_admin = False

        # show player info: map level, room, stats, dwarf alive
        lines = [f"{'Player':<20} {'Level':<5} {'Room':<20}", "Stats"]

        """
status
 setint(1)
 print \n1$"'s Current Stats: (BHR="hp+(xp*2)+((pe+pd+ps)/2)+((sh+ar)/4)")"\
 g1=gh:g2=gl:gosub prt.gold
 print "Gold - In Hand:"gd$
 g1=bh:g2=bl:gosub prt.gold
 print "       In Bank:"gd$
 print \"Experience Pts :"right$("   "+str$(ep),5)"   Hit Points :"right$("   "+str$(hp),3)
 print "Monsters Kills :"right$("   "+str$(mk),5)" Player Level :"right$("   "+str$(xp),3)
 a=ps*4:print \"Strength: "right$("  "+str$(ps),2)right$("    "+str$(a),4)"%   ";
 a=pt*4:print "Const'n  :"right$("  "+str$(pt),2)right$("    "+str$(a),4)"%"
 a=pi*4:print "Intel   : "right$("  "+str$(pi),2)right$("    "+str$(a),4)"%   ";
 a=pd*4:print "Dexterity:"right$("  "+str$(pd),2)right$("    "+str$(a),4)"%"
 a=pw*4:print "Wisdom  : "right$("  "+str$(pw),2)right$("    "+str$(a),4)"%   ";
 a=pe*4:print "Energy   :"right$("  "+str$(pe),2)right$("    "+str$(a),4)"%"
 print \"Shield  :    "right$("  "+str$(sh),3)"%   ";
 print "Armor    :   "right$("  "+str$(ar),3)"%"
 if instr(left$(zu$,1),"BC") i$="YES":else i$="NO"
 a=1+xp:if pc=4 a=a*2
 print "Shield skill: "a", Formal training- "i$
 i$="Wizard  Druid   Fighter Paladin Ranger  Thief   Archer  AssassinKnight  "
 print \"Class : "mid$(i$,pc*8-7,8);
 i$="Human   Ogre    Pixie   Elf     Hobbit  Gnome   Dwarf   Orc     Half-Elf"
 print " Race: ";mid$(i$,pr*8-7,8)
 i$="Neutral":if (pr=2) or (pr=8) i$="Bad"
 if (pr=3) or (pr=4) i$="Good"
 print "Natural Alignment: '"i$"'.";
 i$="Evil":if vk>399 i$="Bad":if vk>799 i$="Neutral"
 if vk>1200 i$="Good":if vk>1600 i$="Saintly"
 print " Current alignment: "i$" ("vk" Honor points)"
 if vv<3 goto no.guild
 print \"GUILD FOLLOWER? ";
 if mid$(zu$,10,1)="1" print "YES":else print "NO"
no.guild
 if mid$(zu$,3,1)="1" print \"POISONED!":else print \"Not poisoned"
 if mid$(zu$,4,1)="1" print "DISEASED!":else print "Not diseased"
 if mid$(zu$,2,1)="1" print "Ring worn.."
 if mid$(zu$,6,1)="1" print "Gauntlets worn.."
 i$=mid$(zu$,8,1):zs=instr("076,",xi$):zr=instr("076,",ai$)
 if i$="1" print "Amulet of life -  ENERGIZED!"
 if i$="0" then if zs+zr>0 print "[][] AMULET OF LIFE NOT ENERGIZED! [][]":if zr>0 print "(Your ally carries it!)"
 if instr(mid$(zu$,7,1),"23") print "Wizard's Glow spell active!"
 print \"King of the Wraiths : ";
 if instr(mid$(zu$,7,1),"12") print "Dead..":else print "Alive.."
 print "SPUR : ";:if (sr) print "Alive!":else print "Dead..."
 g1=dh:g2=dl:gosub prt.gold
 print "Dwarf: ";:if (df) print "Alive!  ["gd$" gold]":else print "Dead..."
 print "Tut's Treasure: ";:if mid$(zu$,9,1)="2" print "Looted..":else print "Somewhere.."
 ex=clock(1)-ew:ex=ev-ex:if ex<0 ex=0
 print \"Hourglass: "(ex/60)" mins."
 return
;
        """
        return CommandResult.ok()
