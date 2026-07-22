"""commands/look.py

LookCommand — examine the current room or inspect a target.

Plain description only -- SPUR's original LOOK just redisplayed the
room and took no target at all (SPUR.MAIN.S:102). The roll-based
flavor-text/magic-cursed/"already examined" logic (SPUR.MISC3.S's
EXAMINE/X) lives in commands/examine.py now, split out so LOOK stays a
simple "show me around" command -- Ryan's request.
"""

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext
from tada_utilities import PronounType, get_pronoun

_SELF_TARGETS = {'me', 'self', 'myself'}


class LookCommand(Command):
    """Examine the current room or inspect a target."""

    name    = 'look'
    aliases = ['l']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Examine the current room, or inspect an object.',
        description = (
            'Without a target, describes your current location. '
            'With a target, gives a plain description of that object, '
            'creature, or player -- see EXAMINE for a closer look that '
            'might reveal something LOOK misses.'
        ),
        category = HelpCategory.MOVEMENT,
        usage    = [
            ('look',          'Describe the current room.'),
            ('l',             'Shorthand for look.'),
            ('look <target>', 'Describe an object, creature, or player.'),
        ],
        examples = [
            ('look',       'See where you are.'),
            ('look sword', 'Describe the sword.'),
            ('look me',    'Describe yourself.'),
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

        # Search items on the ground too.
        from commands.get import _room_available_items
        for name, entry, _remove_fn in _room_available_items(ctx):
            if target in name.lower():
                await self._describe_item(ctx, name, entry.item)
                return CommandResult.ok()

        await ctx.send(f"You don't see any '{target}' here.")
        return CommandResult.ok()

    async def _describe_item(self, ctx: GameContext, name: str, item) -> None:
        description = (getattr(item, 'description', '') or '').strip()
        await ctx.send(description or f'You see a {name}.')
