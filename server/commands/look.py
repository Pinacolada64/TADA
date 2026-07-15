"""commands/look.py

LookCommand — examine the current room or inspect a target.
"""

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from quests.tuts_treasure import examine as tuts_treasure_examine, is_tuts_treasure
from tada_utilities import PronounType, get_pronoun

_SELF_TARGETS = {'me', 'self', 'myself'}


def _examine_item(name: str, item) -> str:
    """Return a one-line flavour description for *item*. Mirrors SPUR.MISC3.S exam3."""
    uname = name.upper()
    if 'STORM' in uname:
        return f'There is much power in the {name}!'
    if 'POTION' in uname:
        return 'It is a magic potion!'
    kind = str(getattr(item, 'kind', '') or '').lower()
    if kind == 'magic':
        return f'This {name} is Magical.'
    if kind == 'cursed':
        return f'This {name} is Cursed.'
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
        await ctx.send(_examine_item(name, item))
