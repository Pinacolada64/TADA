"""encounters/dwarf.py — The Dwarf: a level-1 NPC who steals silver (or an
item) from players and can be hunted down and killed for his hoard.

SPUR source:
  - SPUR.LOGON.S "dwf.spur"/"dwf": world-init room placement -- a random
    level-1 room, re-rolling past a short exclusion list of "we don't want
    the dwarf here" rooms.
  - SPUR.MAIN.S "dwarf"/"no.dwarf" (called every move, `gosub dwarf`): a
    1-in-100 roll (only once the Dwarf is placed) triggers the theft
    subroutine below; separately, if the player is standing in the
    Dwarf's own room (level 1 only), he appears as a fightable encounter
    ("A short bearded person is here, with a pile of gold!").
  - SPUR.MISC5.S "dwarf" (the actual theft): steals all silver in hand if
    the player is carrying any; otherwise steals an inventory item,
    preferentially the win-condition item if carried, else a random one.
    No-op in water/vacuum ("@@") rooms.
  - SPUR.MISC.S:385-388 ("p.a4"): on death, awards his entire accumulated
    hoard to the killer and resets it to 0.

Deviates from SPUR (Ryan's explicit request, not a ported mechanic): the
original places the Dwarf once at world-init and never relocates him
(MECHANICS.md's original note said as much). This adds a periodic
relocation timer (config.dwarf_move_interval_minutes) so he's a moving
target instead of a campable fixed encounter.

One shared Dwarf, one shared room, one shared hoard -- but "have I
personally killed him" is tracked per player (PlayerFlags.DWARF_ALIVE):
killing him stops him robbing you specifically, while he keeps roaming
and stealing from everyone else who hasn't killed him yet. See
try_steal()'s per-player immunity check and on_killed()'s flag clear.

State split across two places:
  - config.py's dwarf_silver -- his stolen hoard, server-wide, shared by
    every player, sysop-visible/editable via CONFIG (unchanged by this
    module).
  - run/server/dwarf_state.json (this module) -- his current room and the
    last time he relocated. Also server-wide/shared.
  - PlayerFlags.DWARF_ALIVE (flags.py, per-player) -- the one piece of
    per-player state: whether *this player* has personally killed him.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import random
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from network_context import GameContext

log = logging.getLogger(__name__)

MONSTER_NUMBER = 137
MONSTER_NAME = 'DWARF'  # monsters.json's own name field -- combat/engine.py
                        # hardcodes "the {name}" everywhere, so (matching
                        # every other monster's naming convention, e.g.
                        # "SAND CRAB" not "THE SAND CRAB") the name itself
                        # carries no built-in article.

DWARF_LEVEL = 1

# SPUR.LOGON.S "dwf": rooms the world-init roll skips past (SPUR's own
# room-numbering, which doesn't line up 1:1 with this port's level_1.json
# -- see quests/README.md's "recurring blocker" note). Translated
# functionally instead of reusing the stale literals: the shoppe elevator
# (room 1, rc==1/2) and any guild-HQ-aligned room (sword/claw/fist),
# both of which trigger their own movement.py interception and would be a
# strange place for a second encounter to also live.
_EXCLUDED_ALIGNMENTS = {'sword', 'claw', 'fist'}

_STATE_FILE = Path('run') / 'server' / 'dwarf_state.json'

# Rooms flagged 'water'/'water_with_rocks' are safe from the Dwarf -- same
# "@@" gate SPUR.MISC5.S's theft subroutine checks (this port's level 6
# reuses the same flag name for vacuum; the Dwarf never appears there
# anyway since he's level-1 only, but the gate is written generically).
_SAFE_ROOM_FLAGS = {'water', 'water_with_rocks'}

_THEFT_CHANCE_PCT = 1  # SPUR.MAIN.S: rnd(100)==50, i.e. 1-in-100


def _append_battle_log(entry: str) -> None:
    """New in TADA -- the original doesn't log the Dwarf's death at all
    (checked SPUR.MISC.S's p.a3, just a print, no file write). Added on
    Ryan's request to match this port's own convention for other notable
    kills (Excalibur pull, Wraith King). Duplicated rather than shared,
    matching street/allies_guild.py's/combat/engine.py's own copies of
    the same helper."""
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
    except Exception:
        log.exception('Failed to write battle.log')


def load_state() -> dict:
    try:
        if _STATE_FILE.exists():
            return json.loads(_STATE_FILE.read_text())
    except Exception:
        log.exception('Failed to load dwarf state')
    return {'room': 0, 'last_moved': None}


def save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2))


def current_room() -> int:
    """Return the Dwarf's current level-1 room number, or 0 if not placed
    / dead (mirrors SPUR's df==0 meaning "no dwarf")."""
    return int(load_state().get('room', 0) or 0)


def is_placed() -> bool:
    """Whether the Dwarf currently exists anywhere in the world at all --
    server-wide, distinct from a given player's own PlayerFlags.DWARF_ALIVE
    (whether *that player specifically* has already killed him; see
    try_steal()'s per-player immunity check and on_killed())."""
    return current_room() != 0


def visible_to(player) -> bool:
    """Whether *player* can currently see/target the Dwarf as a monster,
    given monster['number'] == MONSTER_NUMBER was already found in their
    room. False once this specific player has personally killed him
    (PlayerFlags.DWARF_ALIVE) -- he's still there for everyone else who
    hasn't. Call sites: commands/attack.py, commands/get.py,
    commands/give.py's monster-in-room lookups."""
    from flags import PlayerFlags
    return player.query_flag(PlayerFlags.DWARF_ALIVE)


def _eligible_rooms(game_map) -> list[int]:
    level_rooms = game_map.levels.get(DWARF_LEVEL, {}) if game_map else {}
    eligible = []
    for num, room in level_rooms.items():
        exits = getattr(room, 'exits', {}) or {}
        if exits.get('rc'):
            continue  # shoppe elevator / any transport room
        alignment = getattr(room, 'alignment', None)
        align_value = getattr(alignment, 'value', alignment)
        if align_value in _EXCLUDED_ALIGNMENTS:
            continue
        eligible.append(num)
    return eligible


def relocate(game_map) -> int:
    """Move the Dwarf to a new random eligible level-1 room, clearing his
    old room's monster slot first. Returns the new room number (0 if no
    eligible room exists, e.g. level 1 not loaded)."""
    eligible = _eligible_rooms(game_map)
    if not eligible:
        log.warning('encounters.dwarf.relocate: no eligible level-1 room found')
        return 0

    state = load_state()
    old_room_no = int(state.get('room', 0) or 0)
    if old_room_no:
        old_room = game_map.get_room(DWARF_LEVEL, old_room_no)
        if old_room is not None and getattr(old_room, 'monster', 0) == MONSTER_NUMBER:
            old_room.monster = 0

    new_room_no = random.choice(eligible)
    new_room = game_map.get_room(DWARF_LEVEL, new_room_no)
    if new_room is not None:
        new_room.monster = MONSTER_NUMBER

    save_state({
        'room': new_room_no,
        'last_moved': datetime.datetime.utcnow().isoformat(),
    })
    return new_room_no


def maybe_relocate(ctx: 'GameContext') -> None:
    """Call on every player move (mirrors wild_horse_events.py's
    try_wandering_horse_encounter() call site). Relocates the Dwarf if
    config.dwarf_move_interval_minutes has elapsed since he last moved, or
    places him for the first time if he's never been placed."""
    game_map = getattr(ctx.server, 'game_map', None)
    if not game_map:
        return

    state = load_state()
    last_moved = state.get('last_moved')
    room = int(state.get('room', 0) or 0)

    if room == 0 or not last_moved:
        relocate(game_map)
        return

    from config import config
    interval = datetime.timedelta(minutes=config.dwarf_move_interval_minutes)
    try:
        elapsed_since = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last_moved)
    except (TypeError, ValueError):
        relocate(game_map)
        return

    if elapsed_since >= interval:
        relocate(game_map)


def _room_is_safe(room) -> bool:
    flags = getattr(room, 'flags', None) or []
    return any(f in _SAFE_ROOM_FLAGS for f in flags)


def _carries_silver(player) -> int:
    from base_classes import PlayerMoneyTypes
    return int(player.get_silver(PlayerMoneyTypes.IN_HAND) or 0)


def _take_all_silver(player) -> None:
    from base_classes import PlayerMoneyTypes
    from config import config
    amount = _carries_silver(player)
    player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, 0)
    config.dwarf_silver = config.dwarf_silver + amount
    player.unsaved_changes = True


def _steal_item(player) -> str | None:
    """Remove one item from the player's inventory (preferentially the
    win-condition item if carried, else random) and return its name, or
    None if the player carries nothing."""
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return None
    entries = list(inv.entries())
    if not entries:
        return None

    from config import config
    target_entry = None
    if config.victory_item_number:
        target_entry = next(
            (e for e in entries
             if getattr(e.item, 'id_number', None) == config.victory_item_number),
            None,
        )
    if target_entry is None:
        target_entry = random.choice(entries)

    name = getattr(target_entry.item, 'name', 'something')
    inv.remove(target_entry.item)
    player.unsaved_changes = True
    return name


_EVASION_CHANCE_PCT = 50  # mounted / Pixie: half the time he can't reach you


async def try_steal(ctx: 'GameContext') -> None:
    """SPUR.MAIN.S "dwarf" + SPUR.MISC5.S "dwarf": per-move 1% theft roll.
    No-op if the Dwarf isn't currently placed, the room is water/vacuum
    -flagged, or this specific player has already killed him (per-player
    immunity -- PlayerFlags.DWARF_ALIVE, not a ported SPUR mechanic; he
    keeps robbing every other player who hasn't killed him yet, since he's
    one shared world NPC, not a per-player instance).

    New in TADA: mounted players and Pixies (both effectively out of a
    short dwarf's reach) get a 50% chance he fails to actually grab
    anything even though he tries -- Ryan's addition, flavor text only.
    """
    if not is_placed():
        return
    if random.randint(1, 100) > _THEFT_CHANCE_PCT:
        return

    game_map = getattr(ctx.server, 'game_map', None)
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(ctx.player, 'map_level', 1) or 1)
    room     = game_map.get_room(level, room_no) if game_map and room_no else None
    if _room_is_safe(room):
        return

    player = ctx.player
    from flags import PlayerFlags
    if not player.query_flag(PlayerFlags.DWARF_ALIVE):
        return

    from tada_utilities import PronounType, get_pronoun
    name      = getattr(player, 'name', 'Someone')
    possessive = get_pronoun(player, PronounType.POSSESSIVE_ADJECTIVE)
    objective  = get_pronoun(player, PronounType.OBJECTIVE)

    if player.query_flag(PlayerFlags.MOUNTED):
        if random.randint(1, 100) <= _EVASION_CHANCE_PCT:
            await ctx.send('The DWARF struggles to reach up towards you!')
            await ctx.send_room(
                f'The DWARF struggles to reach up towards {name}!',
                exclude_self=True,
            )
            return
    else:
        from base_classes import PlayerRace
        if getattr(player, 'char_race', None) == PlayerRace.PIXIE:
            if random.randint(1, 100) <= _EVASION_CHANCE_PCT:
                await ctx.send('The DWARF swats at you angrily as you fly by!')
                await ctx.send_room(
                    f'The DWARF swats angrily at {name} as {objective} flies by!',
                    exclude_self=True,
                )
                return

    if _carries_silver(player) > 0:
        _take_all_silver(player)
        await ctx.send('The DWARF runs into the room, knocks you down and steals your silver!')
        await ctx.send_room(
            f'The DWARF runs into the room, knocks {name} down and steals '
            f'{possessive} silver!',
            exclude_self=True,
        )
        return

    item_name = _steal_item(player)
    if item_name is None:
        # SPUR.MISC5.S's own "dwarf" returns silently here (`if xi=0
        # return`) -- nothing to steal, no message. This flavor line is
        # Ryan's addition: a successful roll should still be visible even
        # when he comes up empty-handed, rather than vanishing silently.
        await ctx.send('A short bearded person eyes you, grumbles, and wanders off empty-handed.')
        await ctx.send_room(
            f'A short bearded person eyes {name}, grumbles, and wanders off empty-handed.',
            exclude_self=True,
        )
        return
    await ctx.send(
        'The dwarf, seeing you are not carrying any silver, '
        f'steals your {item_name}!'
    )
    await ctx.send_room(
        f'The dwarf, seeing {name} is not carrying any silver, '
        f'steals {possessive} {item_name}!',
        exclude_self=True,
    )


async def on_killed(ctx: 'GameContext') -> list[str]:
    """SPUR.MISC.S:385-388 ("p.a4"): award the Dwarf's entire (shared,
    server-wide) hoard to the killer, reset it, clear his room, and
    relocate him. Call this from combat/engine.py's _monster_dies() once
    it's confirmed the monster that died was the Dwarf (monster['number']
    == MONSTER_NUMBER).

    Also clears the killer's own PlayerFlags.DWARF_ALIVE (per-player, not
    from SPUR -- see try_steal()'s docstring): this player personally
    stops being robbed from now on, but the Dwarf keeps roaming and
    stealing from everyone else once he relocates.
    """
    from config import config
    from flags import PlayerFlags

    hoard = config.dwarf_silver
    if hoard:
        from base_classes import PlayerMoneyTypes
        player = ctx.player
        current = player.get_silver(PlayerMoneyTypes.IN_HAND)
        player.set_silver_absolute(PlayerMoneyTypes.IN_HAND, current + hoard)
        player.unsaved_changes = True
    config.dwarf_silver = 0
    ctx.player.clear_flag(PlayerFlags.DWARF_ALIVE)

    game_map = getattr(ctx.server, 'game_map', None)
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    room     = game_map.get_room(DWARF_LEVEL, room_no) if game_map and room_no else None
    if room is not None and getattr(room, 'monster', 0) == MONSTER_NUMBER:
        room.monster = 0
    save_state({'room': 0, 'last_moved': datetime.datetime.utcnow().isoformat()})

    name = getattr(ctx.player, 'name', 'Someone')
    if hoard:
        _append_battle_log(f'{name} slew the Dwarf and claimed {hoard:,} silver!')
        return [f'You find {hoard:,} silver on the Dwarf!']
    _append_battle_log(f'{name} slew the Dwarf!')
    return []
