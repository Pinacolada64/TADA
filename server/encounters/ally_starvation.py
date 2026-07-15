"""encounters/ally_starvation.py — a weakened, owned ally dies (or, if
divine, leaves) from lack of nourishment.

SPUR source: SPUR.MISC6.S's `dead.al`/`dead.al2`/`fre.ally` labels.
Part of the same random-event dispatcher as encounters/little_girl.py,
encounters/meteor.py, and encounters/djinn_sighting.py -- see
little_girl.py's docstring for why this rolls its own flat composite
share instead of a shared dispatcher for now. (The dispatcher's sibling
sub-event, an ally finding gold / SPUR's `al.find`, already existed as
ally_events.try_ally_find_gold() before this package did -- not
duplicated here.)

  dead.al
   x=0:i$="*"
   if a1>0 if a1<8 i$=d1$:d1$="*":a1=0:x=h1:h1=0:goto dead.al2
   if a2>0 if a2<8 i$=d2$:d2$="*":a2=0:x=h2:h2=0:goto dead.al2
   if a3>0 if a2<8 i$=d3$:d3$="*":a3=0:x=h3:h3=0:goto dead.al2
   return
  dead.al2
   if i$="*" return
   print \"The weakened "i$" stumbles and falls!"
   gosub delay
   if (a1+a2+a3)<1 then ai=0:ai$=""
   print \\\\i$" is dead! (wait..)"
   dy$=dx$+"battle.log":create dy$:open #1,"battle.log":append #1
   print #1, left$(date$,6)yr$" "time$"-LOSS OF FACE!"
   print #1, i$" died in "ww$","
   print #1, "from lack of nourishment while in"
   print #1, "service to "n1$"..."
   print #1,"[]=-=-=-=-=-=-=[ LOS ]=-=-=-=-=-=-=[]":close
   if vk>20 vk=vk-20:print "You feel less honorable"
   if pw>5 pw=pw-5:print "You feel foolish"
   if pi>5 pi=pi-5:print "You feel dumb"
  fre.ally
   if x=0 return
   dy$=dx$+"allies":open #1,dy$
   position #1,26,x
   print #1,1:close:return

Unlike every other encounter in this package, the original has NO
water/vacuum ("@@") gate and NO once-per-session gate on this label --
it can fire repeatedly, every move, for as long as a qualifying
weakened ally exists. This port follows suit: no _ONCE_PER_DAY_KEY, no
room-safety check.

"Weakened" means 0 < strength < 8 (SPUR: `a1<8`) -- a narrower band
than ally_events.py's existing try_hungry_ally() hunger threshold
(`< 11`), and a separate mechanic (that one intercepts eating/drinking;
this one is a pure random tick). SPUR checks ally slots in forward
order (a1, then a2, then a3) -- this port's allies are a plain list
rather than fixed slots, so the first qualifying owned ally in party
order stands in for "whichever slot is checked first".

God/goddess distinction: taken from the SKIP branch, which this
master-derived label doesn't have --

  dead.al2 (skip)
   ...
   if not instr(">",i$) a$="The weakened "+lu$+" stumbles and falls!"
   if instr(">",i$) a$=lu$+" looks annoyed, and flies away!"
   ...
   if instr(">",i$) goto god.lv
   print #1, lu$" DIED IN "ww$","
   ...
  god.lv
   print #1, lu$" GREW UNHAPPY WITH "n1$","
   print #1, "AND LEFT!"

Skip marks god/goddess allies with a ">"/"+" sigil in their display
name (see cln.ally) and lets them desert instead of dying. This port's
Ally dataclass already carries AllyFlags.GOD/AllyFlags.GODDESS
(currently unused anywhere else), so the same distinction is cheap to
implement directly off the flag instead of a name sigil -- used here
even though the module is otherwise ported from master, since it's a
strict improvement and the flags exist for exactly this.

Stat penalties use MASTER's numbers (Honor -20, Wisdom -5, Intelligence
-5), not skip's harsher Honor -25 -- same "master is the default,
divergence noted" treatment as meteor.py's dodge numbers.

Not from SPUR: ELITE allies (AllyFlags.ELITE) never die or desert here,
just a flavor line ("looks gaunt, but grits ITS teeth and endures").
Neither branch's dead.al checks ELITE at all -- this extends the
immunity ally_events.py's try_hungry_ally() already grants elites
against hunger complaints (SPUR: ``instr("!",zt$)``) to this related
starvation-death mechanic, for consistency.
"""
from __future__ import annotations

import datetime
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

# SPUR.MAIN.S:239 (2% world-event roll) x SPUR.MISC6.S's dead.al slice
# (master: z<60 after the z<45 al.find check, i.e. a 15%-wide band) =
# 0.3% composite chance per move.
_ENCOUNTER_CHANCE_PCT = 0.3

_WEAKENED_STRENGTH_MAX = 8  # SPUR: 0 < strength < 8

_HONOR_PENALTY = 20
_HONOR_FLOOR   = 20  # SPUR: `if vk>20 vk=vk-20`
_WISDOM_PENALTY = 5
_WISDOM_FLOOR   = 5
_INTELLIGENCE_PENALTY = 5
_INTELLIGENCE_FLOOR   = 5


def _append_battle_log(entry: str) -> None:
    """Duplicated rather than shared, matching this port's own
    convention for the same helper (street/allies_guild.py,
    bar/zelda.py, combat/engine.py, victory.py, encounters/dwarf.py)."""
    try:
        import net_common
        base = getattr(net_common, 'run_server_dir', None)
    except Exception:
        base = None
    path = os.path.join(str(base or './run/server'), 'battle.log')
    try:
        with open(path, 'a') as fh:
            stamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
            fh.write(f'[{stamp}] {entry}\n')
    except OSError:
        pass


def _weakened_ally(player):
    from bar.allies import owned_allies
    for ally in owned_allies(player):
        strength = int(getattr(ally, 'strength', 0) or 0)
        if 0 < strength < _WEAKENED_STRENGTH_MAX:
            return ally
    return None


def _is_divine(ally) -> bool:
    from bar.ally_data import AllyFlags
    flags = getattr(ally, 'flags', None) or []
    return AllyFlags.GOD in flags or AllyFlags.GODDESS in flags


def _is_elite(ally) -> bool:
    from bar.ally_data import AllyFlags
    flags = getattr(ally, 'flags', None) or []
    return AllyFlags.ELITE in flags


async def try_encounter(ctx: 'GameContext') -> None:
    import random

    player = ctx.player
    ally = _weakened_ally(player)
    if ally is None:
        return

    if random.uniform(0, 100) > _ENCOUNTER_CHANCE_PCT:
        return

    from bar.allies import owned_allies
    from bar.ally_data import AllyStatus
    from ally_events import _free_ally_in_roster

    name = getattr(player, 'name', 'Someone')

    # Not from SPUR: dead.al has no ELITE check at all in either branch,
    # but ally_events.py's try_hungry_ally() already treats ELITE allies
    # as immune to hunger complaints ("instr('!',zt$)" in the original).
    # Extending that same immunity here so an elite ally never starves to
    # death (or deserts) is consistent with that established precedent.
    if _is_elite(ally):
        from tada_utilities import get_pronoun, PronounType
        possessive = get_pronoun(ally, PronounType.POSSESSIVE_ADJECTIVE)
        await ctx.send([
            '', f'{ally.name} looks gaunt, but grits {possessive} teeth and endures.',
        ])
        await ctx.send_room(
            f"{name}'s ally, {ally.name}, looks gaunt but endures without complaint.",
            exclude_self=True,
        )
        return

    divine = _is_divine(ally)

    if divine:
        await ctx.send(['', f'{ally.name} looks annoyed, and flies away!'])
        player.party.remove(ally)
        ally.status = AllyStatus.FREE
        ally.owner  = None
        _free_ally_in_roster(ally.name, AllyStatus.FREE, None)
        await ctx.send_room(
            f"{name}'s ally, {ally.name}, looks annoyed, and flies away!",
            exclude_self=True,
        )
    else:
        await ctx.send(['', f'The weakened {ally.name} stumbles and falls!'])
        await ctx.send(f'{ally.name} is dead! (wait..)')
        player.party.remove(ally)
        ally.status = AllyStatus.DEAD
        ally.owner  = None
        _free_ally_in_roster(ally.name, AllyStatus.DEAD, None)
        await ctx.send_room(
            f"{name}'s ally, the weakened {ally.name}, stumbles, falls, and dies.",
            exclude_self=True,
        )

    player.unsaved_changes = True

    room_name = getattr(ctx.server, 'game_map', None)
    room = None
    if room_name is not None:
        level = int(getattr(player, 'map_level', 1) or 1)
        room_no = int(getattr(ctx.client, 'room', 0) or 0)
        rooms = room_name.levels.get(level) if hasattr(room_name, 'levels') else None
        room = rooms.get(room_no) if rooms else None
    where = getattr(room, 'name', 'the wilderness')

    if divine:
        _append_battle_log(f'{ally.name} grew unhappy with {name}, and left!')
    else:
        _append_battle_log(
            f'{ally.name} died in {where}, from lack of nourishment while in service to {name}...'
        )

    honor = int(getattr(player, 'honor', 0) or 0)
    if honor > _HONOR_FLOOR:
        player.honor = honor - _HONOR_PENALTY
        await ctx.send('You feel less honorable')

    wisdom = int(player.stats.get('Wisdom', 0) or 0)
    if wisdom > _WISDOM_FLOOR:
        player.stats['Wisdom'] = wisdom - _WISDOM_PENALTY
        await ctx.send('You feel foolish')

    intelligence = int(player.stats.get('Intelligence', 0) or 0)
    if intelligence > _INTELLIGENCE_FLOOR:
        player.stats['Intelligence'] = intelligence - _INTELLIGENCE_PENALTY
        await ctx.send('You feel dumb')
