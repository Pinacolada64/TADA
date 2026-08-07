"""commands/movement.py

MoveCommand — move the player between rooms.

Handles bare direction aliases (n, s, e, w, u, d) and 'go <direction>'.
The direction is resolved from the first positional arg when present
(e.g. 'go north'), otherwise from ctx._invoked_as (e.g. bare 'n').

Special exits (shoppe elevator, bar) are checked here before delegating
normal movement to ctx.server._move().
"""

from base_classes import RoomAlignment
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext

_WATER_FLAGS = {'water', 'water_with_rocks'}

# SPUR's vehicle-launch mechanic (SPUR.MAIN.S's block.s/boat, ~lines
# 151-163 -- see TODO.md's "SPUR boat/vehicle-launch exit flavor text"
# entry and convert_from_gbbs_tool.py's RoomFlag.VEHICLE_EXIT_*/
# VEHICLE_DEPARTURE_* for the full derivation). Only one real instance
# exists in the converted game (level 6's Air Lock <-> Outer Space), but
# the mechanic itself is level-agnostic: dinghy on levels 1-5, spacesuit
# on level 6+. This is the item-gated half (can abort the move); the
# flavor-only sibling (VEHICLE_DEPARTURE_*, no item check, can't fail)
# lives in simple_server.py's _move() instead, since it depends on that
# method's own dest-resolution (hidden exits, rc/rt fallback) that isn't
# duplicated here.
_DINGHY_ID        = 74   # inflatable dinghy (objects.json)
_SPACESUIT_ID     = 122  # spacesuit (objects.json)
_SPACE_TRACKER_ID = 138  # space tracker (objects.json) -- level 6 bonus flavor only

_DIRECTION_TO_SUFFIX = {'n': 'north', 's': 'south', 'e': 'east', 'w': 'west'}

_DIR_ALIASES: dict[str, str] = {
    'n': 'n', 'north': 'n',
    's': 's', 'south': 's',
    'e': 'e', 'east':  'e',
    'w': 'w', 'west':  'w',
    'u': 'u', 'up':    'u',
    'd': 'd', 'down':  'd',
}

# Alt keymap (command_settings.wasd_movement): w/a/s/d -> north/west/south/
# east instead of the classic n/s/e/w. 's' means south either way, but 'w'
# and 'd' collide with the classic meanings (west, down) -- this can't be
# layered onto _DIR_ALIASES as extra entries, it has to replace w/d's
# meaning per-player. 'u'/'up' still work for Up under this keymap; there's
# no letter collision to resolve there.
_WASD_ALIASES: dict[str, str] = {
    'w': 'n', 'a': 'w', 's': 's', 'd': 'e',
}

# Rooms that trigger a sub-area module when entered, keyed by room number.
# The bar is level-gated in the original source, same as the Allys Guild/
# Jake's Stable checks below it (SPUR.MAIN.S: "if cl=1 then if cr=49 then
# if di=1 link dy$", right alongside those two's own cl/cr/di checks) --
# _BAR_ROOM (37) is this port's own exit-*destination* room number, which
# doesn't match SPUR's source room number (49) 1:1, but the level guard
# still applies: without it, any level whose map happens to route an exit
# to room 37 incorrectly drops the player into the bar. Bug: confirmed
# live -- moving to room 49 on a different level triggered the bar.
_BAR_LEVEL   = 1
_BAR_ROOM    = 37   # Wall Bar & Grill
_SHOPPE_ROOM = None  # Shoppe is reached via rc/rt elevator, not a map room

# The Allys Guild (skip branch SPUR.MISC8.S s.guild) is a hardcoded
# interception in the original source, not a normal data-driven room exit:
# SPUR.MAIN.S: "if cl=4 if cr=42 if di=3 i$=\"SRV.GUILD\":...link dy$"
# (cl=level, cr=room, di=3 means the player typed East). Level 4 room 42
# ("A Maze Of Alleys") has no east exit in the room data for exactly this
# reason -- moving east there is caught here instead of by ctx.server._move().
_ALLY_GUILD_LEVEL = 4
_ALLY_GUILD_ROOM  = 42

# Jake's Stable: same hardcoded-interception mechanism, one level over.
# SPUR.MAIN.S: "if cl=5 if cr=157 if di=3 i$=\"JAKES\":...link dy$"
_JAKES_LEVEL = 5
_JAKES_ROOM  = 157

# Ship's Stores: level 6 room 1 ("the ship's Stores area is visible thru a
# manhole below you..") is the only rc==2/no-rt room on level 6, and would
# otherwise fall through to the generic Merchant Shoppe below -- but
# SPUR.SHIP.S is its own distinct shop program (Armory/Bank/General Store
# reused, plus SALVAGE/TR that don't exist anywhere else), not a level-6
# instance of SPUR.SHOP.S. See ship/main.py.
_SHIP_LEVEL = 6
_SHIP_STORES_ROOM = 1


def _room_has_flag(room, flag_prefix: str, direction: str) -> bool:
    """True if *room*'s flags include '<flag_prefix>_<direction word>'
    (e.g. flag_prefix='vehicle_exit', direction='w' ->
    'vehicle_exit_west'). direction must be one of n/s/e/w -- up/down
    have no directional-flag equivalent, so always returns False."""
    suffix = _DIRECTION_TO_SUFFIX.get(direction)
    if not suffix:
        return False
    return f'{flag_prefix}_{suffix}' in (getattr(room, 'flags', None) or [])


async def _check_vehicle_exit_gate(ctx: GameContext, room, direction: str, level: int) -> bool:
    """SPUR.MAIN.S's block.s/boat: if *room* has a VEHICLE_EXIT_<dir>
    marker for *direction*, leaving that way requires the player to be
    carrying the vehicle item (inflatable dinghy on levels 1-5, spacesuit
    on level 6+). Returns False (already sent a message) if the move
    should be blocked; True if it's clear to proceed (either no marker at
    all, or the player has the right item -- departure flavor + level-6
    Space Tracker bonus already sent in that case).
    """
    if not _room_has_flag(room, 'vehicle_exit', direction):
        return True

    player = ctx.player
    if player.query_flag(PlayerFlags.MOUNTED):
        # SPUR.MAIN.S (skip's branch): "Must DISMOUNT first" -- a horse
        # can't follow you through an airlock/into the water any more
        # than it can into a water room (see _auto_dismount_if_needed()
        # above for the arrival-side version of this same rule).
        await ctx.send('You must dismount first.')
        return False

    item_id = _SPACESUIT_ID if level >= 6 else _DINGHY_ID
    vehicle_name = 'spacesuit' if level >= 6 else 'dinghy'
    # id_number is only unique within its own category (weapons/items/
    # rations each number independently -- items.py:364); without the
    # category filter, _DINGHY_ID (#74) collided with ration #74
    # ISSUE#92667 LIQUID, letting that ration substitute for a real dinghy.
    from items import ItemCategory
    if not player.inventory.find(item_id=item_id, category=str(ItemCategory.ITEM)):
        await ctx.send(f"Not without a {vehicle_name}!")
        return False

    verb = 'You put on your spacesuit..' if level >= 6 else 'You shove the dinghy into the water..'
    lines = [verb]
    if level >= 6:
        if player.inventory.find(item_id=_SPACE_TRACKER_ID):
            lines.append('The space tracker powers up! (Giving galactic space coordinates.)')
        else:
            lines.append("(Too bad you don't have a space tracker..)")
    await ctx.send(lines)
    return True


async def _auto_dismount_if_needed(ctx: GameContext) -> None:
    """After a move, drop the player off their horse if it's no longer valid
    or if they've walked into a water room (SPUR.COMBAT.S:74 -- water rooms
    need a Boat, not a horse). No-op if the player isn't currently mounted.
    """
    player = ctx.player
    if not player.query_flag(PlayerFlags.MOUNTED):
        return

    from bar.allies import find_mount
    if find_mount(player) is None:
        player.clear_flag(PlayerFlags.MOUNTED)
        player.unsaved_changes = True
        await ctx.send('Your horse is gone -- you find yourself on foot.')
        return

    game_map = getattr(ctx.server, 'game_map', None)
    level    = getattr(player, 'map_level', 1) or 1
    room_no  = getattr(ctx.client, 'room', 1) or 1
    room     = game_map.get_room(int(level), int(room_no)) if game_map else None
    room_flags = getattr(room, 'flags', None) or [] if room else []
    if any(f in _WATER_FLAGS for f in room_flags):
        player.clear_flag(PlayerFlags.MOUNTED)
        player.unsaved_changes = True
        await ctx.send('Your horse balks at the water -- you dismount.')


async def _enter_shoppe(ctx: GameContext) -> None:
    """Player takes the elevator down to the Merchant Shoppe."""
    from shoppe.main import main as shoppe_main
    await shoppe_main(ctx)
    await ctx.server._show_room(ctx)


async def _enter_ship_stores(ctx: GameContext) -> None:
    """Player climbs down the manhole into the Ship's Stores (level 6,
    room 1's rc==2 down-exit -- SPUR.SHIP.S's own copy of the shop
    program, not the regular Merchant Shoppe)."""
    from ship.main import main as ship_main
    await ship_main(ctx)
    await ctx.server._show_room(ctx)


async def _enter_allies_guild(ctx: GameContext) -> None:
    """Player finds Bubba's Allys Guild down the alley (level 4, room 42, east)."""
    from street.allies_guild import main as allies_guild_main
    await allies_guild_main(ctx)
    await ctx.server._show_room(ctx)


async def _enter_jakes_stable(ctx: GameContext) -> None:
    """Player finds Jake's Stable (level 5, room 157, east)."""
    from street.jakes import main as jakes_main
    await jakes_main(ctx)
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
               'n', 's', 'e', 'w', 'u', 'd', 'a',
               'north', 'south', 'east', 'west', 'up', 'down']
    modes   = {Mode.GAME}
    counts_as_move = True

    help = Help(
        summary     = 'Move in a compass direction.',
        description = (
            'Use single-letter shortcuts (n, s, e, w, u, d), full words '
            '(north, south, east, west, up, down), or "go <direction>". '
            'PREFS (\'W\') can switch w/a/s/d to mean north/west/south/east '
            'instead.'
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

        # w/a/s/d are ambiguous between the two keymaps (only 's' agrees),
        # so under the alt keymap they take priority over _DIR_ALIASES for
        # exactly those four letters; every other token (full words, n, u,
        # d as a full word "down", etc.) is unambiguous and resolves the
        # same regardless of the player's keymap choice.
        direction = None
        if token in _WASD_ALIASES and getattr(ctx.player.command_settings, 'wasd_movement', False):
            direction = _WASD_ALIASES.get(token)
        else:
            direction = _DIR_ALIASES.get(token)
        if not direction:
            hint = 'w/a/s/d/u' if getattr(ctx.player.command_settings, 'wasd_movement', False) else 'n/s/e/w/u/d'
            await ctx.send(f'Go where? ({hint})')
            return CommandResult.fail('No direction.', error='no_direction')

        # Check for special exits before normal movement
        game_map = getattr(ctx.server, 'game_map', None)
        room_no  = getattr(ctx.client, 'room', 1) or 1
        player_level = getattr(ctx.player, 'map_level', 1) or 1

        # TODO: handle live monster blocking player's movement

        # Allys Guild: hardcoded level/room/direction interception (see
        # _ALLY_GUILD_LEVEL / _ALLY_GUILD_ROOM above), matching SPUR's own
        # hardcoded check rather than a data-driven room exit.
        if (direction == 'e' and player_level == _ALLY_GUILD_LEVEL
                and int(room_no) == _ALLY_GUILD_ROOM):
            await _enter_allies_guild(ctx)
            return CommandResult.ok()

        # Jake's Stable: same hardcoded interception (see _JAKES_LEVEL / _JAKES_ROOM).
        if (direction == 'e' and player_level == _JAKES_LEVEL
                and int(room_no) == _JAKES_ROOM):
            await _enter_jakes_stable(ctx)
            return CommandResult.ok()

        room = game_map.get_room(player_level, int(room_no)) if game_map else None

        if room:
            # Vehicle-launch gate (SPUR.MAIN.S's block.s/boat) -- runs
            # before any exit is resolved, matching SPUR's own ordering.
            # Only fires if this room+direction actually has the marker;
            # every other room is untouched.
            if not await _check_vehicle_exit_gate(ctx, room, direction, player_level):
                return CommandResult.fail('Blocked.', error='vehicle_required')

            exits = getattr(room, 'exits', {})

            # rc/rt transport system: rc=1 -> Up, rc=2 -> Down (no normal exit
            # key). rt==0 means the shoppe elevator; rt>0 is a real up/down
            # staircase to that room number on the same level (labyrinth
            # ladders, pits, etc.) -- only the rt==0 case goes to the shoppe
            # here. A nonzero rt falls through to ctx.server._move(), which
            # also consults rc/rt when resolving the destination.
            rc = int(exits.get('rc', 0) or 0)
            rt = int(exits.get('rt', 0) or 0)

            # Win/escape check (SPUR.MISC.S:454 "travel3"/"no.shop": going
            # Up while on level 6 links to spur.misc7's win check instead
            # of a normal level transition). Checked before the rc==1
            # fallthrough below, which would otherwise just walk the
            # player to room rt on the same level.
            if direction == 'u' and rc == 1 and player_level == 6:
                from victory import declare_victory, evaluate_victory
                result = evaluate_victory(ctx.player)
                await ctx.send(*result.lines)
                if result.won:
                    await ctx.send(*declare_victory(ctx.player))
                return CommandResult.ok()

            if (direction == 'u' and rc == 1) or (direction == 'd' and rc == 2):
                if not rt:
                    if player_level == _SHIP_LEVEL and int(room_no) == _SHIP_STORES_ROOM:
                        await _enter_ship_stores(ctx)
                    else:
                        await _enter_shoppe(ctx)
                    return CommandResult.ok()

            # Special destination: entering the bar
            dest = room.get_exit(direction)
            if not dest and rt and ((direction == 'u' and rc == 1) or (direction == 'd' and rc == 2)):
                dest = rt
            if dest and int(dest) == _BAR_ROOM and player_level == _BAR_LEVEL:
                await _enter_bar(ctx)
                return CommandResult.ok()

            # Guild-aligned rooms trigger the guild HQ.
            if dest:
                dest_room = game_map.get_room(player_level, int(dest)) if game_map else None
                align = getattr(dest_room, 'alignment', None) if dest_room else None
                _GUILD_KEY = {
                    RoomAlignment.CLAW:  'CLAW',
                    RoomAlignment.SWORD: 'SWORD',
                    RoomAlignment.FIST:  'FIST',
                }
                gkey = _GUILD_KEY.get(align)
                if gkey:
                    await _enter_guild_hq(ctx, gkey)
                    return CommandResult.ok()

        await ctx.server._move(ctx, direction)
        await _auto_dismount_if_needed(ctx)
        return CommandResult.ok()
