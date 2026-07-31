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
from terminal import ANSIGraphicsChars as _Box

_BFS_DEPTH = 2
_DIRECTIONS = ('north', 'south', 'east', 'west')
_DIR_ABBR = {'north': 'N', 'south': 'S', 'east': 'E', 'west': 'W'}
_DIR_VECTOR = {'north': (0, -1), 'south': (0, 1), 'east': (1, 0), 'west': (-1, 0)}
_ABBR_DIR = {v: k for k, v in _DIR_ABBR.items()}

# Cell geometry for the ANSI grid renderer: each room box is a fully
# independent 7x5 (5x3 interior + its own border on all four sides) --
# boxes never share a wall or overwrite each other's color, so adjacent
# cells sit one gap cell apart (pitch = box size + gap). An exit between
# two rendered rooms draws a single connector glyph in that gap cell
# rather than punching a hole in a shared border.
_CELL_W, _CELL_H = 7, 5
_GAP = 1
_PITCH_W, _PITCH_H = _CELL_W + _GAP, _CELL_H + _GAP

# Color assigned to a room box by substring match against room.name, same
# instr()-style keyword check SPUR itself used for its "grassy" flag (see
# base_classes.py's RoomAlignment/grassy-flag docstrings). First match wins.
_KEYWORD_COLORS = [
    (('desert', 'sand', 'dune'), 'brown'),
    (('water', 'lake', 'river', 'sea', 'swamp', 'pond'), 'light_blue'),
    (('forest', 'wood', 'grove', 'jungle', 'tree'), 'green'),
    (('snow', 'ice', 'glacier', 'frost'), 'light_white'),
    (('cave', 'cavern', 'tunnel', 'mine'), 'dark_gray'),
]
_DEFAULT_ROOM_COLOR = 'light_gray'
_PLAYER_ROOM_COLOR = 'cyan'


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


def _room_color(room, *, is_player_room: bool) -> str:
    if is_player_room:
        return _PLAYER_ROOM_COLOR
    lname = room.name.lower()
    for keywords, color in _KEYWORD_COLORS:
        if any(kw in lname for kw in keywords):
            return color
    return _DEFAULT_ROOM_COLOR


def _grid_positions(visited: dict[int, list[str]]) -> dict[int, tuple[int, int]]:
    """Derive relative (col, row) grid coordinates for every room found by
    _nearby_rooms(), by summing unit direction vectors along each room's
    shortest BFS path from the player (at (0, 0)). This sidesteps needing
    a map_width grid stride (see this module's docstring) -- the BFS
    already gives us a direction path per room, which is all a coordinate
    system needs."""
    positions: dict[int, tuple[int, int]] = {}
    for rn, path in visited.items():
        col = row = 0
        for abbr in path:
            dc, dr = _DIR_VECTOR[_ABBR_DIR[abbr]]
            col += dc
            row += dr
        positions[rn] = (col, row)
    return positions


def _fill_room_box(canvas, r0: int, c0: int, room, occupied: bool, color: str) -> None:
    m = 'M' if room.monster else ' '
    i = 'I' if room.item else ' '
    w = 'W' if room.weapon else ' '
    f = 'F' if room.food else ' '
    p = 'P' if occupied else ' '
    top    = [_Box.CORNER_UPPER_LEFT, _Box.HORIZONTAL_LINE, _Box.HORIZONTAL_LINE,
              _Box.HORIZONTAL_LINE, _Box.HORIZONTAL_LINE, _Box.HORIZONTAL_LINE, _Box.CORNER_UPPER_RIGHT]
    row0   = [_Box.VERTICAL_LINE, m, ' ', ' ', ' ', i, _Box.VERTICAL_LINE]
    row1   = [_Box.VERTICAL_LINE, ' ', ' ', p, ' ', ' ', _Box.VERTICAL_LINE]
    row2   = [_Box.VERTICAL_LINE, w, ' ', ' ', ' ', f, _Box.VERTICAL_LINE]
    bottom = [_Box.CORNER_LOWER_LEFT, _Box.HORIZONTAL_LINE, _Box.HORIZONTAL_LINE,
              _Box.HORIZONTAL_LINE, _Box.HORIZONTAL_LINE, _Box.HORIZONTAL_LINE, _Box.CORNER_LOWER_RIGHT]
    for dr, chars in enumerate((top, row0, row1, row2, bottom)):
        for dc, ch in enumerate(chars):
            canvas[r0 + dr][c0 + dc] = (str(ch), color)


_OPPOSITE = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}

# One-way-exit arrow shown in the middle of a doorway's tee gap, keyed by
# the direction of travel it actually permits (a two-way exit leaves this
# slot blank, matching Ryan's original "-| |-" spec).
_ONE_WAY_ARROW = {'north': '↑', 'south': '↓', 'east': '→', 'west': '←'}


def _cut_exit_gaps(canvas, rooms: dict[int, object], rn: int,
                    r0: int, c0: int, color: str) -> None:
    """Cut a tee-flanked doorway gap directly into this room's own border
    for each real exit -- '-| |-' (Ryan's spec) on the top/bottom edge for
    north/south, the same shape rotated 90 degrees on the left/right edge
    for east/west -- instead of floating the gap in the empty space
    between boxes. Boxes still never share or overwrite each other's
    wall: each room only ever cuts into its own four edges, regardless of
    whether the neighbor on the other side of the gap is even rendered.
    Exits are directional in this game (one-way passages exist), so each
    edge is checked independently: if the destination room (when it's
    part of this render) doesn't have a matching exit back, the gap's
    middle glyph becomes an arrow showing the only direction of travel
    instead of a plain two-way opening."""
    room = rooms[rn]

    def mid_glyph(direction: str, dest: int) -> str:
        if dest not in rooms:
            return ' '  # neighbor not rendered -- can't tell one-way from two-way
        return ' ' if rooms[dest].exits.get(_OPPOSITE[direction]) == rn else _ONE_WAY_ARROW[direction]

    dest = room.exits.get('north')
    if dest:
        seq = (_Box.HORIZONTAL_LINE, _Box.RIGHT_TEE, mid_glyph('north', dest),
               _Box.LEFT_TEE, _Box.HORIZONTAL_LINE)
        for dc, ch in enumerate(seq, start=1):
            canvas[r0][c0 + dc] = (str(ch), color)

    dest = room.exits.get('south')
    if dest:
        seq = (_Box.HORIZONTAL_LINE, _Box.RIGHT_TEE, mid_glyph('south', dest),
               _Box.LEFT_TEE, _Box.HORIZONTAL_LINE)
        for dc, ch in enumerate(seq, start=1):
            canvas[r0 + _CELL_H - 1][c0 + dc] = (str(ch), color)

    dest = room.exits.get('east')
    if dest:
        seq = (_Box.BOTTOM_TEE, mid_glyph('east', dest), _Box.TOP_TEE)
        for dr, ch in enumerate(seq, start=1):
            canvas[r0 + dr][c0 + _CELL_W - 1] = (str(ch), color)

    dest = room.exits.get('west')
    if dest:
        seq = (_Box.BOTTOM_TEE, mid_glyph('west', dest), _Box.TOP_TEE)
        for dr, ch in enumerate(seq, start=1):
            canvas[r0 + dr][c0] = (str(ch), color)


def _serialize_canvas_row(row) -> str:
    """Turn a row of (char, color) cells into a |token|-marked-up string --
    reverse_on/reverse_off bracket each colored run so ANSI clients render
    the box in reverse video (see ANSI_COLOR_CODES in formatting.py);
    uncolored cells (exit gaps) pass through as plain characters."""
    parts = []
    cur_color = None
    for ch, color in row:
        if color != cur_color:
            if cur_color is not None:
                parts.append('|reverse_off||reset|')
            if color is not None:
                parts.append(f'|{color}||reverse_on|')
            cur_color = color
        parts.append(ch)
    if cur_color is not None:
        parts.append('|reverse_off||reset|')
    return ''.join(parts)


def render_ansi_grid(ctx: GameContext, game_map, level: int, player, depth: int) -> list[str]:
    """Render the nearby-rooms BFS as a colored grid of boxes (ANSI only
    for now -- see commands/map.py's module docstring / MEMORY for the
    PETSCII follow-up)."""
    visited = _nearby_rooms(game_map, level, player.map_room, depth)
    positions = _grid_positions(visited)

    cols = [c for c, _ in positions.values()]
    rows = [r for _, r in positions.values()]
    min_col, min_row = min(cols), min(rows)
    width  = (max(cols) - min_col + 1) * _PITCH_W - _GAP
    height = (max(rows) - min_row + 1) * _PITCH_H - _GAP
    canvas = [[(' ', None) for _ in range(width)] for _ in range(height)]

    room_players = getattr(ctx.server, 'room_players', {})
    rooms = {}
    for rn, (col, row) in positions.items():
        room = game_map.get_room(level, rn)
        if room:
            rooms[rn] = room

    for rn, room in rooms.items():
        col, row = positions[rn]
        r0, c0 = (row - min_row) * _PITCH_H, (col - min_col) * _PITCH_W
        occupied = bool(room_players.get(rn))
        color = _room_color(room, is_player_room=(rn == player.map_room))
        _fill_room_box(canvas, r0, c0, room, occupied, color)
        _cut_exit_gaps(canvas, rooms, rn, r0, c0, color)

    lines = [_serialize_canvas_row(canvas_row) for canvas_row in canvas]
    lines.append('')
    for rn in sorted(rooms, key=lambda n: (positions[n][1], positions[n][0])):
        marker = '|cyan|@|reset|' if rn == player.map_room else ' '
        lines.append(f'{marker} {rooms[rn].name}')
    lines.append('')
    lines.append('|red|M|reset|=monster |yellow|I|reset|=item |yellow|W|reset|=weapon '
                 '|green|F|reset|=food |cyan|P|reset|=player(s) |cyan|@|reset|=you')
    lines.append('an arrow (↑↓→←) in a doorway marks a one-way exit '
                 '-- passable only in the direction it points')
    return lines


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
        usage    = [
            ('map', 'Show nearby rooms.'),
            ('map grid', 'Show nearby rooms as a colored grid of boxes.'),
        ],
        notes = [
            'Only available to the Ranger class, and only from character '
            'level 3 onward (SPUR.MISC5.S\'s original xp>2 gate).',
            '"map grid" draws the same nearby rooms as connected boxes '
            '(ANSI clients only, for now) -- colored by terrain keywords '
            'in the room name, with M/I/W/F/P markers and exit gaps.',
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

        if args and args[0].lower() == 'grid':
            lines = render_ansi_grid(ctx, game_map, player.map_level, player, _BFS_DEPTH)
            await ctx.send(lines)
            return CommandResult.ok('Showed nearby rooms as a grid.')

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
