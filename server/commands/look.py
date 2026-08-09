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
        category = HelpCategory.INTERACTION,
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

        # Search the player's own party for a matching ally.
        from bar.allies import owned_allies
        for ally in owned_allies(ctx.player):
            if target in ally.name.lower():
                await self._describe_ally(ctx, ally)
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

    async def _describe_ally(self, ctx: GameContext, ally) -> None:
        """Simple LOOK flavor for a party member.

        A MOUNT ally (AllyFlags.MOUNT) also gets its gender/breed/colour,
        e.g. "SILVER is a female Palomino Arabian." -- see MECHANICS.md's
        "Horses" section and base_classes.HorseBreed/HorseColor's
        docstrings. General NPC/ally flavor text beyond this is a wider,
        not-yet-scoped gap (see the project_npc_descriptions_todo memory
        note) -- this only covers the horse-specific case Ryan asked for.

        A mount also gets a second line reporting saddle/armor status
        (AllyFlags.SADDLED/ARMORED, set by USEing a Saddle/Horse Armor
        bought at Jake's Stable -- commands/use.py's SPUR.USE.S eq.horse
        port) -- there was previously no way to check this without USEing
        the items again. Ryan's request.

        A mount with saddlebags (AllyFlags.SADDLEBAGS) gets a third line
        noting them, plus a thin/fat build based on how full they are
        (ally.items vs commands/give.py's _MOUNT_CAPACITY_WITH_SADDLEBAGS)
        -- a whimsical way to check pack fullness at a glance without
        opening the inventory menu. Ryan's request.
        """
        from bar.ally_data import AllyFlags
        from base_classes import Gender

        if AllyFlags.MOUNT in (ally.flags or []):
            gender_word = 'female' if ally.gender == Gender.FEMALE else 'male'
            if ally.breed and ally.color:
                await ctx.send(f'{ally.name} is a {gender_word} {ally.color} {ally.breed}.')
            else:
                # Legacy/older save: mount predates the breed/colour fields.
                await ctx.send(f'{ally.name} is a {gender_word} horse.')

            flags      = ally.flags or []
            has_saddle = AllyFlags.SADDLED in flags
            has_armor  = AllyFlags.ARMORED in flags
            if has_saddle and has_armor:
                await ctx.send(f'{ally.name} is saddled and wearing horse armor.')
            elif has_saddle:
                await ctx.send(f'{ally.name} is saddled, but has no horse armor.')
            elif has_armor:
                await ctx.send(f'{ally.name} is wearing horse armor, but has no saddle.')
            else:
                await ctx.send(f'{ally.name} has no saddle or horse armor.')

            if AllyFlags.SADDLEBAGS in flags:
                from commands.give import _MOUNT_CAPACITY_WITH_SADDLEBAGS
                count = len(ally.items or [])
                if count <= 0:
                    build = 'looking a bit thin'
                elif count >= _MOUNT_CAPACITY_WITH_SADDLEBAGS:
                    build = 'looking fat and well-packed'
                else:
                    build = 'looking comfortably full'
                await ctx.send(f'{ally.name} has saddlebags strapped on, {build}.')
            else:
                await ctx.send(f'{ally.name} has no saddlebags.')
            return

        await ctx.send(f'{ally.name} is here with you, ready to help.')
