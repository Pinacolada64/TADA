"""commands/map.py — MAP: the Ranger's wilderness sense.

Ports SPUR.MISC5.S:13's '#'-bound `ranger` ability (gated `xp>2` /
character level 3+) under a real command name instead of reclaiming '#'
-- this port's '#' already belongs to the admin debug TeleportCommand
(commands/teleport.py). Original SPUR just show.file'd a static
pre-rendered map.<level> ASCII art file, printed "Room #<n>", and (level
1 only) an approximate Dwarf-location hint.

This port instead computes a live "nearby rooms" listing via BFS over
each room's own real .exits links (already-resolved destination room
numbers) -- unlike SPUR-data/level-1/map_explorer.py's standalone
render_minimap(), which needs a map_width (row/column grid stride) the
live server has never loaded for any level; map_width only exists in
the original binary D.LEVELn.TXT headers. A graph walk needs no such
metadata and works identically on all 7 levels today. Room markers
(monster/item/weapon/food) and the legend line are adapted from
map_explorer.py's _cell_contents()/legend.

Room numbers are only shown to privileged players (Admin/Dungeon
Master, same _is_privileged() check as commands/board.py/whereat.py) --
an ordinary player just gets the direction path and room name, not the
raw room number.
"""
from __future__ import annotations

from base_classes import PlayerClass
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext

_BFS_DEPTH = 2
_DIRECTIONS = ('north', 'south', 'east', 'west')
_DIR_ABBR = {'north': 'N', 'south': 'S', 'east': 'E', 'west': 'W'}


def _is_privileged(player) -> bool:
    return bool(player.query_flag(PlayerFlags.ADMIN) or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def _nearby_rooms(game_map, level: int, start_room: int, depth: int) -> dict[int, list[str]]:
    """BFS out from start_room over cardinal exits only (rc/rt -- up/down,
    shoppe transports -- aren't spatial neighbors, so they're left out of
    the walk). Returns {room_number: [direction abbreviations taken to
    reach it]}, including start_room itself (mapped to an empty path)."""
    visited: dict[int, list[str]] = {start_room: []}
    frontier = [start_room]
    for _ in range(depth):
        next_frontier = []
        for rn in frontier:
            room = game_map.get_room(level, rn)
            if not room:
                continue
            for d in _DIRECTIONS:
                dest = room.exits.get(d)
                if not dest or dest in visited:
                    continue
                visited[dest] = visited[rn] + [_DIR_ABBR[d]]
                next_frontier.append(dest)
        frontier = next_frontier
    return visited


def _room_markers(room) -> str:
    return ''.join([
        '|red|M|reset|'    if room.monster else ' ',
        '|yellow|I|reset|' if room.item    else ' ',
        '|yellow|W|reset|' if room.weapon  else ' ',
        '|green|F|reset|'  if room.food    else ' ',
    ])


def _dwarf_hint(game_map, level: int, start_room: int) -> str | None:
    """Approximate Dwarf-location flavor line, level 1 only (SPUR.MISC5.S's
    `ranger` subroutine) -- a real BFS distance (unbounded, not capped at
    _BFS_DEPTH) bucketed into vague proximity tiers rather than pointing
    straight at his room, matching SPUR's "approximate" framing rather
    than just letting him show up as a plain M marker if he happens to
    already be within the nearby-rooms listing."""
    from encounters.dwarf import current_room, is_placed
    if level != 1 or not is_placed():
        return None
    dwarf_room = current_room()

    visited: dict[int, int] = {start_room: 0}
    frontier = [start_room]
    distance = None
    steps = 0
    while frontier and distance is None and steps < 200:
        steps += 1
        next_frontier = []
        for rn in frontier:
            if rn == dwarf_room:
                distance = visited[rn]
                break
            room = game_map.get_room(level, rn)
            if not room:
                continue
            for d in _DIRECTIONS:
                dest = room.exits.get(d)
                if not dest or dest in visited:
                    continue
                visited[dest] = visited[rn] + 1
                next_frontier.append(dest)
        if distance is not None:
            break
        frontier = next_frontier

    if distance is None:
        return "Your senses find no trace of the Dwarf on this level."
    if distance == 0:
        return "|red|You feel the Dwarf's presence right here!|reset|"
    if distance <= 2:
        return '|yellow|The Dwarf is close by -- tread carefully.|reset|'
    if distance <= 5:
        return 'You sense the Dwarf somewhere not too far off.'
    return 'You sense the Dwarf lurking somewhere deeper in these tunnels.'


class MapCommand(Command):
    name  = 'map'
    modes = {Mode.GAME}

    help = Help(
        summary = "Ranger wilderness sense -- nearby rooms within a few steps.",
        description = (
            "Rangers of experience level 3 or higher can sense the dungeon "
            "layout around them: every room within a couple of steps of "
            "where you're standing, the direction path to reach it, and "
            "whether it holds a monster, item, weapon, or food. On level 1, "
            "also gives an approximate sense of the Dwarf's whereabouts."
        ),
        category = HelpCategory.GENERAL,
        usage    = [('map', 'Show nearby rooms.')],
        notes = [
            'Only available to the Ranger class, and only from character '
            'level 3 onward (SPUR.MISC5.S\'s original xp>2 gate).',
        ],
        admin_notes = [
            'Admins/DMs additionally see each nearby room\'s number -- '
            'ordinary players just get the direction path and name.',
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player

        if player.char_class != PlayerClass.RANGER:
            await ctx.send('Only a Ranger has the wilderness sense for this.')
            return CommandResult.fail('Not a Ranger.', error='wrong_class')
        if player.xp_level < 3:
            await ctx.send("Your Ranger senses aren't sharp enough yet -- try again at level 3.")
            return CommandResult.fail('Not experienced enough.', error='too_low_level')

        game_map = getattr(ctx.server, 'game_map', None)
        start = game_map.get_room(player.map_level, player.map_room) if game_map else None
        if not start:
            await ctx.send('You lose your bearings -- no map data here.')
            return CommandResult.fail('No room data.', error='no_map')

        visited = _nearby_rooms(game_map, player.map_level, player.map_room, _BFS_DEPTH)
        privileged = _is_privileged(player)

        if privileged:
            lines = ['', f'|yellow|Room #{player.map_room}|reset|  ({start.name})', '']
        else:
            lines = ['', f'|yellow|{start.name}|reset|', '']
        others = sorted(
            (rn for rn in visited if rn != player.map_room),
            key=lambda rn: (len(visited[rn]), visited[rn]),
        )
        if not others:
            lines.append('  (no explored exits nearby)')
        for rn in others:
            room = game_map.get_room(player.map_level, rn)
            path = ','.join(visited[rn])
            if privileged:
                lines.append(f'  {path:<6} #{rn:<4} {_room_markers(room)}  {room.name}')
            else:
                lines.append(f'  {path:<6} {_room_markers(room)}  {room.name}')
        lines.append('')
        lines.append('|red|M|reset|=monster |yellow|I|reset|=item '
                     '|yellow|W|reset|=weapon |green|F|reset|=food')

        hint = _dwarf_hint(game_map, player.map_level, player.map_room)
        if hint:
            lines.append('')
            lines.append(hint)

        await ctx.send(lines)
        return CommandResult.ok('Showed nearby rooms.')
