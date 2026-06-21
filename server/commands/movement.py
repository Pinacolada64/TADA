"""commands/movement.py

MoveCommand — move the player between rooms.

Handles bare direction aliases (n, s, e, w, u, d) and 'go <direction>'.
The direction is resolved from the first positional arg when present
(e.g. 'go north'), otherwise from ctx._invoked_as (e.g. bare 'n').
"""

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from network_context import GameContext

_DIR_ALIASES: dict[str, str] = {
    'n': 'n', 'north': 'n',
    's': 's', 'south': 's',
    'e': 'e', 'east':  'e',
    'w': 'w', 'west':  'w',
    'u': 'u', 'up':    'u',
    'd': 'd', 'down':  'd',
}


class MoveCommand(Command):
    """Move the player's character between rooms."""

    name    = 'go'
    aliases = ['move',
               'n', 's', 'e', 'w', 'u', 'd',
               'north', 'south', 'east', 'west', 'up', 'down']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Move in a compass direction.',
        description = (
            'Use single-letter shortcuts (n, s, e, w, u, d), full words '
            '(north, south, east, west, up, down), or "go <direction>".'
        ),
        category = HelpCategory.MOVEMENT,
        usage    = [
            ('n | s | e | w | u | d', 'Move one step in that direction.'),
            ('go <direction>',          'Alternate form: go north, go n, etc.'),
        ],
        examples = [
            ('n',        'Move north.'),
            ('go west',  'Move west.'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        positional, _ = self.parse_args(*args)

        # 'go north' / 'move n' → direction is first arg
        # bare 'n' / 'north'   → direction is the token the player typed
        token = positional[0].lower() if positional else getattr(ctx, '_invoked_as', '')

        direction = _DIR_ALIASES.get(token)
        if not direction:
            await ctx.send('Go where? (n/s/e/w/u/d)')
            return CommandResult.fail('No direction.', error='no_direction')

        await ctx.server._move(ctx, direction)
        return CommandResult.ok()
