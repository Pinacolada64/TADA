"""encounters/turf_guards.py — SPUR.MISC4.S/SPUR.COMBAT.S's Guild turf guard
special cases: a guard occasionally spawns as its guild's captain, and a
surprised guard calls for backup.

SPUR source:
  - encounters/monster.py's _try_turf_guard() already ports the friendly
    half of monster #65/66/67 (FIST/SWORD/CLAW's turf guard, see that
    module's _TURF_GUARD_NUMBERS -- duplicated below since that constant
    is that module's own private convention, not meant to be imported):
    a guild member who meets their own guard gets saluted, not attacked.
  - Before that salute check even runs, rd.mons's "claw" label
    (SPUR.MISC4.S:69) rolls a 20% chance for the guard to be a captain
    instead of a rank-and-file guard:
        if m>64 then if m<68 zx$=rnd$:if random(100)/20=3
            m$="CAPTAIN!"+mid$(m$,6):ms=ms+(xp*3):wy$="|;>]"
    (`random(100)/20=3` is BASIC integer division -- true for the 20-of-100
    range 60-79.) mid$(m$,6) drops the leading "GUARD" word but keeps the
    guild's ASCII-art tag (e.g. "GUARD ==[]" -> "CAPTAIN! ==[]"), ms gains
    +3 strength per player level, and wy$ is reassigned outright to
    "|;>]" -- light_armor/chance_find_gold/double_attacks (';'/'>'/']',
    '|' isn't a real flag character) -- replacing the base guard's
    re_animates the same way mad.gd's reinforcement squad replaces flags
    outright rather than adding to them. See try_captain_spawn() below.
    SPUR rolls this at room-entry time (rd.mons), before any fight starts,
    and the result rides along in the m$/ms/wy$ BASIC variables into
    SPUR.COMBAT.S if a fight actually happens. This port has no per-
    player-safe way to persist a room-entry roll onto a shared monster
    template that multiple players might see differently (unlike
    encounters/monster.py's _try_surprise, which is inherently a solo,
    one-player-at-a-time roll stored on player.pending_surprise) -- so
    it's rolled instead in combat/engine.py's enter_combat(), on the
    CombatSession's own per-fight copy of the monster, at the moment a
    fight actually starts. Functionally equivalent for SPUR's original
    single-player-driving-events assumption.
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
    the same reason. This can stack with a captain spawn (captain rolls
    first, at combat start; reinforcements can still arrive later mid-
    fight and overwrite the captain's name/flags/strength baseline in
    turn), matching how the two independent SPUR rolls can both fire
    against the same guard.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

# encounters/monster.py's _TURF_GUARD_NUMBERS (FIST/SWORD/CLAW), duplicated
# here rather than imported -- that module's own private convention.
_GUARD_MONSTER_NUMBERS = (65, 66, 67)

# SPUR.MISC4.S:69 `random(100)/20=3` -- BASIC integer division, true for the
# 20-of-100 range 60-79.
_CAPTAIN_CHANCE = 0.20

# "GUARD " is always exactly 5 characters in monsters.json (see
# _GUARD_MONSTER_NUMBERS' three records) -- mid$(m$,6) drops just that word.
_GUARD_PREFIX_LEN = 5


def try_captain_spawn(monster: dict, xp_level: int) -> bool:
    """SPUR.MISC4.S:69 (rd.mons "claw" label). No-ops unless *monster* is one
    of the three Guild turf guards. Mutates *monster* in place -- safe to
    call with CombatSession.monster, which is already a per-fight copy (see
    CombatSession.__init__). Returns True the roll succeeds.
    """
    if monster.get('number') not in _GUARD_MONSTER_NUMBERS:
        return False
    if random.random() >= _CAPTAIN_CHANCE:
        return False

    name = monster.get('name', '')
    monster['name'] = 'CAPTAIN!' + name[_GUARD_PREFIX_LEN:]

    hp = int(monster.get('strength') or monster.get('hit_points') or 5)
    new_hp = hp + xp_level * 3
    if 'strength' in monster:
        monster['strength'] = new_hp
    else:
        monster['hit_points'] = new_hp

    from monsters import monster_flags
    new_flags = {flag_name: False for _, flag_name in monster_flags}
    for flag_name in ('light_armor', 'chance_find_gold', 'double_attacks'):
        new_flags[flag_name] = True
    monster['flags'] = new_flags

    return True


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
