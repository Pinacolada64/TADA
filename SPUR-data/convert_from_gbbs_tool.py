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
    # SPUR.MAIN.S's block.s/block.s1 (~lines 160-174): despite the raw `]N`/
    # `]E`/`]S`/`]W` token, this is an ALLOW override, not a blocker -- if
    # the just-typed direction matches a `]`-flagged one, movement is
    # treated as succeeding (no "Can't go there!") rather than gated by the
    # room's normal exit-existence flags. It does NOT relocate the player,
    # though: cr (current room) is only reassigned in block.s1's own four
    # direction lines, never on this bypass path. From the player's seat
    # this still reads as "blocked" (you typed a direction and stayed put)
    # -- matches Skip's own description in file-formats.txt ("]E]S Blocks
    # travel in direction after ']'"), just naming the actual mechanism
    # (no error shown) rather than the felt outcome.
    NO_ERROR_EXIT_NORTH = "no_error_exit_north"
    NO_ERROR_EXIT_EAST  = "no_error_exit_east"
    NO_ERROR_EXIT_SOUTH = "no_error_exit_south"
    NO_ERROR_EXIT_WEST  = "no_error_exit_west"
    WATER    = "water"    # @@ -- requires Boat (lvl 1-5) or Spacesuit (lvl 6+); no flee (SPUR.COMBAT.S:74)
    WATER_WITH_ROCKS = "water_with_rocks"  # @@! -- per programming-notes/file-formats.txt

    SNOW     = "snow"     # ** -- requires Great Coat; no flee (SPUR.COMBAT.S:74)
    NO_FLEE  = "no_flee"  # << -- cannot flee from this room (SPUR.COMBAT.S:74)
    BLOCK_LEVEL_TRAVEL_SPELL = "block_level_travel_spell"  # >> -- blocks spell-based up/down
                                                            # level travel; also blocks fleeing,
                                                            # like << (file-formats.txt)
    RADIATION = "radiation"  # &
    RADIATION_EXTREME = "radiation_extreme"  # &&
    HIDDEN_EXIT_EAST = "hidden_exit_east"  # ->
    HIDDEN_EXIT_WEST = "hidden_exit_west"  # <-
    OUTER_SPACE = "outer_space"  # =+
    # SPUR.USE.S's comm label (~line 130): "if instr(\"FR\",lo$) print
    # 'You hear only static from the communicator..'". Not documented in
    # file-formats.txt -- found by tracing the communicator USE mechanic.
    # Exclusively a level 6 "Land of Oz" sub-zone marker in the real data
    # (Dark Woods/Witches Coven/Emerald City/Yellow Brick Road/Chamber Of
    # Oz -- 99 rooms, confirmed absent from every other level's raw Msg
    # text) -- likely "Faraday" (shielded from the communicator's signal),
    # matching base_classes.py's own note about this sub-zone ("the HOT
    # AIR BALLOON in 'The Land of Oz' level could allow flight").
    NO_COMM_SIGNAL = "no_comm_signal"  # FR
    HIDDEN_ITEM = "hidden_item"  # ~*
    HIDDEN_DOOR_NORTH = "hidden_door_north"  # ~*N
    HIDDEN_DOOR_EAST  = "hidden_door_east"   # ~*E
    HIDDEN_DOOR_SOUTH = "hidden_door_south"  # ~*S
    HIDDEN_DOOR_WEST  = "hidden_door_west"   # ~*W

    # SPUR.MAIN.S's `+@N` token (block.s's own boat-check, ~line 151):
    # leaving THIS room via direction N requires the player to be
    # carrying the vehicle item (inflatable dinghy #74 on levels 1-5,
    # spacesuit #122 on level 6+) -- prints departure flavor + (level 6)
    # a Space Tracker (#138) bonus line on success, or "Not without a
    # BOAT/SPACE SUIT!" and aborts the move entirely if the player lacks
    # it. Confirmed real (not dead code) via the one live instance in
    # level 6: room 277 "Air Lock" has `+@4` (west, toward the vacuum).
    VEHICLE_EXIT_NORTH = "vehicle_exit_north"
    VEHICLE_EXIT_EAST  = "vehicle_exit_east"
    VEHICLE_EXIT_SOUTH = "vehicle_exit_south"
    VEHICLE_EXIT_WEST  = "vehicle_exit_west"

    # SPUR.MAIN.S's `@@+N` token (travel1's own check, ~line 181): leaving
    # THIS room via direction N prints "You get out of the BOAT/SPACE
    # SUIT.." flavor, same wording as VEHICLE_EXIT_* but with no item
    # check and no failure path -- the room is already water/vacuum
    # (always paired with WATER/WATER_WITH_ROCKS in practice), so leaving
    # it is assumed to always require having already been using the
    # vehicle to be there at all. Confirmed real via level 6 room 276
    # "Outer Space" (`@@+3`, east, back toward the Air Lock). Per Skip's
    # file-formats.txt, `+@N`/`@@+N` are two spellings of the same
    # documented "@@+x" concept -- SPUR's own source just checks two
    # different substrings ("+@" vs "@@+") in two different code paths,
    # not a deliberate two-tier design; kept as two RoomFlag values here
    # because the two paths genuinely differ in whether they can abort
    # the move.
    VEHICLE_DEPARTURE_NORTH = "vehicle_departure_north"
    VEHICLE_DEPARTURE_EAST  = "vehicle_departure_east"
    VEHICLE_DEPARTURE_SOUTH = "vehicle_departure_south"
    VEHICLE_DEPARTURE_WEST  = "vehicle_departure_west"
    # UNKNOWN  # - (file-formats.txt says unknown too -- not resolved)
    # T (room transports you / "wave of nausea") -- "must be last flag, apparently"; not
    #   implemented as an inline_flags token because a bare "T" would false-positive-match
    #   almost any room name as a substring (e.g. "THE DESERT"). Needs a suffix-anchored
    #   check (only after the "|", as the literal last character) rather than `in`.

# Maps the letter found after ']' in the room flag string to a RoomFlag
DIRECTION_FLAGS = {
    'N': RoomFlag.NO_ERROR_EXIT_NORTH,
    'E': RoomFlag.NO_ERROR_EXIT_EAST,
    'S': RoomFlag.NO_ERROR_EXIT_SOUTH,
    'W': RoomFlag.NO_ERROR_EXIT_WEST,
}

# Maps the letter found after '~*' in the room flag string to a hidden-door RoomFlag.
HIDDEN_DOOR_FLAGS = {
    'N': RoomFlag.HIDDEN_DOOR_NORTH,
    'E': RoomFlag.HIDDEN_DOOR_EAST,
    'S': RoomFlag.HIDDEN_DOOR_SOUTH,
    'W': RoomFlag.HIDDEN_DOOR_WEST,
}

# Maps the digit found after '+@' or '@@+' to a direction -- matches SPUR's
# own di numbering (SPUR.MAIN.S:91-96: N=1, S=2, E=3, W=4) and Skip's
# file-formats.txt table for '@@+x'.
VEHICLE_EXIT_DIGITS = {
    '1': RoomFlag.VEHICLE_EXIT_NORTH,
    '2': RoomFlag.VEHICLE_EXIT_SOUTH,
    '3': RoomFlag.VEHICLE_EXIT_EAST,
    '4': RoomFlag.VEHICLE_EXIT_WEST,
}
VEHICLE_DEPARTURE_DIGITS = {
    '1': RoomFlag.VEHICLE_DEPARTURE_NORTH,
    '2': RoomFlag.VEHICLE_DEPARTURE_SOUTH,
    '3': RoomFlag.VEHICLE_DEPARTURE_EAST,
    '4': RoomFlag.VEHICLE_DEPARTURE_WEST,
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
    r"""
    Parse a raw room name like:
      'THE DESERT|]S]W'      -> ('The Desert', RoomAlignment.NEUTRAL, [BLOCK_SOUTH, BLOCK_WEST])
      'THE PLAIN +'          -> ('The Plain', RoomAlignment.FREE_FIRE, [])
      'THE OCEAN |@@!'       -> ('The Ocean', RoomAlignment.NEUTRAL, [WATER_WITH_ROCKS])
      'WOODED GLEN'          -> ('Wooded Glen', RoomAlignment.NEUTRAL, [])

    Per programming-notes/file-formats.txt (confirmed by Ryan directly): every one of
    these room-condition flags -- @@, **, <<, >>, ->, <-, &, &&, =+, ~* -- only ever
    appears AFTER a "|" in the raw name. FIX: this function used to check these tokens
    against the pre-pipe name (already truncated by the block-move-flag step below),
    so they never matched anything and were silently dropped for every room that used
    them -- confirmed against level 5 room 157 ("THE OCEAN |@@!"), which the live
    level_5.json shows with flags: [] despite the raw data. '+' (free-fire) is the one
    documented exception -- file-formats.txt says explicitly it is "not after |".

    FIX: the pipe-suffix search used to match ANY "|", including the one embedded in
    the '\|/' Claw guild alignment symbol -- e.g. 'STORAGE ROOM \|/ HQ' would get
    truncated at that pipe, leaving 'STORAGE ROOM \' (missing the rest of the symbol)
    for the ALIGNMENT_SYMBOLS check below, so Claw never matched. Confirmed: every
    level_N.json this project has generated so far has zero Claw-aligned rooms, and
    level 1 (which does have Claw territory) was the first real test of this path.
    The lookbehind below skips a "|" immediately preceded by "\" so it only matches
    the real condition-flag delimiter, not the one inside '\|/'.
    """
    flags = []
    room_alignment = RoomAlignment.NEUTRAL

    # Check for the pipe-suffix flag section: everything after "|" is a condition/
    # block-move flag, never part of the display name. (?<!\\) excludes the pipe
    # inside the '\|/' Claw alignment symbol -- see FIX note above.
    pipe_match = re.search(r'(?<!\\)\|(.+)$', raw_name)
    if pipe_match:
        raw_name = raw_name[:pipe_match.start()]
        flag_str = pipe_match.group(1)

        # Block-move flags: pipe followed by ]DIR pairs e.g. |]S]W
        for letter in re.findall(r']([NESW])', flag_str, re.IGNORECASE):
            flag = DIRECTION_FLAGS.get(letter.upper())
            if flag:
                flags.append(flag)
        remaining = re.sub(r']\w', '', flag_str)

        # Hidden-door flags: ~* followed by a direction letter, e.g. ~*E
        for letter in re.findall(r'~\*([NESW])', remaining, re.IGNORECASE):
            flag = HIDDEN_DOOR_FLAGS.get(letter.upper())
            if flag:
                flags.append(flag)
        remaining = re.sub(r'~\*[NESW]', '', remaining, flags=re.IGNORECASE)

        # Vehicle-exit flags: '@@+N' (travel1's departure-flavor-only
        # check) and '+@N' (block.s's item-gated departure check) -- two
        # different literal substrings SPUR's own source searches for in
        # two different code paths, not overlapping (see RoomFlag's own
        # comment above VEHICLE_EXIT_*/VEHICLE_DEPARTURE_*). '@@+N' is
        # checked first since it's the more specific/longer pattern;
        # stripping it here (rather than leaving the trailing digit for
        # the '@@' WATER check below) keeps 'remaining' clean for
        # whatever gets added after this.
        for digit in re.findall(r'@@\+([1-4])', remaining):
            flag = VEHICLE_DEPARTURE_DIGITS.get(digit)
            if flag:
                flags.append(flag)
        remaining = re.sub(r'@@\+[1-4]', '@@', remaining)

        for digit in re.findall(r'(?<!@)\+@([1-4])', remaining):
            flag = VEHICLE_EXIT_DIGITS.get(digit)
            if flag:
                flags.append(flag)
        remaining = re.sub(r'(?<!@)\+@[1-4]', '', remaining)

        # Traversal/restriction flags embedded in the pipe suffix.
        # Order matters: longer/more-specific tokens first to avoid partial matches
        # (e.g. '@@!' before '@@', bare '~*' only after the ~*DIR variants above).
        inline_flags = [
            ('@@!', RoomFlag.WATER_WITH_ROCKS),
            ('@@',  RoomFlag.WATER),
            ('**',  RoomFlag.SNOW),
            ('<<',  RoomFlag.NO_FLEE),
            ('>>',  RoomFlag.BLOCK_LEVEL_TRAVEL_SPELL),
            ('->',  RoomFlag.HIDDEN_EXIT_EAST),
            ('<-',  RoomFlag.HIDDEN_EXIT_WEST),
            ('&&',  RoomFlag.RADIATION_EXTREME),
            ('&',   RoomFlag.RADIATION),
            ('=+',  RoomFlag.OUTER_SPACE),
            ('FR',  RoomFlag.NO_COMM_SIGNAL),
            ('~*',  RoomFlag.HIDDEN_ITEM),
        ]
        for token, flag in inline_flags:
            if token in remaining:
                remaining = remaining.replace(token, '', 1)
                flags.append(flag)

    # Check for room alignment symbol suffix (e.g. '+', '\|/') on the pre-pipe name.
    # These are literal strings, not regex patterns, so use plain 'in' check.
    # '+' (free-fire) is documented as the one flag NOT gated behind "|".
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
      Line 1: ROOM NAME[' +' or '\\|/'][|]DIR flags],stat1,stat2,...,stat10
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