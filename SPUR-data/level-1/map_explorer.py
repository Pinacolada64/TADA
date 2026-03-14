"""
map_explorer.py — Standalone TADA map navigator and room inspector.

Parses level-1.json and D_LEVEL1.TXT (binary level header) and lets you
walk the map using cardinal directions (n/s/e/w) and inspect room contents,
exits, flags, and debug info.

Usage:
    python map_explorer.py
    python map_explorer.py --room 5       # start at room 5
    python map_explorer.py --debug        # start with debug mode on
"""

import json
import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Optional


# ── ANSI colours (no external deps) ──────────────────────────────────────────
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    MAGENTA = "\033[35m"
    DIM = "\033[2m"


def bold(s):    return f"{C.BOLD}{s}{C.RESET}"


def header(s):  return f"{C.BOLD}{C.CYAN}{s}{C.RESET}"


def warn(s):    return f"{C.YELLOW}{s}{C.RESET}"


def debug(s):   return f"{C.DIM}{C.MAGENTA}{s}{C.RESET}"


def good(s):    return f"{C.GREEN}{s}{C.RESET}"


def red(s):     return f"{C.RED}{s}{C.RESET}"


# ── Level header parser ───────────────────────────────────────────────────────
@dataclass
class LevelHeader:
    """
    Parses the binary D_LEVEL1.TXT file.
    Format: fields delimited by 0xAC (carriage return with high bit set).
      [0] Title string (ASCII)
      [1] total_rooms  — pre-computed room count (e.g. 144), stored to avoid
                         a multiply on original hardware. Equals map_width * map_width.
      [2] map_width    — rooms per row (e.g. 12), used for navigation offsets.
                         Followed immediately by binary map data.

    map_height is derived: total_rooms // map_width (e.g. 144 // 12 = 12).
    Navigation uses map_width as the row stride:
        north = current_room - map_width
        south = current_room + map_width
    """
    title: str = "Unknown"
    total_rooms: int = 0  # stored in file; width * height, pre-computed
    map_width: int = 0  # rooms per row — the navigation stride
    map_height: int = 0  # derived: total_rooms // map_width
    raw_map_data: bytes = field(default_factory=bytes)

    @classmethod
    def read(cls, filename: str) -> "LevelHeader":
        hdr = cls()
        try:
            with open(filename, 'rb') as f:
                data = f.read()
            # Split on 0xAC (high-bit carriage return)
            parts = data.split(b'\xac')
            if len(parts) >= 1:
                hdr.title = parts[0].decode('ascii', errors='replace').strip()
            if len(parts) >= 2:
                hdr.total_rooms = int(parts[1].decode('ascii', errors='replace').strip())
            if len(parts) >= 3:
                # map_width is at the start of parts[2], terminated by 0x0D
                remainder = parts[2]
                cr_pos = remainder.find(b'\r')
                if cr_pos != -1:
                    hdr.map_width = int(remainder[:cr_pos].decode('ascii', errors='replace').strip())
                    hdr.raw_map_data = remainder[cr_pos + 1:]
                else:
                    digits = b''
                    i = 0
                    while i < len(remainder) and remainder[i:i + 1].isdigit():
                        digits += remainder[i:i + 1]
                        i += 1
                    if digits:
                        hdr.map_width = int(digits.decode('ascii'))
                    hdr.raw_map_data = remainder[len(digits):]
            # Derive map_height; guard against divide-by-zero
            if hdr.map_width > 0:
                hdr.map_height = hdr.total_rooms // hdr.map_width
        except FileNotFoundError:
            print(warn(f"Warning: Level header file '{filename}' not found. Using defaults."))
        except Exception as e:
            print(warn(f"Warning: Could not parse level header: {e}"))
        return hdr


# ── Room dataclass ────────────────────────────────────────────────────────────
@dataclass
class Room:
    number: int
    name: str
    alignment: str
    flags: list
    exits: dict  # e.g. {"north": 1, "east": 1, "rc": 2, "rt": 23}
    monster: int  # index (1-based) into monsters list, 0 = none
    item: int  # index (1-based) into items list, 0 = none
    weapon: int  # index (1-based) into weapons list, 0 = none
    food: int  # index (1-based) into food list, 0 = none
    desc: str

    @classmethod
    def from_dict(cls, d: dict) -> "Room":
        return cls(
            number=d.get('number', 0),
            name=d.get('name', 'Unknown Room'),
            alignment=d.get('room_alignment', 'neutral'),
            flags=d.get('flags', []),
            exits=d.get('exits', {}),
            monster=d.get('monster', 0),
            item=d.get('item', 0),
            weapon=d.get('weapon', 0),
            food=d.get('food', 0),
            desc=d.get('desc', ''),
        )

    def exit_room_number(self, direction: str, map_width: int, total_rooms: int,
                         wrap_exits: dict = None) -> Optional[int]:
        """
        Calculate destination room number for a move in direction.
        For edge rooms, wrapping is only allowed if the room+direction
        appears in wrap_exits (derived from MAP_1.TXT).
        Returns None if the move is blocked or invalid.
        """
        if direction not in self.exits or not self.exits[direction]:
            return None

        offsets = {
            'north': -map_width,
            'south': +map_width,
            'east': +1,
            'west': -1,
        }

        on_edge = {
            'north': self.number <= map_width,
            'south': self.number > total_rooms - map_width,
            'west': self.number % map_width == 1,
            'east': self.number % map_width == 0,
        }

        if on_edge.get(direction, False):
            key = (self.number, direction)
            if wrap_exits and key in wrap_exits:
                dest = wrap_exits[key]
                logging.debug("Room %i: '%s' wraps to room %i", self.number, direction, dest)
                return dest
            else:
                logging.warning(
                    "Room %i: '%s' exit blocked -- on map edge with no wrap defined",
                    self.number, direction
                )
                return None

        dest = self.number + offsets[direction]
        if dest < 1 or dest > total_rooms:
            return None
        return dest


# ── Map loader ────────────────────────────────────────────────────────────────
def load_map(filename: str) -> dict[int, Room]:
    """Load level JSON and return a dict of {room_number: Room}."""
    with open(filename) as f:
        data = json.load(f)
    rooms = {}
    for r in data.get('rooms', []):
        room = Room.from_dict(r)
        rooms[room.number] = room
    return rooms


def load_json_list(filename: str, key: Optional[str] = None) -> list:
    """Load a JSON file that is either a list or a dict with a list inside."""
    try:
        with open(filename) as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if key and key in data:
                return data[key]
            # return first list value found
            for v in data.values():
                if isinstance(v, list):
                    return v
    except FileNotFoundError:
        pass
    except Exception as e:
        print(warn(f"Warning: could not load {filename}: {e}"))
    return []


# ── Wrap exits table (derived from MAP_1.TXT) ────────────────────────────────
def build_wrap_exits(map_width: int, total_rooms: int) -> dict:
    """
    Build the wrap-exit table for level 1 from MAP_1.TXT.
    Returns { (room_number, direction): dest_room_number }.

    East/West wraps: rows whose ASCII art line starts/ends with '-'.
    North/South wraps: columns with '|'/'^'/'v' in the top/bottom connector lines.
      '|' = two-way,  '^' = one-way north,  'v' = one-way south.
    """
    wraps = {}

    # ── East/West wraps ───────────────────────────────────────────────────────
    # (row, has_left_wrap, has_right_wrap)
    ew_rows = [
        (2, True, True),
        (5, True, True),
        (7, True, False),  # room 73 can go west->84, but 84 has no east wrap
        (8, True, True),
        (9, True, True),
        (10, True, True),
        (11, True, True),
    ]
    for row, has_left, has_right in ew_rows:
        left_room = (row - 1) * map_width + 1
        right_room = row * map_width
        if has_left:
            wraps[(left_room, 'west')] = right_room
        if has_right:
            wraps[(right_room, 'east')] = left_room

    # ── North/South wraps ─────────────────────────────────────────────────────
    # (col, top_marker, bottom_marker)
    ns_cols = [
        (2, '|', '|'),  # two-way
        (3, '^', None),  # one-way north only: room 3->135, not back
        (4, '|', '|'),  # two-way
        (6, None, '|'),  # bottom only: room 138 wraps south->6
        (8, None, 'v'),  # one-way south only: room 140->8, not back
        (10, '|', '|'),  # two-way
    ]
    for col, top_marker, bot_marker in ns_cols:
        top_room = col
        bot_room = (total_rooms - map_width) + col
        if top_marker in ('|', '^'):
            wraps[(top_room, 'north')] = bot_room
        if bot_marker in ('|', 'v'):
            wraps[(bot_room, 'south')] = top_room

    return wraps


# ── Display helpers ───────────────────────────────────────────────────────────
COMPASS = {'north': 'North', 'south': 'South', 'east': 'East', 'west': 'West'}
ALIGNMENT_COLOURS = {
    'neutral': C.RESET,
    'free_fire': C.RED,
    'fist': C.YELLOW,
    'sword': C.CYAN,
    'claw': C.MAGENTA,
    'outlaw': C.RED,
}


def alignment_str(alignment: str) -> str:
    colour = ALIGNMENT_COLOURS.get(alignment.lower(), C.RESET)
    return f"{colour}{alignment.title()}{C.RESET}"


# ── Map renderer ──────────────────────────────────────────────────────────────
# Box-drawing characters
_H = '─'
_V = '│'
_TL = '┌'
_TR = '┐'
_BL = '└'
_BR = '┘'
_TT = '┬'
_BT = '┴'
_LT = '├'
_RT = '┤'
_XX = '┼'


def _content_flags(room: "Room") -> str:
    """Return up to 2 coloured content-flag characters for a room."""
    flags = ''
    count = 0
    if room.monster and count < 2: flags += red('M'); count += 1
    if room.item and count < 2: flags += warn('I'); count += 1
    if room.weapon and count < 2: flags += warn('W'); count += 1
    if room.food and count < 2: flags += good('F'); count += 1
    flags += ' ' * (2 - count)  # pad to 2 visible chars
    return flags


def render_minimap(player_room_no: int, rooms: dict,
                   map_width: int, total_rooms: int,
                   wrap_exits: dict = None,
                   visited: set = None,
                   viewport_cols: int = 7,
                   viewport_rows: int = 5) -> str:
    """
    Render a viewport-sized minimap centred on the player's room.

    Each cell is 5 chars wide x 1 content row tall (plus shared borders).
    Exits appear as gaps in the cell walls.
    Cell interior layout: [room##] [MF] where M/I/W/F are content flags.

    Returns a multi-line string ready to print.
    """
    map_height = total_rooms // map_width

    # If no visited set provided, show all known rooms (useful for debug/testing)
    if visited is None:
        visited = set(rooms.keys())

    def num_to_cr(n):
        """Room number -> (col, row), both 0-based."""
        return ((n - 1) % map_width, (n - 1) // map_width)

    def cr_to_num(col, row):
        """(col, row) -> room number, or None if out of bounds."""
        if col < 0 or col >= map_width or row < 0 or row >= map_height:
            return None
        return row * map_width + col + 1

    def room_has_exit(rn, direction):
        r = rooms.get(rn)
        if not r:
            return False
        # Check JSON exits
        if r.exits.get(direction):
            return True
        # Check wrap exits
        if wrap_exits and (rn, direction) in wrap_exits:
            return True
        return False

    pcol, prow = num_to_cr(player_room_no)
    half_c = viewport_cols // 2
    half_r = viewport_rows // 2
    start_col = pcol - half_c
    start_row = prow - half_r

    lines = []

    for vr in range(viewport_rows):
        map_row = start_row + vr

        # ── Top border of this row of cells ───────────────────────
        top = ''
        for vc in range(viewport_cols):
            map_col = start_col + vc
            rn = cr_to_num(map_col, map_row)
            in_bounds = rn is not None
            north_exit = in_bounds and rn in visited and room_has_exit(rn, 'north')

            # Junction character at top-left of this cell
            if vr == 0 and vc == 0:
                junc = _TL
            elif vr == 0:
                junc = _TT
            elif vc == 0:
                junc = _LT
            else:
                junc = _XX

            if not in_bounds:
                wall = '     '  # off-map: no wall drawn
            elif north_exit:
                wall = _H * 2 + '  ' + _H * 2  # gap in centre for exit
            else:
                wall = _H * 5

            top += junc + wall

        top += _TR if vr == 0 else _RT
        lines.append(top)

        # ── Content row ───────────────────────────────────────────
        mid = ''
        for vc in range(viewport_cols):
            map_col = start_col + vc
            rn = cr_to_num(map_col, map_row)
            in_bounds = rn is not None
            west_exit = in_bounds and rn in visited and room_has_exit(rn, 'west')

            left_wall = ' ' if west_exit else _V

            if not in_bounds:
                interior = '     '  # off-map
            elif rn not in visited:
                interior = f"{C.DIM}  ·· {C.RESET}"  # unvisited
            else:
                room = rooms[rn]
                flags = _content_flags(room)
                if rn == player_room_no:
                    interior = f"{C.CYAN}{C.BOLD} @{rn:02d}{C.RESET} {flags}"
                else:
                    interior = f"{C.DIM}{rn:3d}{C.RESET}  {flags}"

            mid += left_wall + interior

        # Right wall of last cell in row
        last_rn = cr_to_num(start_col + viewport_cols - 1, map_row)
        east_exit = (last_rn is not None and last_rn in visited
                     and room_has_exit(last_rn, 'east'))
        mid += ' ' if east_exit else _V
        lines.append(mid)

    # ── Bottom border ─────────────────────────────────────────────
    bot = ''
    for vc in range(viewport_cols):
        map_col = start_col + vc
        map_row_b = start_row + viewport_rows - 1
        rn = cr_to_num(map_col, map_row_b)
        in_bounds = rn is not None
        south_exit = in_bounds and rn in visited and room_has_exit(rn, 'south')

        junc = _BL if vc == 0 else _BT
        wall = _H * 2 + '  ' + _H * 2 if south_exit else _H * 5
        bot += junc + wall
    bot += _BR
    lines.append(bot)

    # ── Legend ────────────────────────────────────────────────────
    lines.append('')
    lines.append(
        f"  {C.CYAN}{C.BOLD}@NN{C.RESET}=you  "
        f"{red('M')}=monster  {warn('I')}=item  "
        f"{warn('W')}=weapon  {good('F')}=food  "
        f"{C.DIM}··{C.RESET}=unvisited"
    )

    return '\n'.join(lines)


def describe_room(room: Room, rooms: dict, map_width: int, total_rooms: int,
                  items: list, weapons: list, food: list, monsters: list,
                  wrap_exits: dict = None, debug_mode: bool = False):
    """Print a full room description to stdout."""
    print()
    print("─" * 60)

    # ── Header ────────────────────────────────────────────────────
    room_tag = debug(f"  [Room #{room.number}]") if debug_mode else ""
    print(f"{header(room.name)}{room_tag}  {alignment_str(room.alignment)}")

    # ── Flags (debug) ─────────────────────────────────────────────
    if debug_mode:
        if room.flags:
            print(debug(f"  Flags: {', '.join(str(f) for f in room.flags)}"))
        else:
            print(debug("  Flags: (none)"))

    # ── Description ───────────────────────────────────────────────
    if room.desc:
        print()
        print(f"  {room.desc}")

    # ── Contents ──────────────────────────────────────────────────
    seen = []

    if room.item and 0 < room.item <= len(items):
        entry = items[room.item - 1]
        name = entry.get('name', '???') if isinstance(entry, dict) else str(entry)
        seen.append(('item', name, room.item))

    if room.weapon and 0 < room.weapon <= len(weapons):
        entry = weapons[room.weapon - 1]
        name = entry.get('name', '???') if isinstance(entry, dict) else str(entry)
        seen.append(('weapon', name, room.weapon))

    if room.food and 0 < room.food <= len(food):
        entry = food[room.food - 1]
        name = entry.get('name', '???') if isinstance(entry, dict) else str(entry)
        seen.append(('food', name, room.food))

    if room.monster and 0 < room.monster <= len(monsters):
        entry = monsters[room.monster - 1]
        name = entry.get('name', 'a creature') if isinstance(entry, dict) else str(entry)
        size = entry.get('size', '') if isinstance(entry, dict) else ''
        monster_str = f"{size} {name}".strip()
        print()
        print(f"  {red('!')} There is {red(monster_str)} here.")
        if debug_mode:
            print(debug(f"    [Monster index #{room.monster}]"))

    if seen:
        print()
        for kind, name, idx in seen:
            kind_tag = debug(f" [{kind} #{idx}]") if debug_mode else ""
            print(f"  {good('>')} You see {bold(name)}.{kind_tag}")

    # ── Exits ─────────────────────────────────────────────────────
    exits_list = []
    for direction, label in COMPASS.items():
        if room.exits.get(direction):
            dest = room.exit_room_number(direction, map_width, total_rooms, wrap_exits)
            if debug_mode and dest:
                dest_room = rooms.get(dest)
                dest_name = dest_room.name if dest_room else '?'
                exits_list.append(f"{bold(label)} {debug(f'(→ #{dest} {dest_name})')}")
            else:
                exits_list.append(bold(label))

    # rc / rt (room connection / room transport = up/down to another level or shoppe)
    rc = room.exits.get('rc', 0) or 0
    rt = room.exits.get('rt', 0) or 0
    if rc:
        direction_word = 'Up' if rc == 1 else 'Down'
        if rt:
            dest_tag = debug(f" (→ level transport #{rt})") if debug_mode else ""
            exits_list.append(f"{bold(direction_word)}{dest_tag}")
        else:
            exits_list.append(f"{bold(direction_word)} (to Shoppe)")

    if exits_list:
        print()
        print(f"  Exits: {', '.join(exits_list)}")
    else:
        print()
        print(f"  {warn('No exits.')}")

    print("─" * 60)


def print_help():
    print()
    print(bold("Commands:"))
    print("  n / north       move north")
    print("  s / south       move south")
    print("  e / east        move east")
    print("  w / west        move west")
    print("  u / up          move up (rc exit)")
    print("  d / down        move down (rc exit)")
    print("  go <number>     jump directly to room number")
    print("  look / l        redisplay current room")
    print("  map  / m        show minimap centred on your position")
    print("  debug / db      toggle debug mode")
    print("  list            list all rooms")
    print("  help / ?        show this help")
    print("  quit / q        exit")
    print()


# ── Main explorer loop ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="TADA Map Explorer")
    parser.add_argument('--room', type=int, default=1, help="Starting room number (default: 1)")
    parser.add_argument('--debug', action='store_true', help="Start with debug mode enabled")
    parser.add_argument('--map', default='level-1.json', help="Map JSON file")
    parser.add_argument('--level', default='D.LEVEL1', help="Binary level header file")
    # Optional data files — gracefully absent
    parser.add_argument('--items', default='objects.json', help="Items JSON file")
    parser.add_argument('--weapons', default='weapons.json', help="Weapons JSON file")
    parser.add_argument('--food', default='rations.json', help="Rations JSON file")
    parser.add_argument('--monsters', default='monsters.json', help="Monsters JSON file")
    args = parser.parse_args()

    # ── Resolve file paths relative to this script's directory ────
    base = os.path.dirname(os.path.abspath(__file__))

    def resolve(name):
        return os.path.join(base, name)

    # ── Load level header ──────────────────────────────────────────
    level_hdr = LevelHeader.read(resolve(args.level))
    map_width = level_hdr.map_width if level_hdr.map_width > 0 else 12  # fallback
    total_rooms = level_hdr.total_rooms if level_hdr.total_rooms > 0 else 144  # fallback
    wrap_exits = build_wrap_exits(map_width, total_rooms)

    print()
    print(header(f"  {level_hdr.title}"))
    print(f"  Map: {level_hdr.map_width} wide x {level_hdr.map_height} tall"
          f"  ({level_hdr.total_rooms} total rooms)")

    # ── Load map and data ──────────────────────────────────────────
    try:
        rooms = load_map(resolve(args.map))
        print(f"  Loaded {good(str(len(rooms)))} rooms from {args.map}")
    except FileNotFoundError:
        print(red(f"Error: map file '{args.map}' not found."))
        sys.exit(1)

    items = load_json_list(resolve(args.items), key='items')
    weapons = load_json_list(resolve(args.weapons), key='weapons')
    food = load_json_list(resolve(args.food), key='rations')
    monsters = load_json_list(resolve(args.monsters), key='monsters')

    print(f"  Data loaded — items: {len(items)}, weapons: {len(weapons)}, "
          f"food: {len(food)}, monsters: {len(monsters)}")

    # ── State ──────────────────────────────────────────────────────
    current_room_no = args.room
    debug_mode = args.debug
    visited = {current_room_no}  # rooms the player has seen

    if current_room_no not in rooms:
        print(warn(f"Room {current_room_no} not found; starting at room 1."))
        current_room_no = 1

    print_help()
    describe_room(rooms[current_room_no], rooms, map_width, total_rooms,
                  items, weapons, food, monsters, wrap_exits, debug_mode)

    # ── REPL ───────────────────────────────────────────────────────
    while True:
        try:
            raw = input(f"\n{C.BOLD}[Room {current_room_no}]>{C.RESET} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nFarewell, adventurer.")
            break

        if not raw:
            continue

        room = rooms.get(current_room_no)
        if room is None:
            print(red(f"Error: room {current_room_no} not in map data."))
            break

        # ── Navigation ─────────────────────────────────────────────
        direction = None
        if raw in ('n', 'north'):
            direction = 'north'
        elif raw in ('s', 'south'):
            direction = 'south'
        elif raw in ('e', 'east'):
            direction = 'east'
        elif raw in ('w', 'west'):
            direction = 'west'

        if direction:
            if not room.exits.get(direction):
                print(warn(f"  You can't go {direction} from here."))
            else:
                dest = room.exit_room_number(direction, map_width, total_rooms, wrap_exits)
                if dest and dest in rooms:
                    current_room_no = dest
                    visited.add(current_room_no)
                    describe_room(rooms[current_room_no], rooms, map_width, total_rooms,
                                  items, weapons, food, monsters, wrap_exits, debug_mode)
                elif dest is None:
                    print(warn(f"  That exit is on the map edge -- nowhere to go."))
                else:
                    print(warn(f"  Exit leads to room #{dest}, which is not in the map data."))
            continue

        # ── Up / Down (rc exits) ───────────────────────────────────
        if raw in ('u', 'up', 'd', 'down'):
            rc = room.exits.get('rc', 0) or 0
            rt = room.exits.get('rt', 0) or 0
            if not rc:
                print(warn("  There is no up/down exit here."))
            else:
                expected_rc = 1 if raw in ('u', 'up') else 2
                if rc != expected_rc:
                    word = 'up' if rc == 1 else 'down'
                    print(warn(f"  The vertical exit here goes {word}, not {raw}."))
                elif rt:
                    if rt in rooms:
                        current_room_no = rt
                        visited.add(current_room_no)
                        describe_room(rooms[current_room_no], rooms, map_width, total_rooms,
                                      items, weapons, food, monsters, wrap_exits, debug_mode)
                    else:
                        print(warn(f"  Transport leads to room #{rt} (not in this level's data)."))
                else:
                    print(warn("  This exit leads to the Shoppe (not implemented in explorer)."))
            continue

        # ── go <number> ────────────────────────────────────────────
        if raw.startswith('go '):
            parts = raw.split()
            if len(parts) == 2 and parts[1].isdigit():
                dest = int(parts[1])
                if dest in rooms:
                    current_room_no = dest
                    visited.add(current_room_no)
                    describe_room(rooms[current_room_no], rooms, map_width, total_rooms,
                                  items, weapons, food, monsters, wrap_exits, debug_mode)
                else:
                    print(warn(f"  Room #{dest} not found in map."))
            else:
                print(warn("  Usage: go <room number>"))
            continue

        # ── look ───────────────────────────────────────────────────
        if raw in ('look', 'l'):
            describe_room(rooms[current_room_no], rooms, map_width, total_rooms,
                          items, weapons, food, monsters, wrap_exits, debug_mode)
            continue

        # ── debug toggle ───────────────────────────────────────────
        if raw in ('debug', 'db'):
            debug_mode = not debug_mode
            state = good("ON") if debug_mode else warn("OFF")
            print(f"  Debug mode: {state}")
            describe_room(rooms[current_room_no], rooms, map_width, total_rooms,
                          items, weapons, food, monsters, wrap_exits, debug_mode)
            continue

        # ── map ────────────────────────────────────────────────────
        if raw in ('map', 'm'):
            print(render_minimap(
                current_room_no, rooms, map_width, total_rooms,
                wrap_exits=wrap_exits,
                visited=visited,
                viewport_cols=7,
                viewport_rows=5,
            ))
            continue

        # ── list rooms ─────────────────────────────────────────────
        if raw == 'list':
            print()
            print(bold(f"  {'#':>4}  {'Name':<30}  {'Alignment':<12}  Exits"))
            print("  " + "─" * 64)
            for num in sorted(rooms.keys()):
                r = rooms[num]
                exits_str = ' '.join(
                    k[0].upper() for k in ['north', 'south', 'east', 'west']
                    if r.exits.get(k)
                )
                if r.exits.get('rc'):
                    exits_str += ' ↕'
                marker = good("►") if num == current_room_no else " "
                print(f"  {marker}{num:>4}  {r.name:<30}  {r.alignment:<12}  {exits_str}")
            continue

        # ── help ───────────────────────────────────────────────────
        if raw in ('help', '?', 'h'):
            print_help()
            continue

        # ── quit ───────────────────────────────────────────────────
        if raw in ('quit', 'q', 'exit'):
            print("Farewell, adventurer.")
            break

        print(warn(f"  Unknown command: '{raw}'. Type 'help' for a list of commands."))


if __name__ == '__main__':
    # initialize logging:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')

    main()
