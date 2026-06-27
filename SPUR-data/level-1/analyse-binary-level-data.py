#!/usr/bin/env python3
"""
analyse_level_binary.py — Examine the binary D_LEVEL1.TXT level header file.

Parses the binary format, decodes the two 18-byte room bitfields, and
compares them against the ASCII map art to help reconcile room numbering.

Usage:
    python analyse_level_binary.py
    python analyse_level_binary.py --level D_LEVEL1.TXT --map MAP_1.TXT --json level-1.json
"""

import argparse
import json
import os

# ── ASCII map room lines (from MAP_1.TXT) ─────────────────────────────────────
# Each string represents one row of the 12x12 grid.
# Room characters: O M S C F d s b f  (and one-way door chars < > ^ v)
ROOM_CHARS = set('OMSCFdsbf')

ROOM_LINES = [
    " s M-M-M   O-O-O   O      ",   # row 1,  rooms  1-12
    "-O-O-O-O-O-O   d-O-O-O-O- ",   # row 2,  rooms 13-24
    "     O     O   O-O   O    ",   # row 3,  rooms 25-36
    " b   S-S O-O-O   O C-C    ",   # row 4,  rooms 37-48
    "-O-O-O S-F-F>F   O-C O O- ",   # row 5,  rooms 49-60
    " M-M-M-M F-F<F<F<O O-O-O  ",   # row 6,  rooms 61-72
    "-M-M>d-M F-d-F O-O-O-O-O  ",   # row 7,  rooms 73-84
    "-M O-O-O-O O-O-O-O M-M-d- ",   # row 8,  rooms 85-96
    "-O-O d O-O O-O-O<O d-O-O- ",   # row 9,  rooms 97-108
    "-M-M-M   O<O O-O-O   F d- ",   # row 10, rooms 109-120
    "-M-M>M-O-O>O-O<O>O-F-f O- ",   # row 11, rooms 121-132
    " M-M>M-M   O-O<O-O>O      ",   # row 12, rooms 133-144
]


def parse_level_header(filename: str) -> dict:
    """Parse the binary D.LEVEL1 file and return a dict of extracted fields."""
    with open(filename, 'rb') as f:
        data = f.read()

    parts = data.split(b'\xac')   # 0xAC = CR with high bit set
    title       = parts[0].decode('ascii', errors='replace').strip()
    total_rooms = int(parts[1].decode('ascii', errors='replace').strip())

    remainder = parts[2]
    cr_pos    = remainder.find(b'\r')
    map_width = int(remainder[:cr_pos].decode('ascii', errors='replace').strip())
    map_data  = remainder[cr_pos + 1:].rstrip(b'\x00')

    return {
        'title':       title,
        'total_rooms': total_rooms,
        'map_width':   map_width,
        'map_height':  total_rooms // map_width,
        'map_data':    map_data,
    }


def decode_bitfield(eighteen_bytes: bytes) -> list[int]:
    """Decode 18 bytes as 144 bits, MSB-first. Returns list of 0/1."""
    bits = []
    for byte in eighteen_bytes:
        for bit in range(7, -1, -1):
            bits.append((byte >> bit) & 1)
    return bits[:144]


def ascii_room_presence() -> list[int]:
    """Return 144-element list: 1 if ASCII map has a room at that grid position."""
    presence = []
    for line in ROOM_LINES:
        for col in range(1, 13):
            idx = (col - 1) * 2 + 1
            ch = line[idx] if idx < len(line) else ' '
            presence.append(1 if ch in ROOM_CHARS else 0)
    return presence


def section(title: str):
    print()
    print('─' * 60)
    print(f"  {title}")
    print('─' * 60)


def main():
    parser = argparse.ArgumentParser(description="Analyse TADA level binary file")
    parser.add_argument('--level', default='D.LEVEL1', help="Binary level header file")
    parser.add_argument('--json',  default='level-1.json', help="Level JSON file")
    args = parser.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    def resolve(f): return os.path.join(base, f)

    # ── 1. Parse header ───────────────────────────────────────────────────────
    section("1. Level header")
    hdr = parse_level_header(resolve(args.level))
    print(f"  Title:       {hdr['title']}")
    print(f"  Total rooms: {hdr['total_rooms']}")
    print(f"  Map width:   {hdr['map_width']}")
    print(f"  Map height:  {hdr['map_height']}")
    print(f"  Binary data: {len(hdr['map_data'])} bytes ({len(hdr['map_data'].rstrip(chr(0).encode()))} non-null)")

    # ── 2. Raw binary ─────────────────────────────────────────────────────────
    section("2. Raw map data (hex + binary)")
    stripped = hdr['map_data'].rstrip(b'\x00')
    print(f"  Byte  Dec   Bin       Hex")
    for i, b in enumerate(stripped):
        print(f"  {i:3d}   {b:3d}   {b:08b}   {b:02x}")

    # ── 3. Two 18-byte blocks ─────────────────────────────────────────────────
    section("3. The two 18-byte bitfield blocks")
    block1 = stripped[:18]
    block2 = stripped[18:36]
    print(f"  Block 1: {block1.hex()}")
    print(f"  Block 2: {block2.hex()}")
    print(f"  Identical: {block1 == block2}")
    if block1 != block2:
        print()
        print("  Differences:")
        for i, (a, b) in enumerate(zip(block1, block2)):
            if a != b:
                diff = a ^ b
                bit_from_msb = 7 - (diff.bit_length() - 1)
                room_slot = i * 8 + bit_from_msb + 1
                print(f"    Byte {i}: {a:08b} ({a:02x})  vs  {b:08b} ({b:02x})")
                print(f"    Differing room slot (MSB-first): {room_slot}")
                print(f"    Block 1 has bit=0, Block 2 has bit=1 for this slot")

    # ── 4. Bitfield decoded ───────────────────────────────────────────────────
    section("4. Block 1 decoded as 12x12 room bitfield")
    bits1 = decode_bitfield(block1)
    bits2 = decode_bitfield(block2)
    ascii_p = ascii_room_presence()

    print(f"  Rooms set in block 1:    {sum(bits1)}")
    print(f"  Rooms set in block 2:    {sum(bits2)}")
    print(f"  Rooms in ASCII map:      {sum(ascii_p)}")

    try:
        with open(resolve(args.json)) as f:
            jdata = json.load(f)
        json_rooms = set(r['number'] for r in jdata['rooms'])
        print(f"  Rooms in {args.json}: {len(json_rooms)}")
    except FileNotFoundError:
        json_rooms = set()
        print(f"  (JSON file not found)")

    # ── 5. Grid comparison ────────────────────────────────────────────────────
    section("5. ASCII map vs Block 1 bitfield (grid view)")
    print("         ASCII map                   Block 1 bitfield")
    print("col:    1 2 3 4 5 6 7 8 9 0 1 2      1 2 3 4 5 6 7 8 9 0 1 2")
    for row in range(12):
        a = ['#' if ascii_p[row*12+c] else '.' for c in range(12)]
        b = ['#' if bits1[row*12+c]   else '.' for c in range(12)]
        match = '==' if a == b else '!='
        print(f"row {row+1:2d}: {' '.join(a)}  {match}  {' '.join(b)}")

    # ── 6. Absent rooms ───────────────────────────────────────────────────────
    section("6. Absent rooms per block 1 bitfield (bit=0)")
    print("  Room slot  Row  Col  In JSON?")
    for i, bit in enumerate(bits1):
        if not bit:
            room = i + 1
            row  = (i // 12) + 1
            col  = (i %  12) + 1
            in_j = 'yes' if room in json_rooms else 'NO'
            print(f"  {room:4d}       {row:3d}  {col:3d}  {in_j}")

    # ── 7. Blocks differ ──────────────────────────────────────────────────────
    section("7. Positions that differ between block 1 and block 2")
    diffs = [(i, bits1[i], bits2[i]) for i in range(144) if bits1[i] != bits2[i]]
    if diffs:
        print("  Slot  Row  Col  Block1  Block2")
        for slot, b1, b2 in diffs:
            row = (slot // 12) + 1
            col = (slot %  12) + 1
            print(f"  {slot+1:4d}  {row:3d}  {col:3d}  {b1}       {b2}")
    else:
        print("  (no differences)")

    print()


if __name__ == '__main__':
    main()
