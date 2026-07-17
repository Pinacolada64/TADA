"""encounters/monster.py — SPUR.MISC4.S's rd.mons routine: the code right
after the `teleport` label (lines 44-138), plus its "tactical"/"desert"
tail (lines 140-168). Runs once per room entry whenever a live monster is
present (SPUR.MAIN.S travel2: `if m gosub rd.mons`) -- *before* any fight
starts, unlike spells/charm.py's try_charm_join_offer which fires on
*leaving* a room.

Three rolls, in SPUR's own order, each short-circuiting the next:

  1. Surprise (lines 85-96): sized off the monster + player class/race/
     weapon. Can catch the monster off guard -- a bonus on the player's
     first swing if a fight actually starts (SPUR.COMBAT.S:124/143 zs=997,
     matched here by CombatSession.is_surprise -> resolution.py's
     is_surprise param, which already existed but nothing ever set it) --
     or make the monster flee/miss the player outright before any fight
     starts.
  2. Spontaneous charm (lines 98-131, "d.charm"): an INT+WIS+level+
     alignment roll that can make almost any monster join on the spot, no
     potion required -- gated on YY (below), not on the 'charmable' (AC
     flag); the AC flag instead forces an automatic, unconditional join,
     and 'tough' monsters can never succeed via the roll (rd.mons:126 `if not
     instr(".",wy$) zq=1`). 'tough' or 'charmable' monsters skip the
     surprise roll entirely and come straight here (rd.mons:77 `if
     (instr(".",wy$)) or (instr("AC",wy$)) goto d.charm`). Reuses
     player.pending_charm / spells.charm.try_charm_join_offer verbatim --
     SPUR.MAIN.S:192 sends both this and the CHARM POTION case through
     the same `i$="CHARM":gosub lnk.msc5` join-offer flow, so the join
     prompt/honor-penalty/broadcast logic doesn't need porting twice.
  3. Ally tactical positioning / desertion (lines 140-168, "tactical"/
     "desert"): only rolled if neither 1 nor 2 fired. Picks one ally to
     call out a position -- bar/ally_data.py's AllyPosition enum
     (POINT/FLANK/REAR/LURKING/EMPTY) was already defined there but never
     wired to anything until now -- with a chance that ally deserts the
     party outright.

Two small integers on the monster record are easy to conflate and drive
different rolls below -- see programming-notes/spur variables.txt's `ma`
and `yy` entries for the full derivation:
  - MA is the monster's to-hit stat (monsters.json 'to_hit'), also used as
    a size-word index into rd.mons's own flavor-text table (huge...swift).
    Drives the surprise roll's z=10-ma term.
  - YY is a *different* number: an optional leading digit on the monster's
    NAME field in the original data file (e.g. "M.7RATTLESNAKE"), 1-7,
    matching monsters.json's 'size' string (1=huge ... 7=swift; None means
    no digit, i.e. yy=0). Gates the spontaneous-charm roll entirely (yy=0
    skips it -- confirmed real-data quirk: OLD MAN has the AC/charmable
    flag but no leading digit, so it can never be spontaneously charmed)
    and the surprise roll's "whole encounter flees in terror" branch, plus two
    charm-bonus modifiers keyed to an exact value (yy=1 vs Knights, yy=2
    vs Pixies).

Simplifications from source (documented, not silently dropped -- same
convention as spells/charm.py's own docstring):
  - wy$'s ":" (mechanical) flag: source lets mechanical monsters go
    through the ordinary surprise + charm rolls same as anyone (rd.mons
    never actually checks ":" itself -- only 'tough' and 'charmable' skip
    to d.charm, and the roll-success line only excludes 'tough', not
    mechanical). That reads like an unexercised corner case rather than
    intentional design -- no monster in monsters.json is both mechanical
    and charmable, so it may never have come up. This port deliberately
    keeps mechanical monsters out of both rolls entirely instead, for
    consistency with spells/charm.py's CHARM POTION handling (which does
    exclude mechanical monsters, per SPUR.SUB.S:146).
  - Per-ally "caught off guard" per-round to-hit penalty (SPUR's vz/vq)
    isn't modeled, since combat/engine.py's ally swings don't yet track a
    per-round penalty state -- only desertion (a lasting effect) is
    ported.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

# monsters.json 'size' string -> SPUR's yy (the monster-name leading digit),
# inverse of monsters.py's own monster_sizes table (1=huge ... 7=swift).
_YY_FROM_SIZE = {
    'huge': 1, 'large': 2, 'big': 3, 'man_sized': 4,
    'short': 5, 'small': 6, 'swift': 7,
}

_HP_PER_STRENGTH = 2  # matches spells/charm.py's own constant


def _current_room(ctx: 'GameContext'):
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(ctx.player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    return game_map.get_room(level, room_no) if game_map and room_no else None


def _stat(player, stat, default: int = 10) -> int:
    return int((getattr(player, 'stats', None) or {}).get(stat, default))


async def try_monster_encounter(ctx: 'GameContext', *, level: int, room_no: int) -> None:
    """Run the SPUR rd.mons rolls for the monster (if any) just entered.

    Called from Server._move() right after the player's room actually
    changes. No-op if there's no live monster here, it's already dead or
    charmed-away for this player, or a fight is already underway (SPUR
    only ever calls rd.mons on a fresh room entry).
    """
    player = ctx.player
    room = _current_room(ctx)
    monster_no = int(getattr(room, 'monster', 0) or 0) if room else 0
    if not monster_no:
        return
    if (monster_no in getattr(player, 'monsters_killed', [])
            or monster_no in getattr(player, 'charmed_monsters', [])):
        return

    active = getattr(ctx.server, 'active_combats', {}) or {}
    session = active.get(room_no)
    if session is not None and not session._done.is_set():
        return

    from monsters import get_monster
    monster = get_monster(getattr(ctx.server, 'monsters', []), monster_no)
    if monster is None:
        return

    flags = monster.get('flags') or {}
    if flags.get('mechanical'):
        return  # deliberate deviation from source -- see module docstring

    # SPUR.MISC4.S:77 `if (instr(".",wy$)) or (instr("AC",wy$)) goto d.charm`
    # -- 'tough' or 'charmable' monsters skip the surprise roll entirely.
    if not (flags.get('tough') or flags.get('charmable')):
        if await _try_surprise(ctx, monster, monster_no):
            return  # zs=998 this encounter (surprised, possibly fled) -- SPUR:
                     # `if (yy=0) or (zs=998) goto rd.mon2` skips charm/tactical too

    if await _try_spontaneous_charm(ctx, monster, monster_no, level=level, room_no=room_no):
        return

    await _try_ally_tactical(ctx, monster)


async def _try_surprise(ctx: 'GameContext', monster: dict, monster_no: int) -> bool:
    """SPUR.MISC4.S:85-96. Returns True if the player surprised the monster
    at all (zs=998, whether or not it then fled) -- SPUR skips the charm
    and tactical rolls in either case, not just on a flee."""
    from base_classes import PlayerClass, PlayerRace, PlayerStat

    player = ctx.player
    name   = monster.get('name', 'the monster')
    ma     = int(monster.get('to_hit') or 4)  # SPUR ma -- see combat/resolution.py
    xp     = int(getattr(player, 'xp_level', 1) or 1)

    z = (10 - ma) * 2
    z += 2 * xp
    z += _stat(player, PlayerStat.DEX)

    char_class = getattr(player, 'char_class', None)
    char_race  = getattr(player, 'char_race', None)
    if char_class in (PlayerClass.RANGER, PlayerClass.THIEF):
        z += 15
    if char_class == PlayerClass.ASSASSIN:
        z += 7
    if char_race == PlayerRace.PIXIE:
        z += 15
    if char_race == PlayerRace.ELF:
        z += 7

    weapon = getattr(player, 'readied_weapon', None)
    wc = getattr(weapon, 'weapon_class', None) if weapon else None
    wc_str = (wc.value if hasattr(wc, 'value') else str(wc)) if wc else ''
    if wc_str.lower() == 'projectile':
        z += 15

    z = min(z, 50)

    if random.randint(0, 149) >= z:
        return False  # not surprised

    plural = bool((monster.get('flags') or {}).get('multiple_monsters'))
    article = 'some' if plural else 'a'
    size_word = (monster.get('size') or '').replace('_', ' ')
    size_txt = f'{size_word} ' if size_word else ''

    yy = _YY_FROM_SIZE.get(monster.get('size'), 0)
    if yy > 0:
        hp = int(getattr(player, 'hit_points', 10) or 10)
        xp = int(getattr(player, 'xp_level', 1) or 1)
        if random.randint(0, 99) < hp + xp * 2:
            await ctx.send(f'{name} run away screaming!')
            await ctx.send_room(f'{name} run away screaming from {getattr(player, "name", "someone")}!',
                                 exclude_self=True)
            return True

    await ctx.send(f'You surprised {article} {size_txt}{name}!')
    player.pending_surprise = {
        'level':          int(getattr(player, 'map_level', 1) or 1),
        'room_no':        int(getattr(ctx.client, 'room', 0) or 0),
        'monster_number': monster_no,
    }
    return True


async def _try_spontaneous_charm(ctx: 'GameContext', monster: dict, monster_no: int,
                                  *, level: int, room_no: int) -> bool:
    """SPUR.MISC4.S:98-131 "d.charm". Returns True if the monster joined
    (player.pending_charm is now set -- same shape spells/charm.py's
    try_charm_potion produces, so try_charm_join_offer handles the rest)."""
    from base_classes import PlayerClass, PlayerRace, PlayerStat

    player = ctx.player
    flags  = monster.get('flags') or {}

    # SPUR.MISC4.S:100 `if (yy=0) or (zs=998) goto rd.mon2` -- monsters
    # with no leading size digit never get a charm roll at all, no matter
    # what their other flags say (real-data quirk: OLD MAN is 'charmable'
    # but yy=0, so it can never actually be spontaneously charmed).
    yy = _YY_FROM_SIZE.get(monster.get('size'), 0)
    if yy == 0:
        return False

    name = monster.get('name', 'the monster')
    xp   = int(getattr(player, 'xp_level', 1) or 1)
    z    = _stat(player, PlayerStat.INT) + _stat(player, PlayerStat.WIS) + 2 * xp

    char_class = getattr(player, 'char_class', None)
    char_race  = getattr(player, 'char_race', None)
    if char_class == PlayerClass.PALADIN:
        z += 20
    if char_class == PlayerClass.KNIGHT and yy == 1:  # vs. huge monsters
        z += 20
    if char_race == PlayerRace.OGRE:
        z -= 40
    if char_race == PlayerRace.PIXIE and yy == 2:  # vs. large monsters
        z += 40
    if char_race == PlayerRace.ELF:
        z += 10
    if char_race == PlayerRace.ORC:
        z -= 20
    z = min(z, 70)

    honor = int(getattr(player, 'honor', 1000) or 1000)
    evil_aligned_race = char_race in (PlayerRace.OGRE, PlayerRace.ORC)
    good_aligned_race = char_race in (PlayerRace.PIXIE, PlayerRace.ELF)

    # SPUR.MISC4.S:114/121 also do `ms=ms+(xp*5)` here -- a monster-strength
    # boost that would carry into the fight that follows. Not ported: this
    # port's CombatSession recomputes monster strength fresh from the
    # monster dict when a fight starts, with no pending-boost mechanism to
    # thread this through yet.
    if flags.get('evil'):
        if evil_aligned_race:
            z += 10
            if honor > 900:
                await ctx.send('(Who is aghast at your goodly ways.)')
                return False  # too virtuous despite an evil-aligned race -- charm fails
        if good_aligned_race and honor > 700:
            await ctx.send('(Who is aghast at your goodly ways.)')
            return False
        if honor < 900:
            z += (1000 - honor) / 20
        elif honor > 1100:
            z -= (honor - 1000) / 20
    elif flags.get('good'):
        if good_aligned_race:
            z += 10
            if honor < 1100:
                await ctx.send('(Who is aghast at your evil ways.)')
                return False
        if evil_aligned_race and honor < 1300:
            await ctx.send('(Who is aghast at your evil ways.)')
            return False
        if honor > 1100:
            z += (honor - 1000) / 20
        elif honor < 900:
            z -= (1000 - honor) / 20

    # rd.mons:126 `if not instr(".",wy$) zq=1` -- 'tough' monsters can
    # never succeed via the roll, no matter how high z climbs.
    charmed = not flags.get('tough') and random.randint(0, 199) + 10 < z
    # rd.mons:127 Half-Elf + DRAGON always succeeds, tough or not.
    if char_race == PlayerRace.HALF_ELF and 'DRAGON' in name.upper():
        charmed = True
    # rd.mons:128 the 'charmable' (AC flag) forces an automatic join
    # unconditionally -- the only gate it doesn't bypass is the yy=0 check
    # already applied above (an aghast-alignment cancel above returns
    # early, so those DO still block an AC-flagged monster; only the yy=0
    # gate is checked before all of this).
    if flags.get('charmable'):
        charmed = True

    if not charmed:
        return False

    from bar.allies import owned_allies
    if len(owned_allies(player)) >= 3:
        return False  # full party -- SPUR: `if a1>0 if a2>0 if a3>0` skips the offer entirely

    await ctx.send(f'{name} looks at you adoringly...')
    player.pending_charm = {
        'level':          level,
        'room_no':        room_no,
        'monster_number': monster_no,
        'name':           name,
        'strength':       int(monster.get('strength', 0) or 0),
        'to_hit':         int(monster.get('to_hit', 0) or 0),
    }
    return True


async def _try_ally_tactical(ctx: 'GameContext', monster: dict) -> None:
    """SPUR.MISC4.S:140-168 "tactical"/"desert". Only reached when neither
    the surprise nor charm roll fired this encounter."""
    from bar.ally_data import Ally, AllyPosition

    player = ctx.player
    party  = getattr(player, 'party', None)
    if not party:
        return

    allies = [m for m in party if isinstance(m, Ally) and getattr(m, 'hit_points', 0) > 0]
    if not allies:
        return

    ally = random.choice(allies)
    position = random.choice((AllyPosition.POINT, AllyPosition.FLANK, AllyPosition.REAR))
    ally.position = position
    shout = {
        AllyPosition.POINT: 'To the front!',
        AllyPosition.FLANK: 'On the flank!',
        AllyPosition.REAR:  'To the rear!',
    }[position]
    await ctx.send(f"{ally.name} shouts '{shout}'")

    # SPUR desert: gosub rnd.10z:if z<>5 then return -- 1-in-10 chance
    if random.randint(1, 10) != 5:
        return

    from bar.ally_data import AllyStatus
    name = ally.name
    await ctx.send(f'{name} runs away screaming!')
    await ctx.send_room(f"{name} deserts {getattr(player, 'name', 'someone')}'s party!",
                         exclude_self=True)
    ally.status = AllyStatus.FREE
    ally.owner = None
    ally.position = AllyPosition.EMPTY
    party.remove(ally)
    player.unsaved_changes = True
