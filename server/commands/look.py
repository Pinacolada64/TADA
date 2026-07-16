"""commands/look.py

LookCommand — examine the current room or inspect a target.
"""

import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from items import Rations, Weapon
from network_context import GameContext
from quests.tuts_treasure import examine as tuts_treasure_examine, is_tuts_treasure
from tada_utilities import PronounType, get_pronoun

_SELF_TARGETS = {'me', 'self', 'myself'}

# SPUR.MISC3.S exam2: a=(random(999)/10)+1; "if a>60 ... fails" -- so the
# roll is a 1-100 uniform draw and examination succeeds 60% of the time.
_EXAMINE_SUCCESS_PCT = 60


def _raw_item_data(ctx, item) -> dict | None:
    """Find *item*'s original objects.json/weapons.json/rations.json entry
    by id_number. New in TADA: EXAMINE flavor text used to live in an
    if-chain keyed off the item's name/kind here; it now lives in the data
    files themselves (an "examine" field) so new items don't need a code
    change to get their own description -- Ryan's request."""
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
    """
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


class LookCommand(Command):
    """Examine the current room or inspect a target."""

    name    = 'look'
    aliases = ['l']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Examine the current room, or inspect an object.',
        description = (
            'Without a target, describes your current location. '
            'With a target, inspects that object, creature, or player.'
        ),
        category = HelpCategory.MOVEMENT,
        usage    = [
            ('look',          'Describe the current room.'),
            ('l',             'Shorthand for look.'),
            ('look <target>', 'Inspect an object, creature, or player.'),
        ],
        examples = [
            ('look',       'See where you are.'),
            ('look sword', 'Examine the sword.'),
            ('look me',    'Examine yourself.'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)

        if not positional:
            await ctx.server._show_room(ctx)
            await ctx.send_room(
                f'{ctx.player.name} looks around.',
                exclude_self=True,
            )
            return CommandResult.ok()

        target = ' '.join(positional).lower()

        if target in _SELF_TARGETS:
            name      = ctx.player.name
            reflexive = get_pronoun(ctx.player, PronounType.REFLEXIVE)
            await ctx.send(f'You examine yourself.')
            await ctx.send_room(f'{name} examines {reflexive}.', exclude_self=True)
            return CommandResult.ok()

        # Search inventory for a matching item.
        inv = getattr(ctx.player, 'inventory', None)
        if inv is not None:
            for entry in inv.entries():
                item = entry.item
                iname = (getattr(item, 'name', '') or '').strip()
                if target in iname.lower():
                    await self._describe_item(ctx, iname, item)
                    return CommandResult.ok()

        # Search items on the ground too -- SPUR's EXAMINE worked on floor
        # items as well as carried ones (e.g. Tut's Treasure must be
        # examined before it's ever picked up -- see quests/tuts_treasure.py).
        from commands.get import _room_available_items
        for name, entry, _remove_fn in _room_available_items(ctx):
            if target in name.lower():
                await self._describe_item(ctx, name, entry.item)
                return CommandResult.ok()

        await ctx.send(f"You don't see any '{target}' here.")
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
