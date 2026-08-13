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

from types import SimpleNamespace

from base_classes import PlayerClass
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext
from formatting import COLOR_NAME_TO_TOKEN
from terminal import ANSIGraphicsChars as _Box, ColorName
from terminal import Translation

# cbmcodecs2's petscii_c64en_lc codec has no mapping for the double-line
# glyphs _Box (ANSIGraphicsChars) uses -- '╔' etc encode()-error and
# come out as '?' on a real C64. The single-line U+2500-block glyphs below
# (same chars table.py's SINGLE/PETSCII Border presets use) round-trip
# cleanly through that codec, so PETSCII clients get these instead.
_PETSCII_BOX = SimpleNamespace(
    CORNER_UPPER_LEFT='┌', CORNER_UPPER_RIGHT='┐',
    CORNER_LOWER_LEFT='└', CORNER_LOWER_RIGHT='┘',
    HORIZONTAL_LINE='─', VERTICAL_LINE='│',
    TOP_TEE='┬', BOTTOM_TEE='┴', LEFT_TEE='├', RIGHT_TEE='┤',
)


def _box_chars(ctx: GameContext):
    if ctx.player.client_settings.translation == Translation.PETSCII:
        return _PETSCII_BOX
    return _Box

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
    (('snow', 'ice', 'glacier', 'frost'), 'white'),
    (('cave', 'cavern', 'tunnel', 'mine'), 'dark_gray'),
]
_DEFAULT_ROOM_COLOR = 'light_gray'
_PLAYER_ROOM_COLOR = 'cyan'

# Display names for the room-color legend line, one entry per
# _KEYWORD_COLORS terrain color plus the default/player colors -- kept as
# a separate list (rather than annotating _KEYWORD_COLORS itself) since
# the keyword tuples there are matched in order, not meant for display.
# ColorName gives the player-facing display text ("Dark Gray"); the
# matching |token| for actually coloring that text comes from
# formatting.COLOR_NAME_TO_TOKEN, so the two can't drift out of sync.
_COLOR_LEGEND = [
    (ColorName.BROWN,      'desert'),
    (ColorName.LIGHT_BLUE, 'water'),
    (ColorName.DARK_GREEN, 'forest'),
    (ColorName.WHITE,      'snow/ice'),
    (ColorName.DARK_GRAY,  'cave'),
    (ColorName.LIGHT_GRAY, 'other'),
    (ColorName.CYAN,       'you'),
]


def _is_privileged(player) -> bool:
    return bool(player.query_flag(PlayerFlags.ADMIN) or player.query_flag(PlayerFlags.DUNGEON_MASTER))


def _is_debug(player) -> bool:
    return bool(player.query_flag(PlayerFlags.DEBUG_MODE))


# Grid width (SPUR's `ri`, "Room Incr.") per level -- not tracked anywhere
# on the runtime Map/Room objects (see this module's own docstring), so
# it's hardcoded here from D.LEVEL{N}.TXT's own header, same source
# LEVEL_AUDIT.md's room-renumbering investigation (§17) used. Room number
# -> (row, col) is divmod(number - 1, ri), matching
# SPUR-data/level-2/tada_level_builder.py's resolve_exit_destinations()
# row-major convention (north decreases row, east increases col).
_OVERVIEW_GRID_WIDTH = {1: 12, 2: 15, 3: 10, 4: 7, 5: 20, 6: 30, 7: 10}

_OVERVIEW_ROOM_COLOR = 'light_gray'
_OVERVIEW_PLAYER_ROOM_COLOR = 'cyan'

# ANSI double-headed arrows for a gap between two grid-adjoining rooms
# that each have an exit leading into the other -- distinguishes a real
# two-way passage from a one-way one, which a lone single-direction arrow
# can't (Ryan's request). No PETSCII equivalent: cbmcodecs2's
# petscii_c64en_lc codec doesn't map '↕'/'↔' any more than it maps the
# single-direction arrows (see _PETSCII_ONE_WAY_ARROW's own comment) --
# PETSCII clients fall back to the single-direction glyph for the room
# that's "ahead" on that axis (south/east), same as if only one direction
# existed; the exit still gets an arrow, just not a bidirectional one.
_ANSI_BOTH_WAYS = {'vertical': '↕', 'horizontal': '↔'}


def render_overview(ctx: GameContext, game_map, level: int, player) -> list[str] | None:
    """Compressed birds-eye view of an entire level's grid: one reverse-
    video square per room (no monster/item/weapon/food markers -- see
    render_ansi_grid() for that), with arrow glyphs in the gap between
    each pair of grid-adjoining rooms showing whether north/east/south/
    west exits connect them -- a double-headed arrow (ANSI clients only)
    if both rooms have an exit into the other, a single-direction one if
    only one does. Up/down (rc/rt) exits aren't spatial neighbors on this
    flat grid, so they're not shown -- same reasoning _nearby_rooms()
    already documents. Returns None if this level has no known grid
    width or no rooms are loaded for it."""
    ri = _OVERVIEW_GRID_WIDTH.get(level)
    if not ri:
        return None

    rooms = getattr(game_map, 'levels', {}).get(level) or {}
    if not rooms:
        return None

    arrows = _arrow_chars(ctx)
    is_ansi = arrows is not _PETSCII_ONE_WAY_ARROW
    positions = {rn: divmod(rn - 1, ri) for rn in rooms}
    by_pos = {pos: rooms[rn] for rn, pos in positions.items()}
    max_row = max(row for row, _ in positions.values())
    max_col = max(col for _, col in positions.values())

    height = 2 * max_row + 1
    width  = 2 * max_col + 1
    canvas = [[(' ', None) for _ in range(width)] for _ in range(height)]

    for rn, room in rooms.items():
        row, col = positions[rn]
        is_player_room = level == player.map_level and rn == player.map_room
        color = _OVERVIEW_PLAYER_ROOM_COLOR if is_player_room else _OVERVIEW_ROOM_COLOR
        canvas[2 * row][2 * col] = ('@' if is_player_room else ' ', color)

    # Vertical gaps: between (row, col) and (row+1, col) -- south exit
    # from the first, north exit from the second.
    for row in range(max_row):
        for col in range(max_col + 1):
            north_room = by_pos.get((row, col))
            south_room = by_pos.get((row + 1, col))
            goes_south = bool(north_room and north_room.exits.get('south'))
            goes_north = bool(south_room and south_room.exits.get('north'))
            if goes_south and goes_north and is_ansi:
                glyph = _ANSI_BOTH_WAYS['vertical']
            elif goes_south:
                glyph = arrows['south']
            elif goes_north:
                glyph = arrows['north']
            else:
                continue
            canvas[2 * row + 1][2 * col] = (glyph, None)

    # Horizontal gaps: between (row, col) and (row, col+1) -- east exit
    # from the first, west exit from the second.
    for row in range(max_row + 1):
        for col in range(max_col):
            west_room = by_pos.get((row, col))
            east_room = by_pos.get((row, col + 1))
            goes_east = bool(west_room and west_room.exits.get('east'))
            goes_west = bool(east_room and east_room.exits.get('west'))
            if goes_east and goes_west and is_ansi:
                glyph = _ANSI_BOTH_WAYS['horizontal']
            elif goes_east:
                glyph = arrows['east']
            elif goes_west:
                glyph = arrows['west']
            else:
                continue
            canvas[2 * row][2 * col + 1] = (glyph, None)

    lines = [_serialize_canvas_row(canvas_row) for canvas_row in canvas]
    lines.append('')
    lines.append(f'|{_OVERVIEW_PLAYER_ROOM_COLOR}|@|reset|=you  '
                 f'|{_OVERVIEW_ROOM_COLOR}| |reset|=room')
    if is_ansi:
        lines.append('↑↓→←=one-way exit   ↕↔=exit in both directions')
    else:
        lines.append('^v><=exit exists that direction')
    return lines


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
        '|orange|I|reset|' if room.item    else ' ',
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


def _fill_room_box(canvas, r0: int, c0: int, room, occupied: bool, color: str,
                    box=_Box, is_player_room: bool = False) -> None:
    m = 'M' if room.monster else ' '
    i = 'I' if room.item else ' '
    w = 'W' if room.weapon else ' '
    f = 'F' if room.food else ' '
    p = '@' if is_player_room else ('P' if occupied else ' ')
    top    = [box.CORNER_UPPER_LEFT, box.HORIZONTAL_LINE, box.HORIZONTAL_LINE,
              box.HORIZONTAL_LINE, box.HORIZONTAL_LINE, box.HORIZONTAL_LINE, box.CORNER_UPPER_RIGHT]
    row0   = [box.VERTICAL_LINE, m, ' ', ' ', ' ', i, box.VERTICAL_LINE]
    row1   = [box.VERTICAL_LINE, ' ', ' ', p, ' ', ' ', box.VERTICAL_LINE]
    row2   = [box.VERTICAL_LINE, w, ' ', ' ', ' ', f, box.VERTICAL_LINE]
    bottom = [box.CORNER_LOWER_LEFT, box.HORIZONTAL_LINE, box.HORIZONTAL_LINE,
              box.HORIZONTAL_LINE, box.HORIZONTAL_LINE, box.HORIZONTAL_LINE, box.CORNER_LOWER_RIGHT]
    for dr, chars in enumerate((top, row0, row1, row2, bottom)):
        for dc, ch in enumerate(chars):
            canvas[r0 + dr][c0 + dc] = (str(ch), color)


_OPPOSITE = {'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east'}

# One-way-exit arrow shown in the middle of a doorway's tee gap, keyed by
# the direction of travel it actually permits (a two-way exit leaves this
# slot blank, matching Ryan's original "-| |-" spec).
_ONE_WAY_ARROW = {'north': '↑', 'south': '↓', 'east': '→', 'west': '←'}

# PETSCII substitute for the above: cbmcodecs2's petscii_c64en_lc codec has
# no mapping for '↓'/'→' at all, and even the '↑'/'←' that do map land on
# the up-arrow/left-arrow *keys*, not real up/down/left/right glyphs -- the
# stock C64 charset just doesn't have all four arrow directions. Until
# there's a custom charset upload to the client (see MEMORY), plain ASCII
# carets round-trip cleanly and read unambiguously in every direction.
_PETSCII_ONE_WAY_ARROW = {'north': '^', 'south': 'v', 'east': '>', 'west': '<'}


def _arrow_chars(ctx: GameContext) -> dict:
    if ctx.player.client_settings.translation == Translation.PETSCII:
        return _PETSCII_ONE_WAY_ARROW
    return _ONE_WAY_ARROW


def _cut_exit_gaps(canvas, rooms: dict[int, object], rn: int,
                    r0: int, c0: int, color: str, box=_Box, arrows=_ONE_WAY_ARROW) -> None:
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
        return ' ' if rooms[dest].exits.get(_OPPOSITE[direction]) == rn else arrows[direction]

    dest = room.exits.get('north')
    if dest:
        seq = (box.HORIZONTAL_LINE, box.RIGHT_TEE, mid_glyph('north', dest),
               box.LEFT_TEE, box.HORIZONTAL_LINE)
        for dc, ch in enumerate(seq, start=1):
            canvas[r0][c0 + dc] = (str(ch), color)

    dest = room.exits.get('south')
    if dest:
        seq = (box.HORIZONTAL_LINE, box.RIGHT_TEE, mid_glyph('south', dest),
               box.LEFT_TEE, box.HORIZONTAL_LINE)
        for dc, ch in enumerate(seq, start=1):
            canvas[r0 + _CELL_H - 1][c0 + dc] = (str(ch), color)

    dest = room.exits.get('east')
    if dest:
        seq = (box.BOTTOM_TEE, mid_glyph('east', dest), box.TOP_TEE)
        for dr, ch in enumerate(seq, start=1):
            canvas[r0 + dr][c0 + _CELL_W - 1] = (str(ch), color)

    dest = room.exits.get('west')
    if dest:
        seq = (box.BOTTOM_TEE, mid_glyph('west', dest), box.TOP_TEE)
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
    """Render the nearby-rooms BFS as a colored grid of boxes. Box-drawing
    glyphs come from _box_chars(ctx): double-line for ANSI clients,
    single-line for PETSCII (cbmcodecs2 has no mapping for the double-line
    block, see _PETSCII_BOX's comment)."""
    box = _box_chars(ctx)
    arrows = _arrow_chars(ctx)
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
        is_player_room = rn == player.map_room
        color = _room_color(room, is_player_room=is_player_room)
        _fill_room_box(canvas, r0, c0, room, occupied, color, box, is_player_room)
        _cut_exit_gaps(canvas, rooms, rn, r0, c0, color, box, arrows)

    lines = [_serialize_canvas_row(canvas_row) for canvas_row in canvas]
    lines.append('')
    for rn in sorted(rooms, key=lambda n: (positions[n][1], positions[n][0])):
        marker = '|cyan|@|reset|' if rn == player.map_room else ' '
        room_number = f'|white|#{rooms[rn].number:<3}|reset| ' if _is_privileged(player) else ''
        lines.append(f'{marker} {room_number}{rooms[rn].name}')
    lines.append('')
    lines.append('|red|M|reset|=monster |orange|I|reset|=item |yellow|W|reset|=weapon '
                 '|green|F|reset|=food |cyan|P|reset|=player(s) |cyan|@|reset|=you')
    lines.append(' '.join(
        f'|{COLOR_NAME_TO_TOKEN[color_name]}|{color_name.value}|reset|={classification}'
        for color_name, classification in _COLOR_LEGEND
    ))
    arrow_sample = '^v><' if arrows is _PETSCII_ONE_WAY_ARROW else '↑↓→←'
    lines.append(f'An arrow ({arrow_sample}) in a doorway marks a one-way exit '
                 '-- passable only in the direction it points.')
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
            ('map #grid', 'Same as "map grid".'),
            ('map #overview [<level>]', 'Debug Mode: full-level birds-eye grid.'),
        ],
        notes = [
            'Only available to the Ranger class, and only from character '
            'level 3 onward.',  # (SPUR.MISC5.S's original xp>2 gate)
            '"map grid" (or "map #grid") draws the same nearby rooms as '
            'connected boxes -- colored by terrain keywords in the room '
            'name, with M/I/W/F/@ markers, exit gaps, and a color-key '
            'line underneath. Your own room is always marked with @. '
            'Box-drawing glyphs adapt to your client: double-line for '
            'ANSI, single-line for a real Commodore/PETSCII client.',
        ],
        admin_notes = [
            "Admins/DMs additionally see each nearby room's number -- "
            'ordinary players just get the direction path and name.',
            '"map #overview [<level>]" needs Debug Mode on (not the '
            'Ranger/level-3 gate above) and shows every room on the given '
            'level (your own level if omitted) as a single reverse-video '
            'square, with arrow glyphs around it marking which of '
            'north/east/south/west have an exit. No monster/item/weapon/'
            'food markers, and no up/down exits -- a compressed grid '
            "layout, not the nearby-rooms view. Your own room shows '@'.",
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        player = ctx.player

        if args and args[0].lower().lstrip('#') == 'overview':
            if not _is_debug(player):
                await ctx.send("You need Debug Mode on for that -- see the DBG command.")
                return CommandResult.fail('Not in debug mode.', error='not_debug')

            game_map = getattr(ctx.server, 'game_map', None)
            if not game_map:
                await ctx.send('You lose your bearings -- no map data here.')
                return CommandResult.fail('No map data.', error='no_map')

            if len(args) > 1:
                try:
                    level = int(args[1])
                except ValueError:
                    await ctx.send(f'"{args[1]}" is not a level number.')
                    return CommandResult.fail('Bad level.', error='bad_level')
            else:
                level = player.map_level

            lines = render_overview(ctx, game_map, level, player)
            if lines is None:
                await ctx.send(f"No overview data for level {level}.")
                return CommandResult.fail('No overview data.', error='no_overview')
            await ctx.send([f'|yellow|Level {level} overview|reset|', ''] + lines)
            return CommandResult.ok('Showed level overview.')

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

        if args and args[0].lower().lstrip('#') == 'grid':
            lines = render_ansi_grid(ctx, game_map, player.map_level, player, _BFS_DEPTH)
            await ctx.send(lines)
            return CommandResult.ok('Showed nearby rooms as a grid.')

        visited = _nearby_rooms(game_map, player.map_level, player.map_room, _BFS_DEPTH)
        privileged = _is_privileged(player)

        if privileged:
            lines = ['', f'|yellow|Room #{player.map_room}|reset|  ({start.name})', '']
        else:
            lines = ['', f'|yellow|{start.name}|reset|', '']
        # A BFS-visited destination room number doesn't always resolve to
        # real room data (a dangling/bad exit can point at a room number
        # game_map has nothing for) -- skip those rather than crashing on
        # a None room, matching render_ansi_grid's same guard.
        others = sorted(
            (rn for rn in visited
             if rn != player.map_room and game_map.get_room(player.map_level, rn)),
            key=lambda rn: (len(visited[rn]), visited[rn]),
        )
        if not others:
            lines.append('  (no explored exits nearby)')
        for rn in others:
            room = game_map.get_room(player.map_level, rn)
            path = ','.join(visited[rn])
            if privileged:
                lines.append(f'  |yellow|{path:<6}|reset| |white|#{rn:<4}|reset| '
                             f'{_room_markers(room)}  |cyan|{room.name}|reset|')
            else:
                lines.append(f'  |yellow|{path:<6}|reset| {_room_markers(room)}  |cyan|{room.name}|reset|')
        lines.append('')
        lines.append('|red|M|reset|=monster |orange|I|reset|=item '
                     '|yellow|W|reset|=weapon |green|F|reset|=food')

        hint = _dwarf_hint(game_map, player.map_level, player.map_room)
        if hint:
            lines.append('')
            lines.append(hint)

        await ctx.send(lines)
        return CommandResult.ok('Showed nearby rooms.')
