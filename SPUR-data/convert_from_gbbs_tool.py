#!/bin/env python3

import json
import re
import argparse
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# --- Enums ---

class RoomAlignment(Enum):
    """
    RoomAlignment describes the territorial affiliation of a *room* on the map,
    encoded in the raw ACOS room-name field as a suffix symbol (e.g. '+', '\\|/').

    This is distinct from GuildAlignment, which describes a *player or NPC's*
    membership in a guild. A room's alignment affects what rules apply in that
    location -- e.g. FREE_FIRE allows combat regardless of guild standing, and
    HQ marks the headquarters of whichever guild controls the room.

    Most rooms carry no suffix and default to NEUTRAL (no special rules).
    """
    NEUTRAL   = "neutral"    # no suffix -- open to all, no special rules
    FREE_FIRE = "free_fire"  # '+' suffix -- combat allowed regardless of guild
    FIST      = "fist"       # '=[]' suffix -- Fist guild territory
    CLAW      = "claw"       # '\|/' suffix -- Claw guild territory
    SWORD     = "sword"      # '-}----' suffix -- Sword guild territory
    HQ        = "hq"         # 'HQ' suffix -- headquarters of whichever guild owns the room

class GuildAlignment(Enum):
    """
    GuildAlignment describes a player or NPC's membership in one of the game's
    factions: Civilian (unguilded), Fist, Sword, Claw, or Outlaw.
    """
    CIVILIAN = "civilian"
    FIST     = "fist"
    SWORD    = "sword"
    CLAW     = "claw"
    OUTLAW   = "outlaw"

# Maps the literal symbol found in the raw ACOS source data to a RoomAlignment.
# These are input/parsing concerns only -- rendering is handled separately by
# RoomAlignment.render() based on the connected terminal's capability.
ALIGNMENT_SYMBOLS = {
    '+':       RoomAlignment.FREE_FIRE,  # Free-fire zone
    '\\|/':    RoomAlignment.CLAW,       # Claw guild symbol (backslash-pipe-slash)
    '-}----':  RoomAlignment.SWORD,      # Sword guild symbol
    '=[]':     RoomAlignment.FIST,       # Fist guild symbol
    'HQ':      RoomAlignment.HQ,         # Marker for any guild headquarters square
}

class RoomFlag(Enum):
    BLOCK_MOVE_NORTH = "block_north"
    BLOCK_MOVE_EAST  = "block_east"
    BLOCK_MOVE_SOUTH = "block_south"
    BLOCK_MOVE_WEST  = "block_west"
    WATER = "water"  # @@
    # WATER_WITH_ROCKS? # @@!
    # ROOM_58  # +@1 - exit in direction 1?
    # UNKNOWN  # -

    SNOW = "snow"  # **
    RADIATION = "radiation"  # &
    RADIATION_EXTREME = "radiation_extreme"  # &&
    HIDDEN_EXIT_EAST = "hidden_exit_east"
    HIDDEN_EXIT_WEST = "hidden_exit_west"

# Maps the letter found after ']' in the room flag string to a RoomFlag
DIRECTION_FLAGS = {
    'N': RoomFlag.BLOCK_MOVE_NORTH,
    'E': RoomFlag.BLOCK_MOVE_EAST,
    'S': RoomFlag.BLOCK_MOVE_SOUTH,
    'W': RoomFlag.BLOCK_MOVE_WEST,
}

EXIT_KEYS = ['north', 'south', 'east', 'west', 'rc', 'rt']
STAT_KEYS = ['name_csv', 'monster', 'item', 'weapon', 'food',
             'exit_n', 'exit_s', 'exit_e', 'exit_w', 'exit_rc', 'exit_rt']


# --- Dataclass ---

@dataclass
class Room:
    number: int
    name: str
    exits: dict
    desc: str
    monster: int = 0
    item: int = 0
    weapon: int = 0
    food: int = 0
    room_alignment: RoomAlignment = RoomAlignment.NEUTRAL  # FIX: was GuildAlignment.NEUTRAL (wrong type; GuildAlignment has no NEUTRAL)
    flags: list = field(default_factory=list)

    def __str__(self):
        return f'#{self.number} {self.name} [{self.room_alignment.value}]\n{self.desc}\n{self.exits}'  # FIX: was self.alignment


# --- Parsing helpers ---

def parse_name_field(raw_name: str) -> tuple[str, RoomAlignment, list[RoomFlag]]:
    """
    Parse a raw room name like:
      'THE DESERT|]S]W'  -> ('The Desert', RoomAlignment.NEUTRAL, [BLOCK_SOUTH, BLOCK_WEST])
      'THE PLAIN +'      -> ('The Plain', RoomAlignment.FREE_FIRE, [])
      'WOODED GLEN'      -> ('Wooded Glen', RoomAlignment.NEUTRAL, [])
    """
    flags = []
    room_alignment = RoomAlignment.NEUTRAL

    # Check for block-move flags: pipe followed by ]DIR pairs e.g. |]S]W
    pipe_match = re.search(r'\|(.+)$', raw_name)
    if pipe_match:
        raw_name = raw_name[:pipe_match.start()]
        flag_str = pipe_match.group(1)
        # Extract each letter after ']'
        for letter in re.findall(r'\]([NESW])', flag_str, re.IGNORECASE):
            flag = DIRECTION_FLAGS.get(letter.upper())
            if flag:
                flags.append(flag)

    # Check for room alignment symbol suffix (e.g. '+', '\|/')
    # These are literal strings, not regex patterns, so use plain 'in' check
    for symbol, align_value in ALIGNMENT_SYMBOLS.items():
        if symbol in raw_name:
            raw_name = raw_name.replace(symbol, '').strip()
            room_alignment = align_value  # FIX: was 'guild_alignment' (wrong variable, never returned)
            break

    name = raw_name.strip().title()
    return name, room_alignment, flags


def parse_room_file(filepath: Path, room_number: int) -> Room | None:
    """
    Parse a single Msg-xxxx.txt file.
    Expected format:
      Line 1: ROOM NAME[' +' or '\|/'][|]DIR flags],stat1,stat2,...,stat10
      Line 2+: Description text (multi-line, until EOF)
    """
    lines = filepath.read_text().splitlines()
    if not lines:
        return None

    # First line: name + stats CSV
    first_line = lines[0].strip()
    parts = first_line.split(',')
    if len(parts) < 11:
        print(f"  Warning: unexpected format in {filepath.name}, skipping.")
        return None

    raw_name = parts[0]
    try:
        monster, item, weapon, food = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
        exits = {k: int(v) for k, v in zip(EXIT_KEYS, parts[5:11])}
    except (ValueError, IndexError) as e:
        print(f"  Warning: could not parse stats in {filepath.name}: {e}")
        return None

    name, room_alignment, flags = parse_name_field(raw_name)
    desc = " ".join(line.strip() for line in lines[1:] if line.strip())

    return Room(
        number=room_number,
        name=name,
        exits=exits,
        desc=desc,
        monster=monster,
        item=item,
        weapon=weapon,
        food=food,
        room_alignment=room_alignment,
        flags=flags,
    )


# --- JSON serialization ---

def room_to_dict(room: Room) -> dict:
    return {
        "number": room.number,
        "name": room.name,
        "room_alignment": room.room_alignment.value,  # FIX: was room.alignment (wrong attribute name)
        "flags": [f.value for f in room.flags],
        "exits": {k: v for k, v in room.exits.items() if v != 0},
        "monster": room.monster,
        "item": room.item,
        "weapon": room.weapon,
        "food": room.food,
        "desc": room.desc,
    }


# --- Main conversion ---

def convert(input_dir: str, output_file: str):
    input_path = Path(input_dir)
    msg_files = sorted(input_path.glob("Msg-*.txt"))

    if not msg_files:
        print(f"No Msg-*.txt files found in '{input_dir}'")
        return

    rooms = []
    for filepath in msg_files:
        # Extract room number from filename e.g. Msg-0089.txt -> 89
        match = re.search(r'Msg-(\d+)\.txt', filepath.name, re.IGNORECASE)
        if not match:
            print(f"  Skipping unrecognised filename: {filepath.name}")
            continue
        room_number = int(match.group(1))
        room = parse_room_file(filepath, room_number)
        if room:
            print(f"  Processed room #{room.number}: '{room.name}' [{room.room_alignment.value}]")
            rooms.append(room_to_dict(room))

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump({"rooms": rooms}, f, indent=4)
    print(f"\nWrote {len(rooms)} rooms to '{output_file}'")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Convert GBBS room files to JSON")
    parser.add_argument('input_dir', help="Directory containing Msg-xxxx.txt files (e.g. level-1/)")
    parser.add_argument('--output', default='map_data.json', help="Output JSON filename")
    args = parser.parse_args()
    convert(args.input_dir, args.output)