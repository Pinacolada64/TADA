"""commands/look.py

LookCommand — examine the current room or inspect a target.
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

        await ctx.send(f'You look at {target}.  (object inspection not yet wired up)')
        return CommandResult.ok()
