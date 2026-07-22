"""commands/examine.py

ExamineCommand -- SPUR.MISC3.S's EXAMINE/X: inspect a specific item, or
(with no target) everything you're carrying and everything in the room.
Split out of look.py (Ryan's request) so LOOK stays a plain "show me
around" command and EXAMINE keeps SPUR's roll-based flavor-text/
"already examined" memory logic separate.

Not yet ported from SPUR.MISC3.S: the "hidden" probe branch's hardcoded
per-room item discoveries (its SPUR room numbers, e.g. level 6 room
752, don't match TADA's current level_6.json at all -- would need a
fresh data-driven redesign, not a literal port).
"""
from __future__ import annotations

import random

from base_classes import PlayerRace
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from items import Item, ItemCategory, Rations, Weapon
from network_context import GameContext
from quests.tuts_treasure import examine as tuts_treasure_examine, is_tuts_treasure
from survival import apply_disease
from tada_utilities import a_or_an

# SPUR.MISC3.S exam2: a=(random(999)/10)+1; "if a>60 ... fails" -- so the
# roll is a 1-100 uniform draw and examination succeeds 60% of the time.
_EXAMINE_SUCCESS_PCT = 60

# SPUR.MISC3.S mon.dv: i=16:it$="COIN":iv=1 / a>40 "GOLD SACK":iv=3 /
# a>70 "DIAMOND":iv=4 / a>90 "SACK OF DIAMONDS":iv=6. None of those four
# names exist as their own objects.json entries in this port -- mapped
# onto the nearest existing treasure-tier items instead of inventing new
# data entries for names nothing else references. (threshold, item id, name)
_MONSTER_TREASURE_TIERS = [
    (90, 15, 'mound of jewels'),   # rarest -- "SACK OF DIAMONDS" equivalent
    (70, 22, 'diamonds'),          # "DIAMOND" equivalent
    (40, 27, 'diamond pile'),      # "GOLD SACK" equivalent
    (0,  11, 'gold coins'),        # most common -- "COIN" equivalent
]

# SPUR.MISC3.S mon.fd: fd=69:fd$=m$+" MEAT" -- rations.json #69 is
# literally "MONSTER MEAT", so this reuses that pool entry with a
# monster-specific display name instead of inventing a new one.
_MONSTER_MEAT_RATION_ID = 69

# SPUR.MISC3.S mon.dv: "if a<26" (dwarf treasure-spotting bonus).
_DWARF_TREASURE_CHANCE = 26
# SPUR.MISC3.S mon.des: "if a>2 return" -- a flat 2% disease chance from
# searching a corpse.
_DISEASE_CHANCE_PCT = 2


def _raw_item_data(ctx, item) -> dict | None:
    """Find *item*'s original objects.json/weapons.json/rations.json entry
    by id_number. EXAMINE flavor text lives in the data files themselves
    (an "examine" field) so new items don't need a code change to get
    their own description -- Ryan's request."""
    item_id = getattr(item, 'id_number', None)
    if item_id is None:
        return None
    if isinstance(item, Weapon):
        pool = getattr(ctx.server, 'weapons', None) or []
    elif isinstance(item, Rations):
        pool = getattr(ctx.server, 'rations', None) or []
    else:
        pool = getattr(ctx.server, 'items', None) or []
    for raw in pool:
        if raw.get('number') == item_id:
            return raw
    return None


def _examine_item(ctx, name: str, item) -> str:
    """Return a one-line flavour description for *item*, mirroring
    SPUR.MISC3.S's exam.a/exam2/exam3.

    Items with their own "examine" text in the data file (STORM weapons,
    named treasures, potions, ...) always show it -- SPUR's exam3 branch
    has no random-failure gate. Magic weapons (weapons.json kind=="magic")
    and cursed treasures (objects.json type=="cursed") instead go through
    exam2's skill roll and its one-shot "already examined" memory (xz$ --
    see player.last_examined). SPUR rolls first and checks the memory
    second, so a failed roll re-fails even on a repeat examine; matched
    here for authenticity.

    A room statue (commands/get.py's is_statue pseudo-item, statues.py's
    add_statue()) isn't a real objects.json entry -- no id_number for
    _raw_item_data() to look up -- so it's special-cased here (Ryan's
    request) to name the petrified player and the monster responsible,
    rather than falling through to the generic "It looks pretty
    ordinary.." default.
    """
    if getattr(item, 'is_statue', False):
        victim  = getattr(item, 'victim', None) or 'someone'
        monster = getattr(item, 'monster', None) or 'Unknown'
        return (f'You inspect the statue of {victim}. At the base is a '
                f'small brass plaque which reads, "Artist: {monster}."')

    raw = _raw_item_data(ctx, item)
    if raw and raw.get('examine'):
        return raw['examine']

    kind = None
    if raw:
        if isinstance(item, Weapon) and raw.get('kind') == 'magic':
            kind = 'magic'
        elif raw.get('type') == 'cursed':
            kind = 'cursed'

    if kind in ('magic', 'cursed'):
        if random.randint(1, 100) > _EXAMINE_SUCCESS_PCT:
            return 'Your examination fails...'
        if getattr(ctx.player, 'last_examined', '') == name:
            return 'You have already examined this!'
        ctx.player.last_examined = name
        return f'This {name} is Magical.' if kind == 'magic' else f'This {name} is Cursed.'

    return 'It looks pretty ordinary..'


def _current_room(ctx):
    room_no  = int(getattr(ctx.client, 'room', 0) or 0)
    level    = int(getattr(ctx.player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    return game_map.get_room(level, room_no) if game_map and room_no else None


def room_monster(ctx) -> dict | None:
    """Return the room's monster dict, or None if there isn't one.

    Doesn't check dead_monsters -- callers decide what "examinable"
    means for their purposes (exam.mon's own md==0 refusal handles that
    for EXAMINE specifically).
    """
    room = _current_room(ctx)
    monster_no = int(getattr(room, 'monster', 0) or 0) if room else 0
    if not monster_no:
        return None
    from monsters import get_monster
    return get_monster(getattr(ctx.server, 'monsters', None) or [], monster_no)


def _player_has_item(player) -> bool:
    """SPUR's it$<>"" -- does the player already carry a non-food,
    non-weapon item? (SPUR's single item-slot model doesn't map exactly
    onto TADA's list inventory; "carrying any generic item" is the
    closest equivalent.)"""
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return False
    return any(not isinstance(e.item, (Rations, Weapon)) for e in inv.entries())


def _player_has_food(player) -> bool:
    """SPUR's fd$<>"" -- does the player already carry food?"""
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return False
    return any(isinstance(e.item, Rations) and getattr(e.item, 'kind', None) == 'food'
               for e in inv.entries())


def _monster_treasure(ctx) -> list[str]:
    """SPUR.MISC3.S mon.dv: search reveals a treasure item, awarded
    straight into the player's inventory (SPUR set it as the player's
    held item directly -- there's no separate "pick it up" step)."""
    roll = random.randint(1, 100)
    item_id, name = next((iid, n) for threshold, iid, n in _MONSTER_TREASURE_TIERS
                          if roll > threshold)
    item = Item(id_number=item_id, name=name, category=ItemCategory.ITEM)
    inv = getattr(ctx.player, 'inventory', None)
    if inv is not None:
        inv.add(item)
    return [f'Your search reveals {a_or_an(name)}!']


def _monster_food(ctx, monster: dict, has_food: bool) -> list[str]:
    """SPUR.MISC3.S mon.fd: race-modified roll for whether the corpse
    looks edible. Ogres/Orcs are more easily tempted (+25), Elves are
    disgusted by the idea (-25), Half-Elves mildly so (-12)."""
    player = ctx.player
    race   = getattr(player, 'char_race', None)
    name   = monster.get('name', 'the monster')
    roll   = random.randint(1, 100)
    if race in (PlayerRace.OGRE, PlayerRace.ORC):
        roll += 25
    elif race == PlayerRace.ELF:
        roll -= 25
    elif race == PlayerRace.HALF_ELF:
        roll -= 12

    lines: list[str] = []
    if roll < 1:
        lines.append('Your elvish eyes wrinkle in disgust.')
        roll = 0

    if roll < 50 or has_food:
        lines.append(f'Your search reveals nothing on the {name}.')
        lines.extend(_monster_disease_check(player))
        return lines

    ration = Rations(number=_MONSTER_MEAT_RATION_ID, name=f'{name} meat',
                     kind='food', price=25)
    inv = getattr(player, 'inventory', None)
    if inv is not None:
        inv.add(ration)
    lines.append(f'You decide the {name} looks edible! (sort of..)')
    return lines


def _monster_disease_check(player) -> list[str]:
    """SPUR.MISC3.S mon.des: a flat 2% chance of catching a disease from
    searching the corpse -- see survival.py for the actual HP-drain tick."""
    if random.randint(1, 100) > _DISEASE_CHANCE_PCT:
        return []
    apply_disease(player)
    return ['Yuk! You picked up a disease from the thing!']


def _examine_monster(ctx, monster: dict) -> list[str]:
    """SPUR.MISC3.S's exam.mon/mon.dv/mon.fd/mon.des: search a monster
    for treasure or food, with a small chance of catching a disease.
    Only reaches the search rolls once the monster is in
    player.dead_monsters -- a still-live one just refuses to be examined
    (SPUR's md==0 case; TADA has no equivalent of SPUR's md==2 "tracks
    only" state, so that branch isn't ported)."""
    player = ctx.player
    name   = monster.get('name', 'the monster')
    monster_no = monster.get('number')

    is_dead = monster_no in (getattr(player, 'dead_monsters', None) or [])
    if not is_dead:
        return [f"{name} doesn't like being examined!"]

    room  = _current_room(ctx)
    flags = set(getattr(room, 'flags', None) or [])

    roll = random.randint(1, 100)
    base_msg = f'Your search reveals nothing on the {name}.'
    if 'water' in flags or 'water_with_rocks' in flags:
        base_msg = f'Fish are nibbling on the {name}.'
    if 'snow' in flags:
        base_msg = f'The {name} is quite frozen!'
    if roll > 40:
        base_msg = "Yep. It's dead awright.."
    if roll > 70:
        base_msg = f'The {name} is quite ugly, actually..'

    has_item = _player_has_item(player)
    has_food = _player_has_food(player)

    if not has_item and getattr(player, 'char_race', None) == PlayerRace.DWARF:
        roll = random.randint(1, 100)
        if roll < _DWARF_TREASURE_CHANCE:
            return ['Your dwarvish eyes spot something!'] + _monster_treasure(ctx)

    roll = random.randint(1, 100)
    if roll > 70:
        return _monster_food(ctx, monster, has_food)

    roll = random.randint(1, 100)
    if roll > 15 or has_item:
        return [base_msg] + _monster_disease_check(player)

    # SPUR falls straight through to mon.dv here rather than taking an
    # explicit branch (exam.mon has no statement between this check and
    # the mon.dv label) -- matched for authenticity rather than adding a
    # branch SPUR itself doesn't have.
    return _monster_treasure(ctx)


class ExamineCommand(Command):
    """Inspect a specific item, or (with no target) examine everything
    you're carrying and everything in the room -- SPUR.MISC3.S's EXAMINE."""

    name    = 'examine'
    aliases = ['x']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Take a close look at an item -- may reveal something LOOK missed.',
        description = (
            'Without a target, examines everything you carry and everything '
            'in the room. With a target, examines just that item. Magic and '
            'cursed items only reveal their nature about 60% of the time, '
            'and re-examining one after a failed roll just repeats the '
            'failure message rather than trying again.'
        ),
        category = HelpCategory.MOVEMENT,
        usage    = [
            ('examine',          'Examine everything you carry and everything here.'),
            ('x',                'Shorthand for examine.'),
            ('examine <target>', 'Examine just that item.'),
        ],
        examples = [
            ('examine',       'Look closer at everything around you.'),
            ('examine sword', 'Examine the sword.'),
            ('x',             'Same as "examine".'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)

        from commands.get import _room_available_items
        inv          = getattr(ctx.player, 'inventory', None)
        inv_entries  = list(inv.entries()) if inv is not None else []
        room_entries = list(_room_available_items(ctx))
        monster      = room_monster(ctx)

        if not positional:
            # SPUR's "EXAMINE ALL" (exam.b/plyr.loc): everything carried,
            # then everything in the room, then the room's monster (if
            # any -- exam.mon itself handles a still-live one refusing);
            # "This area is empty.." if there was truly nothing at all.
            examined_any = False
            for entry in inv_entries:
                item  = entry.item
                iname = (getattr(item, 'name', '') or '').strip()
                if not iname:
                    continue
                await self._describe_item(ctx, iname, item)
                examined_any = True
            for name, entry, _remove_fn in room_entries:
                await self._describe_item(ctx, name, entry.item)
                examined_any = True
            if monster is not None:
                await ctx.send(_examine_monster(ctx, monster))
                examined_any = True
            if not examined_any:
                await ctx.send('This area is empty..')
            return CommandResult.ok()

        target = ' '.join(positional).lower()

        for entry in inv_entries:
            item  = entry.item
            iname = (getattr(item, 'name', '') or '').strip()
            if target in iname.lower():
                await self._describe_item(ctx, iname, item)
                return CommandResult.ok()

        for name, entry, _remove_fn in room_entries:
            if target in name.lower():
                await self._describe_item(ctx, name, entry.item)
                return CommandResult.ok()

        if monster is not None and target in monster.get('name', '').lower():
            await ctx.send(_examine_monster(ctx, monster))
            return CommandResult.ok()

        await ctx.send("You either spelled it wrong, or are seeing things..")
        await ctx.send("('X' examines all)")
        return CommandResult.ok()

    async def _describe_item(self, ctx: GameContext, name: str, item) -> None:
        item_id = getattr(item, 'id_number', None)
        if is_tuts_treasure(item_id):
            lines = tuts_treasure_examine(ctx.player)
            if lines is not None:
                await ctx.send(lines)
                return
            # Already examined -- SPUR falls through to the ordinary
            # flavor text on a repeat EXAMINE, so do the same here.
        await ctx.send(_examine_item(ctx, name, item))
