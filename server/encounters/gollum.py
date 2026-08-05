"""encounters/gollum.py — Gollum guards the ring in his cave (level 4,
room 17 "Gollum's Cave", monsters.json #71), and will trade riddles with
you if you SAY or ASK one.

Room 17 has both the monster and the ring (objects.json #67 "ring") sitting
in it together, but nothing previously stopped a player from just GETting
the ring out from under a live Gollum. This gives him what SPUR-flavored
guard monsters elsewhere already do for their own treasure (see
quests/tuts_treasure.py's King Tut, encounters/dwarf.py's hoard): a refusal
plus a real fight, not just a rebuff message.

The riddle content below is original -- no SPUR-native "ask Gollum a
riddle" source exists to port from (see quests/README.md's "Test of
Galadriel" for the one SPUR-sourced riddle mechanic, which is unrelated).
Half of _RIDDLES draw on the same classic riddle *themes* Gollum poses in
The Hobbit (teeth, a fish, the wind, the dark) -- deliberately reworded
rather than quoting Tolkien's copyrighted verses -- and half are wholly
original, built around TADA's own world (silver economy, dragons, etc.)
instead of Middle-earth's.
"""
from __future__ import annotations

import random

RING_ITEM_ID     = 67
MONSTER_NUMBER   = 71
QUOTE            = "You cannot have my precioussssss!"

# Gates the room-description riddle hint (simple_server.py's _describe_room)
# to once per day per player -- same player.once_per_day convention as
# encounters/djinn_sighting.py, so it doesn't rebox itself on every look.
_HINT_ONCE_PER_DAY_KEY = 'gollum_riddle_hint_seen'

_RIDDLE_RESPONSES = [
    'Gollum hisses, "We knows riddles, precious, we do, yes!"',
    'Gollum\'s eyes go wide. "Tricksy, tricksy! But Gollum isn\'t fooled, no!"',
    'Gollum scratches his head. "Let Gollum think, precious... just a moment..."',
    'Gollum grins a nasty grin. "Sneaky hobbitses love a riddle-game, yes!"',
    'Gollum snarls. "Ask usss another! Gollum likes this game, gollum, gollum!"',
]

# The curated ASK-menu riddles (commands/ask.py). Each entry is asked
# verbatim to Gollum, then answered in character -- unlike the freeform
# SAY banter above, these always land on a specific, "correct" answer,
# since in the source material he's a riddle-master, not a random guesser.
_RIDDLES = [
    # -- Hobbit-flavored themes, original wording --
    {
        'text':  'Hard and white in a warm, red room, they grind all day '
                  'and rest at night. What am I?',
        'reply': 'Gollum snaps his jaws together. '
                  '"Teeth, precious! Nasty, biting teeth, gollum, gollum!"',
    },
    {
        'text':  "I've no lungs to breathe, yet I never drown; cold rivers "
                  "are my home, and I never come up for air. What am I?",
        'reply': 'Gollum smacks his lips. '
                  '"A fisssh, precious! Cold and slippery, we loves them raw!"',
    },
    {
        'text':  'I have no mouth, yet I moan and roar; I have no hands, '
                  'yet I topple towers. What am I?',
        'reply': 'Gollum tilts his head, listening. '
                  '"The wind, yes! It blows and blows, and Gollum hears it howl!"',
    },
    {
        'text':  'The more of me there is, the less you can see; kings '
                  'fear me, and thieves love me well. What am I?',
        'reply': 'Gollum\'s eyes glint in the gloom. '
                  '"The dark, precious! Gollum knows the dark, oh yes, very well!"',
    },
    # -- Original, TADA-flavored --
    {
        'text':  'I have a blade but never an edge, a hilt but never a '
                  'hand; I hang on the wall and I guard the land. What am I?',
        'reply': 'Gollum squints at the ceiling, then grins. '
                  '"A sword, precious! A shiny sword that never cuts, no!"',
    },
    {
        'text':  'I open every door there is, yet I never turn a handle '
                  'myself. What am I?',
        'reply': 'Gollum jangles an invisible ring of them. '
                  '"A key, we knows it! Keysss open everything, gollum!"',
    },
    {
        'text':  'I am counted by the piece and prized for my shine, '
                  'spent in the tavern to buy your wine. What am I?',
        'reply': 'Gollum\'s eyes go hungry and bright. '
                  '"Silver, precious! Bright, shiny silver, we wants it!"',
    },
    {
        'text':  'I breathe fire but I am not the sun; I hoard a fortune '
                  'but I spend not one. What am I?',
        'reply': 'Gollum shudders and hisses. '
                  '"A dragon! A nasty, burny dragon, keep it away from usss!"',
    },
]


def _is_alive(monster: dict) -> bool:
    # Not "monster.get('strength') or monster.get('hit_points') or 1"
    # (get.py's own _try_get_living uses that chain) -- 0 is falsy, so
    # that pattern would treat a dead (strength=0) monster as alive again.
    hp = monster.get('strength')
    if hp is None:
        hp = monster.get('hit_points', 1)
    return int(hp) > 0


def guards_ring(item_id, monster: dict | None, player=None) -> bool:
    """True if *monster* is a living Gollum guarding item #67.

    monster.json's strength/hit_points is only the shared template --
    combat/engine.py's CombatSession fights on its own `dict(monster)`
    copy (see enter_combat()), so a kill never actually zeroes the
    global entry. _is_alive() alone is therefore always true again once
    a fresh CombatSession is built, which let a player GET RING right
    back out of a Gollum they'd already killed. player.dead_monsters is
    this port's actual per-player "have I killed this one" gate (see
    combat/engine.py's _record_kill()), so it has to be checked too."""
    try:
        if int(item_id) != RING_ITEM_ID:
            return False
    except (TypeError, ValueError):
        return False

    if not monster or int(monster.get('number', 0) or 0) != MONSTER_NUMBER:
        return False

    if player is not None and MONSTER_NUMBER in (getattr(player, 'dead_monsters', None) or []):
        return False

    return _is_alive(monster)


def should_show_riddle_hint(player) -> bool:
    """True if *player* hasn't seen the "You can ask Gollum riddles" hint
    yet today."""
    return _HINT_ONCE_PER_DAY_KEY not in (getattr(player, 'once_per_day', None) or [])


def mark_riddle_hint_shown(player) -> None:
    once = getattr(player, 'once_per_day', None)
    if once is None:
        player.once_per_day = once = []
    if _HINT_ONCE_PER_DAY_KEY not in once:
        once.append(_HINT_ONCE_PER_DAY_KEY)
    player.unsaved_changes = True


def riddle_response(monster: dict | None) -> str | None:
    """A random Gollum riddle-banter line, or None if *monster* isn't a
    living Gollum (lets callers tell "wrong/dead monster" apart from
    "Gollum had nothing to say" -- currently the same thing, but keeps
    the two reasons distinguishable if that changes)."""
    if not monster or int(monster.get('number', 0) or 0) != MONSTER_NUMBER:
        return None
    if not _is_alive(monster):
        return None
    return random.choice(_RIDDLE_RESPONSES)


def current_gollum(ctx) -> dict | None:
    """Return the monster dict for a living Gollum in ctx's current room,
    or None -- shared by commands/say.py's freeform banter and
    commands/ask.py's riddle menu so the room/alive lookup lives in one
    place instead of two."""
    game_map = getattr(ctx.server, 'game_map', None)
    monsters = getattr(ctx.server, 'monsters', [])
    room_no  = getattr(ctx.client, 'room', None)
    if not game_map or not monsters or room_no is None:
        return None

    level = int(getattr(ctx.player, 'map_level', 1) or 1)
    room  = game_map.get_room(level, int(room_no))
    mon_number = int(getattr(room, 'monster', 0) or 0) if room else 0
    if mon_number != MONSTER_NUMBER:
        return None

    if MONSTER_NUMBER in (getattr(ctx.player, 'dead_monsters', None) or []):
        return None

    from monsters import get_monster
    monster = get_monster(monsters, mon_number)
    return monster if monster and _is_alive(monster) else None


async def ask_riddle_menu(ctx) -> None:
    """Show a numbered menu of _RIDDLES and, if the player picks one, has
    them ask it aloud to Gollum and relays his in-character answer."""
    from formatting import numbered_list
    width = getattr(ctx.player.client_settings, 'screen_columns', 60)
    lines = ['Which riddle would you like to ask Gollum?', '']
    lines += numbered_list([riddle['text'] for riddle in _RIDDLES], width)
    await ctx.send(lines)

    raw = await ctx.prompt(f'Riddle # ({ctx.player.return_key} to cancel)')
    try:
        choice = int((raw or '').strip())
    except ValueError:
        choice = 0
    if choice < 1 or choice > len(_RIDDLES):
        await ctx.send('You decide not to ask, after all.')
        return

    riddle = _RIDDLES[choice - 1]
    name = getattr(ctx.player, 'name', 'Someone')
    await ctx.send(f'You ask, "{riddle["text"]}"')
    await ctx.send_room(f'{name} asks, "{riddle["text"]}"', exclude_self=True)
    # TODO: random chance of not guessing the correct answer:
    await ctx.send_room(riddle['reply'])
    # TODO: reward (NOT the ring!)
