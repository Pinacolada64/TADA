"""commands/movement.py

MoveCommand — move the player between rooms.

Handles bare direction aliases (n, s, e, w, u, d) and 'go <direction>'.
The direction is resolved from the first positional arg when present
(e.g. 'go north'), otherwise from ctx._invoked_as (e.g. bare 'n').

Special exits (shoppe elevator, bar) are checked here before delegating
normal movement to ctx.server._move().
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

# Rooms that trigger a sub-area module when entered, keyed by room number.
_BAR_ROOM    = 37   # Wall Bar & Grill
_SHOPPE_ROOM = None  # Shoppe is reached via rc/rt elevator, not a map room


async def _enter_shoppe(ctx: GameContext) -> None:
    """Player takes the elevator down to the Merchant Shoppe."""
    from shoppe.main import main as shoppe_main
    await shoppe_main(ctx)
    await ctx.server._show_room(ctx)


async def _enter_guild_hq(ctx: GameContext, guild_key: str) -> None:
    """Player enters a room aligned to their guild's HQ."""
    from guild_hq.main import main as hq_main
    await hq_main(ctx, guild_key)
    await ctx.server._show_room(ctx)


async def _enter_bar(ctx: GameContext) -> None:
    """Player enters the Wall Bar & Grill (room 37)."""
    ctx.client.room = _BAR_ROOM
    from bar.main import enter_bar
    await enter_bar(ctx)
    # On exit, show the room they came back to
    await ctx.server._show_room(ctx)


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

        # Check for special exits before normal movement
        game_map = getattr(ctx.server, 'game_map', None)
        room_no  = getattr(ctx.client, 'room', 1) or 1
        room     = game_map.rooms.get(int(room_no)) if game_map else None

        if room:
            exits = getattr(room, 'exits', {})

            # rc/rt transport system: rc=1 → Up, rc=2 → Down (no normal exit key)
            rc = int(exits.get('rc', 0) or 0)
            if (direction == 'u' and rc == 1) or (direction == 'd' and rc == 2):
                await _enter_shoppe(ctx)
                return CommandResult.ok()

            # Special destination: entering the bar
            dest = exits.get(direction)
            if dest and int(dest) == _BAR_ROOM:
                await _enter_bar(ctx)
                return CommandResult.ok()

            # Guild-aligned rooms trigger the guild HQ.
            # Room alignment is stored as a lowercase string ('fist', 'claw',
            # 'sword') from the JSON — not a Guild enum value.
            if dest:
                dest_room = game_map.rooms.get(int(dest)) if game_map else None
                align = getattr(dest_room, 'alignment', None) if dest_room else None
                _GUILD_KEY = {'claw': 'CLAW', 'sword': 'SWORD', 'fist': 'FIST'}
                gkey = _GUILD_KEY.get(str(align).lower()) if align else None
                if gkey:
                    await _enter_guild_hq(ctx, gkey)
                    return CommandResult.ok()

        await ctx.server._move(ctx, direction)
        return CommandResult.ok()
