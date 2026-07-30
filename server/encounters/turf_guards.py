"""encounters/turf_guards.py — SPUR.COMBAT.S's `mad.gd`: a surprised Guild
turf guard calls for backup.

SPUR source:
  - encounters/monster.py's _try_turf_guard() already ports the friendly
    half of monster #65/66/67 (FIST/SWORD/CLAW's turf guard, see that
    module's _TURF_GUARD_NUMBERS -- duplicated below since that constant
    is that module's own private convention, not meant to be imported):
    a guild member who meets their own guard gets saluted, not attacked.
  - A non-member can still surprise-attack the guard (encounters/
    monster.py's _try_surprise(), SPUR.MISC4.S:85-96, zs=998 -> zs=997
    for the rest of the fight). SPUR.COMBAT.S's m.attack (~line 225),
    run every round the monster swings back:
        if zs=997 print m$" "zz$" FURIOUS!"
        if (mw=65) or (mw=66) or (mw=67) then if not instr("GUARDS",m$)
            gosub mad.gd
    -- i.e. a surprised monster is furious every round, and the very
    first time that happens against a turf guard specifically, it calls
    for backup.
  - mad.gd itself (SPUR.COMBAT.S:406):
        gosub rnd.10z:z=z/3+2:ms=ms+((ms/2)*z)
        m$="THE "+str$(z+1)+" GUARDS":wy$="|<]>"
        print "The guard blows on a whistle, and "z" more guards come
        running!"..."They are not amused either, by your treachery.."
    rolls 2-5 reinforcements (d10 // 3 + 2), boosts the guard's strength
    by half again per reinforcement, renames it "THE {z+1} GUARDS", and
    replaces its flags outright with |<]> (re_animates, double_attacks,
    chance_find_gold) -- the merged squad, not additive with whatever
    flags the lone guard had. Guarded by `if not instr("GUARDS",m$)` so
    it only ever fires once per fight -- ported here as a name check for
    the same reason.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

# encounters/monster.py's _TURF_GUARD_NUMBERS (FIST/SWORD/CLAW), duplicated
# here rather than imported -- that module's own private convention.
_GUARD_MONSTER_NUMBERS = (65, 66, 67)


async def try_call_reinforcements(ctx: 'GameContext', monster: dict) -> bool:
    """SPUR.COMBAT.S mad.gd. No-ops unless *monster* is one of the three
    Guild turf guards that hasn't already called for backup this fight.
    Mutates *monster* in place -- safe to call with CombatSession.monster,
    which is already a per-fight copy (see CombatSession.__init__).
    Returns True the one time reinforcements actually arrive.
    """
    if monster.get('number') not in _GUARD_MONSTER_NUMBERS:
        return False
    if 'GUARDS' in monster.get('name', '').upper():
        return False  # already reinforced this fight

    z = random.randint(1, 10) // 3 + 2
    hp = int(monster.get('strength') or monster.get('hit_points') or 5)
    new_hp = hp + (hp // 2) * z
    if 'strength' in monster:
        monster['strength'] = new_hp
    else:
        monster['hit_points'] = new_hp
    monster['name'] = f'THE {z + 1} GUARDS'

    from monsters import monster_flags
    new_flags = {flag_name: False for _, flag_name in monster_flags}
    for flag_name in ('re_animates', 'double_attacks', 'chance_find_gold'):
        new_flags[flag_name] = True
    monster['flags'] = new_flags

    await ctx.send(f'The guard blows on a whistle, and {z} more guards come running!')
    await ctx.send('They are not amused by your treachery either...')
    return True
