"""encounters/little_girl.py — the "little girl" random encounter.

SPUR source: SPUR.MISC6.S's `girl`/`give`/`drop.itm`/`girl.m1`/`girl.m`/
`girl.sad` labels, gated by the `*gi` token in `ys$` (see TODO.md's
"7/15/26" once-per-session flag inventory).

Trigger chain (`SPUR.MAIN.S:239`, `SPUR.MISC6.S:135-159`): on any move
into a room with no monster already present, a 2% roll
(`rnd.100a`, `a=50` or `a=51`) fires a "random world event," which then
rolls again (d100) across six sub-events -- Galadriel (15%), Meteor
(15%), an ally's death (15%), an ally finding gold (15%), The Enforcer
(20%), and this girl (the remaining 20%, z>=80). Only Galadriel (quest
#8, quests/README.md) and this encounter are implemented in this port so
far -- the other four are documented but unbuilt (TODO.md). Rather than
build the full six-way dispatcher now, this module rolls directly for
its own 20%-of-2% = 0.4% composite share; wiring in the other four later
means replacing this flat roll with a real dispatcher, not touching this
module's own encounter logic.

She approaches with a sob story (poor, sick grandmother) and offers
three choices:
  G)ive  — hand over an item (some refused); rewards a stat top-up if the
           player is battered, +5 Honor (capped 2000), and a random hint
           from little_girl_hints.json (SPUR-data/LITTLE.GIRL.TXT).
  I)gnore — 50% chance she's actually EVILYNN in disguise and attacks
            anyway; otherwise she runs off crying (-2 INT, -3 WIS).
  A)ttack — she's always EVILYNN in disguise; Honor penalty (worse for
            Knights, who should know better) then combat.

Once-per-session gate uses player.once_per_day (existing field, not yet
cleared on date rollover -- see TODO.md's daily-reset entry) rather than
a new parallel per-player list.

Arrival flavor text ("A little boat pulls alongside.."/"A little
spacesuit pulls along side..") only shows in water/vacuum-flagged rooms;
checked against both master and the skip branch's SPUR.MISC6.S -- master
prints the spacesuit line unconditionally on any level 6+ encounter, even
in a bone-dry hallway, which reads like a bug skip fixed by gating the
whole line behind the water/vacuum ("@@") room flag and only choosing
spacesuit-vs-boat wording once inside that condition. This module follows
skip's version.
"""
from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)

MONSTER_NUMBER = 106  # monsters.json "EVILYNN"

_HINTS_FILE = Path(__file__).resolve().parent.parent / 'little_girl_hints.json'

_ONCE_PER_DAY_KEY = 'little_girl_seen'

# SPUR.MAIN.S:239 (2% world-event roll) x SPUR.MISC6.S's girl slice
# (z>=80 out of a d100, i.e. 20%) = 0.4% composite chance per move.
_ENCOUNTER_CHANCE_PCT = 0.4

_RING_ITEM_ID = 67   # "ring" -- refused if currently worn (PlayerFlags.RING_WORN)
_REFUSED_ITEM_IDS = {73, 76}  # Crown of Midas, Amulet of Life -- "the girl refuses to hold it!"

_HONOR_GIVE_BONUS   = 5
_HONOR_CAP          = 2000
_HONOR_ATTACK_PENALTY        = 10
_HONOR_ATTACK_PENALTY_KNIGHT = 15

_IGNORE_ATTACK_CHANCE_PCT = 50  # SPUR: rnd.10z, z>5 out of 1-10


def load_hints() -> list[str]:
    try:
        if _HINTS_FILE.exists():
            return json.loads(_HINTS_FILE.read_text())
    except Exception:
        log.exception('Failed to load little_girl_hints file %s', _HINTS_FILE)
    return []


def _has_been_seen(player) -> bool:
    return _ONCE_PER_DAY_KEY in (getattr(player, 'once_per_day', None) or [])


def _mark_seen(player) -> None:
    once = getattr(player, 'once_per_day', None)
    if once is None:
        player.once_per_day = once = []
    if _ONCE_PER_DAY_KEY not in once:
        once.append(_ONCE_PER_DAY_KEY)
    player.unsaved_changes = True


def _current_room(ctx: 'GameContext'):
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(ctx.player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    return game_map.get_room(level, room_no) if game_map and room_no else None


async def try_encounter(ctx: 'GameContext') -> None:
    """Call on every player move (mirrors wild_horse_events.py's
    try_wandering_horse_encounter() call site). No-op if this player has
    already met her this session, the room already has a monster in it,
    or the roll fails."""
    player = ctx.player
    if _has_been_seen(player):
        return

    room = _current_room(ctx)
    if room is None or getattr(room, 'monster', 0):
        return

    if random.uniform(0, 100) > _ENCOUNTER_CHANCE_PCT:
        return

    _mark_seen(player)

    level = int(getattr(player, 'map_level', 1) or 1)
    lines = ['']

    # Arrival flavor -- SPUR.MISC6.S's "girl" label. Using the skip
    # branch's cleaner version here (master prints the spacesuit line
    # unconditionally on level 6+ even in an ordinary dry room, which
    # looks like a bug skip fixed): only shown in water/vacuum rooms at
    # all, spacesuit wording overriding the boat default once level > 5.
    room_flags = getattr(room, 'flags', None) or []
    if 'water' in room_flags or 'water_with_rocks' in room_flags:
        if level > 5:
            lines.append('A little spacesuit pulls along side, retro-rockets firing.')
        else:
            lines.append('A little boat pulls alongside you..')

    lines += [
        'A little girl approaches you. She is quite skinny and very poor looking..',
        '"Oh please, please, kind person. My grandmother is very sick, and I don\'t',
        'know what to do! Won\'t you please give something that I can pawn so I can',
        'buy her the medicine she needs?"',
    ]
    if level > 5:
        lines.append('\'Now, how did SHE get here?\' you wonder to yourself..')
    await ctx.send(lines)

    name = getattr(player, 'name', 'Someone')
    await ctx.send_room(f'A little girl approaches {name}.', exclude_self=True)

    while True:
        raw = await ctx.prompt('G)ive, I)gnore, A)ttack')
        choice = (raw or '').strip().upper()[:1]
        if choice == 'G':
            await _handle_give(ctx)
            return
        if choice == 'I':
            await _handle_ignore(ctx)
            return
        if choice == 'A':
            await _handle_attack(ctx)
            return
        await ctx.send('Please choose G)ive, I)gnore, or A)ttack.')


async def _reveal_and_attack(ctx: 'GameContext') -> None:
    await ctx.send([
        'Suddenly, the girl seems to get bigger!!!!!!!!!!',
        '\'NOW YOU DIE!!\'',
    ])
    name = getattr(ctx.player, 'name', 'Someone')
    await ctx.send_room(f'The little girl suddenly grows monstrous before {name}!', exclude_self=True)

    from monsters import get_monster
    monsters = getattr(ctx.server, 'monsters', []) or []
    monster  = get_monster(monsters, MONSTER_NUMBER)
    if monster is None:
        log.error('EVILYNN monster (#%d) not found -- skipping combat', MONSTER_NUMBER)
        return
    from combat import enter_combat
    await enter_combat(ctx, monster)


async def _handle_attack(ctx: 'GameContext') -> None:
    from base_classes import PlayerClass

    player = ctx.player
    penalty = (_HONOR_ATTACK_PENALTY_KNIGHT if getattr(player, 'char_class', None) == PlayerClass.KNIGHT
               else _HONOR_ATTACK_PENALTY)
    if player.honor > penalty:
        player.honor -= penalty
        player.unsaved_changes = True

    await _reveal_and_attack(ctx)


async def _handle_ignore(ctx: 'GameContext') -> None:
    player = ctx.player
    if random.randint(1, 10) > 5:
        await _reveal_and_attack(ctx)
        return

    await ctx.send('The poor little girl runs away crying..')
    name = getattr(player, 'name', 'Someone')
    await ctx.send_room(f'The little girl runs away crying after {name} ignores her.', exclude_self=True)

    stats = getattr(player, 'stats', None) or {}
    pi = int(stats.get('Intelligence', 10))
    pw = int(stats.get('Wisdom', 10))
    dumber  = pi > 3
    foolish = pw > 4
    if dumber:
        stats['Intelligence'] = pi - 2
    if foolish:
        stats['Wisdom'] = pw - 3
    player.stats = stats
    player.unsaved_changes = True
    if dumber:
        await ctx.send('(You feel a bit dumber)')
    if foolish:
        await ctx.send('(you feel more foolish)')


async def _handle_give(ctx: 'GameContext') -> None:
    player = ctx.player
    await ctx.send('The girl peers in your sack hopefully..')

    inventory = getattr(player, 'inventory', None)
    entries = list(inventory.entries()) if inventory is not None else []
    if not entries:
        await ctx.send('No Items!')
        return

    lines = ['You are carrying:', '']
    for i, entry in enumerate(entries, 1):
        lines.append(f'  {i:>2}. {getattr(entry.item, "name", "?")}')
    await ctx.send(lines)

    raw = await ctx.prompt(f'Give which item? (1-{len(entries)}, Enter to cancel)')
    if not raw or not raw.strip():
        return
    try:
        idx = int(raw.strip()) - 1
        if not (0 <= idx < len(entries)):
            raise ValueError
    except ValueError:
        await ctx.send('Invalid selection.')
        return

    entry   = entries[idx]
    item_id = getattr(entry.item, 'id_number', None)

    from flags import PlayerFlags
    if item_id == _RING_ITEM_ID and player.query_flag(PlayerFlags.RING_WORN):
        await ctx.send("Can't, you are USEing it!")
        return
    if item_id in _REFUSED_ITEM_IDS:
        await ctx.send('The girl refuses to hold it!')
        return

    inventory.remove(entry.item)
    player.unsaved_changes = True
    await ctx.send('The little girl takes it.. \'OH THANK YOU!!\'')
    from tada_utilities import PronounType, get_pronoun
    name = getattr(player, 'name', 'Someone')
    objective = get_pronoun(player, PronounType.OBJECTIVE)
    await ctx.send_room(f'The little girl takes something from {name} and thanks {objective} warmly.', exclude_self=True)

    stats = getattr(player, 'stats', None) or {}
    hp = int(getattr(player, 'hit_points', 1) or 1)
    ps = int(stats.get('Strength', 10))
    pe = int(stats.get('Energy', 10))
    pt = int(stats.get('Constitution', 10))
    pi = int(stats.get('Intelligence', 10))
    pw = int(stats.get('Wisdom', 10))

    if hp + ps + pe + pt < 40:
        await ctx.send([
            'Looking at you, she sees you are not feeling too well. She gently lays',
            'a small hand on your head...',
        ])
        if hp < 10:
            player.hit_points = hp + 10
            await ctx.send('(Hit points return)')
        if ps < 10:
            stats['Strength'] = ps + 10
            await ctx.send('(Strength returns)')
        if pe < 10:
            stats['Energy'] = pe + 10
            await ctx.send('(Energy returns)')
        if pt < 10:
            stats['Constitution'] = pt + 10
            await ctx.send('(You feel healthier)')
        if pi < 27:
            stats['Intelligence'] = pi + 2
            await ctx.send('(You feel more intelligent)')
        if pw < 27:
            stats['Wisdom'] = pw + 2
            await ctx.send('(You feel wiser)')
        player.stats = stats
        player.unsaved_changes = True

    if player.honor < _HONOR_CAP:
        player.honor += _HONOR_GIVE_BONUS
        player.unsaved_changes = True

    hints = load_hints()
    if hints:
        await ctx.send([
            'She smiles a secretive little smile;',
            f'\'{random.choice(hints)}\'',
        ])

    level = int(getattr(player, 'map_level', 1) or 1)
    room  = _current_room(ctx)
    room_flags = getattr(room, 'flags', None) or []
    if 'water' in room_flags or 'water_with_rocks' in room_flags:
        farewell = 'rows off..'
    elif level > 5:
        farewell = 'fires steering rockets, and leaves..'
    else:
        farewell = 'runs off..'
    await ctx.send(f'The little girl {farewell}')
