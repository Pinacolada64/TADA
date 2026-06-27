#!/usr/bin/env python3
"""
tada_level_builder.py — All-in-one TADA level JSON generator.

Pipeline:
  1. Parse D.LEVEL{N}.TXT  → title, grid dimensions, room-number bitfield
  2. Decompress ROOM_LEVEL{N}.TXT via gbbsmsgtool logic → Msg-NNNN in memory
  3. Zip Msg-K with the Kth set bit → correct room number
  4. Parse each message (name/flags/stats CSV + description lines)
  5. Write level-{N}.json

Usage:
    # Single level (auto-detect filenames):
    python tada_level_builder.py --level 1

    # Explicit files:
    python tada_level_builder.py --header D.LEVEL1.TXT --room ROOM_LEVEL1.TXT --output level-1.json

    # All 7 levels at once (files must follow naming convention):
    python tada_level_builder.py --all --input-dir ./data --output-dir ./json

    # Keep intermediate Msg-*.txt files for inspection:
    python tada_level_builder.py --level 2 --keep-msgs
"""

import argparse
import json
import re
import struct
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ── Enums & constants ─────────────────────────────────────────────────────────

class RoomAlignment(Enum):
    NEUTRAL   = "neutral"
    FREE_FIRE = "free_fire"
    FIST      = "fist"
    CLAW      = "claw"
    SWORD     = "sword"
    HQ        = "hq"

class RoomFlag(Enum):
    BLOCK_MOVE_NORTH  = "block_north"
    BLOCK_MOVE_EAST   = "block_east"
    BLOCK_MOVE_SOUTH  = "block_south"
    BLOCK_MOVE_WEST   = "block_west"
    WATER             = "water"          # @@
    WATER_WITH_RAPIDS = "water_rapids"   # @@!
    SNOW              = "snow"           # **
    RADIATION         = "radiation"      # &  (single)
    RADIATION_EXTREME = "radiation_extreme"  # &&
    HIDDEN_EXIT_EAST  = "hidden_exit_east"   # ->
    HIDDEN_EXIT_WEST  = "hidden_exit_west"   # <-
    DARK              = "dark"           # #!
    EXIT_DIRECTION_1  = "exit_direction_1"   # +@1
    EXIT_DIRECTION_2  = "exit_direction_2"   # +@2
    EXIT_DIRECTION_3  = "exit_direction_3"   # +@3
    EXIT_DIRECTION_4  = "exit_direction_4"   # +@4

# Alignment suffix symbols found in raw name fields
ALIGNMENT_SYMBOLS = {
    '+':      RoomAlignment.FREE_FIRE,
    '\\|/':   RoomAlignment.CLAW,
    '-}----': RoomAlignment.SWORD,
    '=[]':    RoomAlignment.FIST,
    'HQ':     RoomAlignment.HQ,
}

# Pipe-flag token -> RoomFlag mapping
# Order matters: longer/more-specific tokens first
PIPE_FLAGS = [
    ('@@!',      RoomFlag.WATER_WITH_RAPIDS),
    ('@@',       RoomFlag.WATER),
    ('**-',      RoomFlag.SNOW),          # ** with hidden exit west
    ('**',       RoomFlag.SNOW),
    ('#!',       RoomFlag.DARK),
    ('->',       RoomFlag.HIDDEN_EXIT_EAST),
    ('<-',       RoomFlag.HIDDEN_EXIT_WEST),
    ('&&',       RoomFlag.RADIATION_EXTREME),
    ('&',        RoomFlag.RADIATION),
    ('+@1',      RoomFlag.EXIT_DIRECTION_1),
    ('+@2',      RoomFlag.EXIT_DIRECTION_2),
    ('+@3',      RoomFlag.EXIT_DIRECTION_3),
    ('+@4',      RoomFlag.EXIT_DIRECTION_4),
]

DIRECTION_FLAGS = {
    'N': RoomFlag.BLOCK_MOVE_NORTH,
    'E': RoomFlag.BLOCK_MOVE_EAST,
    'S': RoomFlag.BLOCK_MOVE_SOUTH,
    'W': RoomFlag.BLOCK_MOVE_WEST,
}

EXIT_KEYS = ['north', 'south', 'east', 'west', 'rc', 'rt']


# ── Level header parser ───────────────────────────────────────────────────────

@dataclass
class LevelHeader:
    title: str
    total_rooms: int
    map_width: int
    map_height: int
    room_numbers: list   # ordered list of room numbers that exist (from bitfield)
    raw_map_data: bytes

    @classmethod
    def read(cls, filename: Path) -> "LevelHeader":
        data = filename.read_bytes()
        parts = data.split(b'\xac')   # 0xAC = CR with high bit set

        title       = parts[0].decode('ascii', errors='replace').strip()
        total_rooms = int(parts[1].decode('ascii', errors='replace').strip())

        remainder = parts[2]
        cr_pos    = remainder.find(b'\r')
        map_width = int(remainder[:cr_pos].decode('ascii', errors='replace').strip())
        map_data  = remainder[cr_pos + 1:].rstrip(b'\x00')

        map_height   = total_rooms // map_width
        bytes_needed = (total_rooms + 7) // 8
        block1       = map_data[:bytes_needed]

        # Decode block 1 as MSB-first bitfield
        bits = []
        for byte in block1:
            for bit in range(7, -1, -1):
                bits.append((byte >> bit) & 1)

        room_numbers = [i + 1 for i, b in enumerate(bits[:total_rooms]) if b]

        return cls(
            title=title,
            total_rooms=total_rooms,
            map_width=map_width,
            map_height=map_height,
            room_numbers=room_numbers,
            raw_map_data=map_data,
        )


# ── GBBS decompression (extracted from gbbsmsgtool.py) ───────────────────────

def _decode_7bit(compressed_data: bytes) -> str:
    """Decode 7-bit packed GBBS data to ASCII text."""
    result = []
    i = 0
    while i + 6 < len(compressed_data):
        bytes_7 = compressed_data[i:i + 7]
        char8 = 0
        chars = []
        for b in bytes_7:
            char8 = (char8 >> 1) | ((b & 0x80) >> 0)
            chars.append(b & 0x7F)
        char8 = char8 >> 1
        chars.append(char8)
        for c in chars:
            if c == 0:
                return bytes(result).decode('ascii', errors='replace').replace('\r', '\n')
            result.append(c)
        i += 7
    return bytes(result).decode('ascii', errors='replace').replace('\r', '\n')


def _follow_chain(data: bytes, start_block: int, total_blocks: int,
                  data_offset: int) -> str:
    """Follow a GBBS block chain and return concatenated decoded text."""
    parts = []
    current = start_block
    visited = set()
    first = True

    while current != 0 and current not in visited:
        visited.add(current)
        offset = data_offset + (current - 1) * 128
        if offset + 128 > len(data) or current > total_blocks:
            break
        block_data = data[offset:offset + 126]
        next_block  = struct.unpack('<H', data[offset + 126:offset + 128])[0]
        decoded     = _decode_7bit(block_data)
        if not first:
            decoded = decoded.lstrip('\x00')
        parts.append(decoded)
        first = False
        if next_block == 0 or next_block in visited or next_block == current:
            break
        current = next_block

    text = ''.join(parts)
    null_pos = text.find('\x00')
    if null_pos >= 0:
        text = text[:null_pos]
    return text


def extract_messages(room_file: Path) -> list[str]:
    """
    Decompress a ROOM_LEVEL{N}.TXT GBBS message database.
    Returns a list of raw message strings in directory order (Msg-0001 first).
    """
    data = room_file.read_bytes()

    if len(data) < 8:
        raise ValueError(f"{room_file}: file too small to be a GBBS database")

    bitmap_blocks = data[0]
    dir_blocks    = data[1]
    bitmap_offset = 8
    dir_offset    = 8 + bitmap_blocks * 128
    data_offset   = dir_offset + dir_blocks * 128
    max_entries   = (dir_blocks * 128) // 4
    total_blocks  = (len(data) - data_offset) // 128

    messages = []
    for entry_num in range(max_entries):
        entry_off = dir_offset + entry_num * 4
        if entry_off + 4 > len(data):
            break
        entry     = data[entry_off:entry_off + 4]
        block_num = struct.unpack('<H', entry[2:4])[0]
        if block_num == 0 or block_num > total_blocks:
            continue
        text = _follow_chain(data, block_num, total_blocks, data_offset)
        if text.strip():
            messages.append(text)

    return messages


# ── Room name / flag parser ───────────────────────────────────────────────────

def parse_name_field(raw: str) -> tuple[str, RoomAlignment, list[RoomFlag]]:
    """
    Parse the raw name field from the CSV first line.

    Examples:
      'MERCHANT ANNEX +'          -> ('Merchant Annex', FREE_FIRE, [])
      'UNDERGROUND STREAM |@@'    -> ('Underground Stream', NEUTRAL, [WATER])
      'UNDERGROUND RAPIDS |@@!'   -> ('Underground Rapids', NEUTRAL, [WATER_WITH_RAPIDS])
      'THE DESERT|]S]W'           -> ('The Desert', NEUTRAL, [BLOCK_SOUTH, BLOCK_WEST])
      'DARK CAVE |@@**#! HQ'      -> ('Dark Cave', HQ, [WATER, SNOW, DARK])
    """
    flags: list[RoomFlag] = []
    alignment = RoomAlignment.NEUTRAL

    # ── Pipe-section flags e.g. |@@!  or  |]S]W  ──────────────────────────
    pipe_pos = raw.find('|')
    if pipe_pos != -1:
        pipe_content = raw[pipe_pos + 1:]
        raw          = raw[:pipe_pos]

        # Block-move direction flags: ]N ]E ]S ]W
        for letter in re.findall(r']([NESW])', pipe_content, re.IGNORECASE):
            f = DIRECTION_FLAGS.get(letter.upper())
            if f:
                flags.append(f)

        # Named flags (longer tokens first to avoid partial matches)
        remaining = re.sub(r']\w', '', pipe_content)   # remove ]DIR already handled
        for token, flag in PIPE_FLAGS:
            if token in remaining:
                flags.append(flag)
                remaining = remaining.replace(token, '', 1)

    # ── Alignment suffix (acts on the name part before the pipe) ─────────
    for symbol, align in ALIGNMENT_SYMBOLS.items():
        if symbol in raw:
            raw       = raw.replace(symbol, '').strip()
            alignment = align
            break

    name = raw.strip().title()
    return name, alignment, flags


# ── Message parser ────────────────────────────────────────────────────────────

@dataclass
class Room:
    """
    Heavily influenced by Brian J. Bernstein's work! and Claude AI!
    """
    number: int
    name: str
    room_alignment: RoomAlignment
    flags: list
    exits: dict
    monster: int
    item: int
    weapon: int
    food: int
    desc: str

    def to_dict(self) -> dict:
        return {
            "number":         self.number,
            "name":           self.name,
            "room_alignment": self.room_alignment.value,
            "flags":          [f.value for f in self.flags],
            "exits":          {k: v for k, v in self.exits.items() if v != 0},
            "monster":        self.monster,
            "item":           self.item,
            "weapon":         self.weapon,
            "food":           self.food,
            "desc":           self.desc,
        }


def parse_message(text: str, room_number: int) -> Room | None:
    """
    Parse a single GBBS message into a Room.

    Line 0: NAME[alignment][|flags],monster,item,weapon,food,N,S,E,W,rc,rt
    Lines 1+: description (joined with single spaces)
    """
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return None

    parts = lines[0].split(',')
    if len(parts) < 11:
        print(f"  Warning: room #{room_number}: unexpected CSV format, "
              f"got {len(parts)} fields (need 11). Skipping.")
        return None

    raw_name = parts[0]
    try:
        monster = int(parts[1])
        item    = int(parts[2])
        weapon  = int(parts[3])
        food    = int(parts[4])
        exits   = {k: int(v) for k, v in zip(EXIT_KEYS, parts[5:11])}
    except (ValueError, IndexError) as e:
        print(f"  Warning: room #{room_number}: could not parse stats: {e}. Skipping.")
        return None

    name, alignment, flags = parse_name_field(raw_name)
    desc = ' '.join(l.strip() for l in lines[1:] if l.strip())

    return Room(
        number=room_number,
        name=name,
        room_alignment=alignment,
        flags=flags,
        exits=exits,
        monster=monster,
        item=item,
        weapon=weapon,
        food=food,
        desc=desc,
    )


# ── Level builder ─────────────────────────────────────────────────────────────

def build_level(header_file: Path, room_file: Path, output_file: Path,
                keep_msgs: bool = False, msg_dir: Path = None,
                verbose: bool = True) -> int:
    """
    Full pipeline: header + room database -> JSON.
    Returns number of rooms written.
    """
    if verbose:
        print(f"\n{'─'*60}")
        print(f"  Header:  {header_file}")
        print(f"  Rooms:   {room_file}")
        print(f"  Output:  {output_file}")
        print(f"{'─'*60}")

    # Step 1: parse level header
    hdr = LevelHeader.read(header_file)
    if verbose:
        print(f"  Level:   {hdr.title}")
        print(f"  Grid:    {hdr.map_width} × {hdr.map_height}  "
              f"({hdr.total_rooms} slots, {len(hdr.room_numbers)} present)")

    # Step 2: decompress messages
    if verbose:
        print(f"  Decompressing {room_file.name}...")
    messages = extract_messages(room_file)
    if verbose:
        print(f"  Extracted {len(messages)} messages")

    # Step 3: validate counts
    if len(messages) != len(hdr.room_numbers):
        print(f"  WARNING: message count ({len(messages)}) != "
              f"bitfield count ({len(hdr.room_numbers)}).")
        print(f"  Using min({len(messages)}, {len(hdr.room_numbers)}) pairs.")

    # Step 4: optionally save Msg-*.txt files
    if keep_msgs and msg_dir:
        msg_dir.mkdir(parents=True, exist_ok=True)
        for i, text in enumerate(messages, 1):
            (msg_dir / f"Msg-{i:04d}.txt").write_text(text)
        if verbose:
            print(f"  Saved {len(messages)} Msg-*.txt files to {msg_dir}/")

    # Step 5: zip messages with room numbers and parse
    rooms = []
    n = min(len(messages), len(hdr.room_numbers))
    for i in range(n):
        room_no = hdr.room_numbers[i]
        room    = parse_message(messages[i], room_no)
        if room:
            rooms.append(room.to_dict())
            if verbose:
                print(f"  Room #{room_no:3d}: {room.name}  [{room.room_alignment.value}]")

    # Step 6: write JSON
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump({"rooms": rooms}, f, indent=4)

    if verbose:
        print(f"\n  ✓ Wrote {len(rooms)} rooms → {output_file}")

    return len(rooms)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="TADA level builder — converts GBBS room databases to JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single level using naming convention (looks for D.LEVEL1.TXT + ROOM_LEVEL1.TXT):
  python tada_level_builder.py --level 1

  # Explicit file paths:
  python tada_level_builder.py --header D.LEVEL2.TXT --room ROOM_LEVEL2.TXT --output level-2.json

  # All 7 levels from a data directory:
  python tada_level_builder.py --all --input-dir ./data --output-dir ./json

  # Keep intermediate Msg-*.txt for inspection:
  python tada_level_builder.py --level 1 --keep-msgs
"""
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--level',  type=int, metavar='N',
                      help="Level number (uses D.LEVEL{N}.TXT + ROOM_LEVEL{N}.TXT)")
    mode.add_argument('--header', metavar='FILE',
                      help="Explicit D.LEVEL{N}.TXT path (use with --room)")
    mode.add_argument('--all',    action='store_true',
                      help="Process all levels found in --input-dir")

    parser.add_argument('--room',       metavar='FILE',   help="Explicit ROOM_LEVEL{N}.TXT path")
    parser.add_argument('--output',     metavar='FILE',   help="Output JSON filename")
    parser.add_argument('--input-dir',  metavar='DIR',    default='.',
                        help="Directory containing level files (default: .)")
    parser.add_argument('--output-dir', metavar='DIR',    default='.',
                        help="Directory for output JSON files (default: .)")
    parser.add_argument('--keep-msgs',  action='store_true',
                        help="Save intermediate Msg-*.txt files alongside output JSON")
    parser.add_argument('--quiet',      action='store_true',
                        help="Suppress per-room output")

    args = parser.parse_args()
    verbose = not args.quiet

    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    total_rooms_written = 0

    if args.all:
        # Find all D.LEVEL{N}.TXT files in input_dir
        header_files = sorted(input_dir.glob("D.LEVEL*.TXT") or input_dir.glob("D_LEVEL*.TXT"))
        if not header_files:
            # Also try underscore variant
            header_files = sorted(input_dir.glob("D_LEVEL*.TXT"))
        if not header_files:
            print(f"No D.LEVEL*.TXT or D_LEVEL*.TXT files found in {input_dir}")
            sys.exit(1)

        for hf in header_files:
            # Extract level number from filename
            m = re.search(r'LEVEL(\d+)', hf.name, re.IGNORECASE)
            if not m:
                continue
            n = m.group(1)

            # Try both naming conventions for room file
            rf = None
            for pattern in [f"ROOM_LEVEL{n}.TXT", f"ROOM.LEVEL{n}.TXT",
                             f"ROOM_LEVEL{n}.txt", f"ROOM.LEVEL{n}.txt"]:
                candidate = input_dir / pattern
                if candidate.exists():
                    rf = candidate
                    break
            if rf is None:
                print(f"  Skipping level {n}: no matching ROOM_LEVEL{n}.TXT found")
                continue

            out = output_dir / f"level-{n}.json"
            msg_dir = (output_dir / f"msgs-level-{n}") if args.keep_msgs else None
            count = build_level(hf, rf, out, args.keep_msgs, msg_dir, verbose)
            total_rooms_written += count

        print(f"\n{'═'*60}")
        print(f"  Total rooms written across all levels: {total_rooms_written}")
        print(f"{'═'*60}")

    elif args.header:
        if not args.room:
            parser.error("--header requires --room")
        hf  = Path(args.header)
        rf  = Path(args.room)
        out = Path(args.output) if args.output else (
            output_dir / f"level-out.json"
        )
        msg_dir = (out.parent / f"msgs-{out.stem}") if args.keep_msgs else None
        build_level(hf, rf, out, args.keep_msgs, msg_dir, verbose)

    else:  # --level N
        n = args.level
        hf = None
        for pattern in [f"D.LEVEL{n}.TXT", f"D_LEVEL{n}.TXT"]:
            candidate = input_dir / pattern
            if candidate.exists():
                hf = candidate
                break
        if hf is None:
            print(f"Could not find D.LEVEL{n}.TXT or D_LEVEL{n}.TXT in {input_dir}")
            sys.exit(1)

        rf = None
        for pattern in [f"ROOM_LEVEL{n}.TXT", f"ROOM.LEVEL{n}.TXT"]:
            candidate = input_dir / pattern
            if candidate.exists():
                rf = candidate
                break
        if rf is None:
            print(f"Could not find ROOM_LEVEL{n}.TXT or ROOM.LEVEL{n}.TXT in {input_dir}")
            sys.exit(1)

        out = Path(args.output) if args.output else (output_dir / f"level-{n}.json")
        msg_dir = (out.parent / f"msgs-level-{n}") if args.keep_msgs else None
        build_level(hf, rf, out, args.keep_msgs, msg_dir, verbose)


if __name__ == '__main__':
    main()
