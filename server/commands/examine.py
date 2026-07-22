"""commands/examine.py

ExamineCommand -- SPUR.MISC3.S's EXAMINE/X: inspect a specific item, or
(with no target) everything you're carrying and everything in the room.
Split out of look.py (Ryan's request) so LOOK stays a plain "show me
around" command and EXAMINE keeps SPUR's roll-based flavor-text/
"already examined" memory logic separate.

Not yet ported from SPUR.MISC3.S: monster examination (exam.mon/
mon.dv/mon.fd/mon.des -- race-based food/treasure discovery, disease
risk -- Ryan plans to fill in item/monster descriptions later) and the
"hidden" probe branch's hardcoded per-room item discoveries (its SPUR
room numbers, e.g. level 6 room 752, don't match TADA's current
level_6.json at all -- would need a fresh data-driven redesign, not a
literal port).
"""
from __future__ import annotations

import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from items import Rations, Weapon
from network_context import GameContext
from quests.tuts_treasure import examine as tuts_treasure_examine, is_tuts_treasure

# SPUR.MISC3.S exam2: a=(random(999)/10)+1; "if a>60 ... fails" -- so the
# roll is a 1-100 uniform draw and examination succeeds 60% of the time.
_EXAMINE_SUCCESS_PCT = 60


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

        if not positional:
            # SPUR's "EXAMINE ALL" (exam.b/plyr.loc): everything carried,
            # then everything in the room; "This area is empty.." if there
            # was truly nothing to examine.
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
