"""combat/monster_spells.py — Monster spellcasting (SPUR.MISC4.S mon.cst).

Split out from combat/resolution.py: a self-contained trigger+dispatch,
same reasoning as spells/charm.py living apart from the rest of combat --
monster spellcasting is its own small mechanic, not part of the general
hit/damage math resolution.py otherwise handles.

Wires up monsters.json's cast_one_spell ('+') / cast_multiple_spells
('++') flags (monsters.py's flag table), which existed in the data model
but had no behavior anywhere before this.
"""
from __future__ import annotations

import random

from combat.resolution import MonsterAttackResult


def monster_casts_spell(monster: dict, player, spells_used: set) -> MonsterAttackResult | None:
    """Trigger + dispatch for a +/++ flagged monster's spellcasting
    (SPUR.COMBAT.S m.attack lines 226-228 for the trigger roll,
    SPUR.MISC4.S mon.cst lines 16-23 for which spell fires).

    Returns None if nothing triggers this round (caller proceeds with a
    normal swing). spells_used tracks which of 'end'/'end2'/'dest'/
    'dest2' have already fired this encounter -- mutated in place,
    matching source's zs$ (each effect only usable once per fight, twice
    for a ++ monster).

    Endurance/Destroy are usable by any +/++ monster; Teleport is
    ++-only, and only once both Endurance and Destroy have already fired
    this fight (SPUR's own fallback order).
    """
    flags = monster.get('flags', {}) or {}
    is_caster = flags.get('cast_one_spell') or flags.get('cast_multiple_spells')
    if not is_caster:
        return None

    multi = bool(flags.get('cast_multiple_spells'))
    ms    = monster.get('strength') or 5
    name  = monster.get('name', 'The monster')
    xp_level = int(getattr(player, 'xp_level', 1) or 1)

    # Trigger roll (SPUR rnd.10z, simplified to the same 1-10 convention
    # commands/cast.py already uses for the equivalent player-side roll).
    z = random.randint(1, 10)
    triggered = ms < (z + 3) or z > 8
    if multi and z > 6:
        triggered = True
    if not triggered:
        return None

    # Dispatch roll -- a fresh z, per source (mon.cst starts its own
    # rnd.10z rather than reusing the trigger roll).
    z = random.randint(1, 10)

    # Endurance and Destroy each have ONE shared formula in source (a
    # single 'endrnce'/'destroy' label) -- the ++ bonus applies to
    # *every* cast by a multi-caster, not just a "second" one. What
    # varies is only whether a cast is *allowed* at all: base condition
    # first, a more lenient ++-only second chance once the base slot is
    # spent. 'end'/'end2' (and 'dest'/'dest2') are just a 2-slot usage
    # counter -- which marker gets set depends on whether the base slot
    # was already used, not on which guard let this particular cast
    # through. (An earlier version of this function modeled these as two
    # differently-powered branches instead of one shared formula with a
    # shared usage counter -- under-powering a ++ monster's first cast
    # and letting the effects fire out of source's intended order.)
    can_endurance = (
        (z + 5 > ms or z < 3) and 'end' not in spells_used
    ) or (
        multi and (z + 7 > ms) and 'end2' not in spells_used
    )
    if can_endurance:
        spells_used.add('end2' if 'end' in spells_used else 'end')
        heal = 5 * xp_level + (2 * xp_level if multi else 0)
        return MonsterAttackResult(
            hit=False, damage=0, spell_cast='endurance', monster_heal=heal,
            cast_narration=[f'{name} casts an endurance spell, and gains strength!'],
        )

    can_destroy = ('dest' not in spells_used) or (multi and 'dest2' not in spells_used)
    if can_destroy:
        spells_used.add('dest2' if 'dest' in spells_used else 'dest')
        damage = int(z / 2) + 1 + 4 + (2 if multi else 0)
        return MonsterAttackResult(
            hit=True, damage=damage, spell_cast='destroy',
            cast_narration=[f'{name} casts a destroyer spell on you!',
                             f'Zap! You take {damage} hits!'],
        )

    if multi:
        z2 = random.randint(1, 10)
        if (z2 + xp_level + 8 > ms) or z2 == 5:
            return MonsterAttackResult(
                hit=False, damage=0, spell_cast='teleport',
                cast_narration=[f'{name} casts a teleport spell on you!',
                                 'The area fades from view..'],
            )

    # Trigger fired, but every effect this monster can cast is already
    # used up this encounter (or, for a ++ monster, the Teleport roll
    # above just failed). SPUR's own fallback (`goto c.return`, no print
    # statement) exits m.attack entirely without a normal swing -- the
    # attempted cast consumes the monster's whole turn even though
    # nothing visibly happens, rather than falling back to an ordinary
    # attack. spell_cast='wasted' tells engine.py to render the round as
    # silent (no message, no damage, no turn-to-stone check) instead of
    # letting it fall through to a normal swing.
    return MonsterAttackResult(hit=False, damage=0, spell_cast='wasted')
