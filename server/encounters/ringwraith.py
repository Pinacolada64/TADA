"""encounters/ringwraith.py — SPUR.MISC4.S's `wraith`: monster #70's
special cases (already in monsters.json as RINGWRAITH).

SPUR source (rd.mons, `if m=70 gosub wraith:if vw return` -- run before
even the turf-guard/mechanical checks, right at the top of monster load):

    wraith
     vz=1:vw=0:wy$="|.*&~<!51E"
     if mid$(zu$,2,1)="1" ms=ms+(xp*7):wy$=wy$+";":print "(..oh, oh... The ring..)"
     if vk>800 return
     gosub rnd1000z:if (pr=2) or (pr=8) z=z+100
     if z+100 < vk print "The monster ignores your alignment, and attacks!":return
     print 'The Ringwraith recognizes one of his own kind! ...'
     for vw=1 to 2000:next
     if hp<30 hp=30 ... if ps<26 ps=26 ... if pe<26 pe=26 ... if pd<26 pd=26
     ep=ep+25
     zt$="RINGWRAITH VISITED":xx$="EVIL!":gosub news
     print "The shadow flies away.."
     if vk>25 vk=vk-25
     mf=0:mw=0:m$="":wy$="":ms=0:zn=70
     return

Two independent pieces, split the same way turf_guards.py splits mad.gd
from the friendly turf-guard salute:

  - apply_flag_overrides(): the unconditional part -- SPUR hardcodes the
    Ringwraith's flags every encounter regardless of what's in the data
    file (tough/poisonous_attack/experience_drain/appears_unaffected/
    re_animates/evil, quote #51), and adds heavy_armor + a strength bonus
    if the player has the ring on ("(..oh, oh... The ring..)"). Called
    from combat/engine.py's enter_combat() on the CombatSession's own
    per-fight copy of the monster, same as turf_guards.try_captain_spawn
    -- never mutates the shared ctx.server.monsters template.
  - try_recognition_scene(): the honor-gated (vk) friendly "recognizes
    one of his own kind" scene -- skipped outright above 800 honor;
    below that, a roll (Ogre/Orc get a bonus, matching their generally
    evil alignment elsewhere in this port) decides whether the Ringwraith
    attacks anyway or the scene fires: stat floors raised, +25 XP, honor
    drained by 25, and the encounter ends with no fight at all. Called
    from encounters/monster.py's try_monster_encounter(), analogous to
    that module's _try_turf_guard() short-circuit, ahead of the mechanical/
    turf-guard/surprise checks -- matching SPUR's own ordering.
  - try_wraith_stalks(): SPUR.MAIN.S:15 -- travel roll for the Ringwraith
    to spontaneously appear (separate from any room's fixed monster; see
    that function's docstring, since MAIN.S's version of this block is
    tangled up with an unrelated turf-guard-room-spawn roll that isn't
    ported). This is the actual mechanical form of the ring's "THE EVIL
    SENSES YOU MORE CLEARLY!" warning -- wearing it doubles the chance of
    triggering the encounter at all. Called once per move, same call site
    as encounters/meteor.py's try_encounter().

Not ported: SPUR's `gosub news` auto-post to the news board. This port's
NEWS (commands/news.py) is sysop-authored only -- nothing anywhere else
auto-generates a news item from a player action yet, so there's no
existing pipeline to hook into. Flavor-only for now.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

RINGWRAITH_NUMBER = 70

_HONOR_SKIP_THRESHOLD = 800   # SPUR vk>800 -- always attacks above this
_RECOGNITION_RACE_BONUS = {'Ogre', 'Orc'}   # SPUR pr=2/pr=8

_MAX_STALK_LEVEL = 5   # SPUR cl>5 -- never stalks on level 6+ (the space level)
_ONCE_PER_DAY_KEY = 'ringwraith_seen'   # same convention as encounters/meteor.py

_HP_FLOOR  = 30
_STR_FLOOR = 26
_EGY_FLOOR = 26
_DEX_FLOOR = 26
_XP_REWARD = 25
_HONOR_DRAIN = 25


def apply_flag_overrides(monster: dict, player) -> None:
    """SPUR wraith's hardcoded wy$="|.*&~<!51E", plus the ring bonus.
    Mutates *monster* in place -- safe on CombatSession.monster, which is
    already a per-fight copy (see CombatSession.__init__). No-ops unless
    *monster* is the Ringwraith (#70).
    """
    if monster.get('number') != RINGWRAITH_NUMBER:
        return

    from monsters import monster_flags
    new_flags = {flag_name: False for _, flag_name in monster_flags}
    for flag_name in ('tough', 'poisonous_attack', 'experience_drain',
                       'appears_unaffected', 're_animates', 'evil', 'has_quote'):
        new_flags[flag_name] = True
    monster['flags'] = new_flags
    monster['quote_number'] = 51

    from flags import PlayerFlags
    if player.query_flag(PlayerFlags.RING_WORN):
        new_flags['heavy_armor'] = True
        hp = int(monster.get('strength') or monster.get('hit_points') or 5)
        xp_level = int(getattr(player, 'xp_level', 1) or 1)
        new_hp = hp + xp_level * 7
        if 'strength' in monster:
            monster['strength'] = new_hp
        else:
            monster['hit_points'] = new_hp


async def try_recognition_scene(ctx: 'GameContext', monster: dict) -> bool:
    """SPUR wraith's honor-gated friendly scene. Returns True (encounter
    over, no fight) if it fires. No-ops (returns False) unless *monster*
    is the Ringwraith (#70).
    """
    if monster.get('number') != RINGWRAITH_NUMBER:
        return False

    player = ctx.player
    honor = int(getattr(player, 'honor', 1000) or 1000)
    if honor > _HONOR_SKIP_THRESHOLD:
        return False

    race = str(getattr(player, 'char_race', '') or '')
    z = random.randint(0, 999)
    if race in _RECOGNITION_RACE_BONUS:
        z += 100
    if z + 100 < honor:
        await ctx.send('The monster ignores your alignment, and attacks!')
        return False

    await ctx.send([
        'The Ringwraith recognizes one of his own kind! Hot yellow eyes glow',
        'at you from under a black hood for a long second. You feel its evil',
        'strength..',
    ])

    stats = getattr(player, 'stats', None) or {}
    hp = int(getattr(player, 'hit_points', 1) or 1)
    if hp < _HP_FLOOR:
        player.hit_points = _HP_FLOOR
        await ctx.send('(hit points increase)')
    if int(stats.get('Strength', 10)) < _STR_FLOOR:
        stats['Strength'] = _STR_FLOOR
        await ctx.send('(strength increases)')
    if int(stats.get('Energy', 10)) < _EGY_FLOOR:
        stats['Energy'] = _EGY_FLOOR
        await ctx.send('(energy increases)')
    if int(stats.get('Dexterity', 10)) < _DEX_FLOOR:
        stats['Dexterity'] = _DEX_FLOOR
        await ctx.send('(dexterity increases)')
    player.stats = stats

    player.experience = int(getattr(player, 'experience', 0) or 0) + _XP_REWARD
    await ctx.send(f'(+{_XP_REWARD} exp)')

    await ctx.send('The shadow flies away..')
    if honor > _HONOR_DRAIN:
        player.honor = honor - _HONOR_DRAIN

    player.unsaved_changes = True
    return True


def _has_been_seen(player) -> bool:
    return _ONCE_PER_DAY_KEY in (getattr(player, 'once_per_day', None) or [])


def _mark_seen(player) -> None:
    once = getattr(player, 'once_per_day', None)
    if once is None:
        player.once_per_day = once = []
    if _ONCE_PER_DAY_KEY not in once:
        once.append(_ONCE_PER_DAY_KEY)
    player.unsaved_changes = True


async def try_wraith_stalks(ctx: 'GameContext') -> bool:
    """SPUR.MAIN.S:15-21 (the Ringwraith half of that block only -- see
    module docstring for the turf-guard-room-spawn half that isn't
    ported). Call once per move, same site as encounters/meteor.py's
    try_encounter(). Rolls two gates against the player's dungeon level
    (deeper levels are more dangerous), the second one skipped entirely
    if the ring is worn -- SPUR's "THE EVIL SENSES YOU MORE CLEARLY!"
    made mechanical, since it roughly doubles the odds of the whole thing
    firing at all. No-op if the room already has a monster, a fight's
    already underway, this player's already seen it today (SPUR's zn=70
    session cooldown, widened to a day the way encounters/meteor.py's
    once-per-session events already are in this port), or map_level > 5.

    Returns True if the Ringwraith actually appeared (recognition scene
    or a real fight either way) so callers can skip other per-move world
    events this turn, same as a normal monster encounter would.
    """
    player = ctx.player
    if _has_been_seen(player):
        return False

    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    room     = game_map.get_room(level, room_no) if game_map and room_no else None
    if room is None or getattr(room, 'monster', 0):
        return False
    if level > _MAX_STALK_LEVEL:
        return False

    active = getattr(ctx.server, 'active_combats', {}) or {}
    session = active.get(room_no)
    if session is not None and not session._done.is_set():
        return False

    from flags import PlayerFlags
    ring_worn = player.query_flag(PlayerFlags.RING_WORN)

    if random.randint(1, 10) > level:
        return False
    if not ring_worn and random.randint(1, 10) > level:
        return False

    await ctx.send('Something evil stalks...')
    if random.randint(1, 10) != 1:
        return False

    await ctx.send('It is here!')
    _mark_seen(player)

    from monsters import get_monster
    monster = get_monster(getattr(ctx.server, 'monsters', []), RINGWRAITH_NUMBER)
    if monster is None:
        return False

    if await try_recognition_scene(ctx, monster):
        return True

    from combat.engine import enter_combat
    await enter_combat(ctx, monster)
    return True
