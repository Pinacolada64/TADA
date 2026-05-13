#!/bin/env python3
"""
convert_monster_data.py

Reads monsters.txt (SPUR binary, record size 32) and writes monsters.json.

Schema per monster:
  number, status, name, size, strength, special_weapon, to_hit,
  flags: {snake_case: bool}, quote_number (int|null), description (null)
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path

from gbbs_io import read_file, iter_records, read_count

TXT_FILE  = Path('..') / 'SPUR-data' / 'monsters.txt'
JSON_FILE = 'monsters.json'
RECORD_SIZE = 32

# ---------------------------------------------------------------------------
# Flag definitions — ORDER MATTERS: longer keys before shorter prefix matches
# ---------------------------------------------------------------------------
MONSTER_FLAGS = [
    (';;',  'heavy_armor'),
    (';',   'light_armor'),
    ('>>',  'chance_find_gold_2x'),
    ('>',   'chance_find_gold'),
    ('++',  'cast_multiple_spells'),
    ('+',   'cast_one_spell'),
    (']',   'double_attacks'),
    (':',   'mechanical'),
    ('.',   'increase_strength'),
    ('E',   'evil'),
    ('G',   'good'),
    ('<',   're_animates'),
    ('#',   'cast_turn_to_stone'),
    ('*',   'poisonous_attack'),
    ('@',   'diseased_attack'),
    ('&',   'experience_drain'),
    ('%',   'magic_resistant'),
    ('~',   'appears_unaffected'),
    ('-',   'fire_attack'),
    ('X',   'no_gold'),
    ('$',   'multiple_monsters'),
    ('?',   'no_article'),
    ('AC',  'charmable'),
    ('!',   'has_quote'),
]

ALL_FLAG_KEYS = [v for _, v in MONSTER_FLAGS]

MONSTER_SIZES = {
    1: 'huge',
    2: 'large',
    3: 'big',
    4: 'man_sized',
    5: 'short',
    6: 'small',
    7: 'swift',
}

EMPTY_FLAGS = {k: False for k in ALL_FLAG_KEYS}


@dataclass
class Monster:
    number:         int
    status:         int
    name:           str
    size:           str | None
    strength:       int
    special_weapon: int
    to_hit:         int
    flags:          dict = field(default_factory=lambda: dict(EMPTY_FLAGS))
    quote_number:   int | None = None
    description:    str | None = None

    def __str__(self):
        return f'#{self.number} {self.name}'


# ---------------------------------------------------------------------------
# Flag parsing
# ---------------------------------------------------------------------------

def parse_flags(flag_str: str) -> tuple[dict, int | None]:
    """
    Parse flag string (everything after '|') into a flags dict.
    Returns (flags_dict, quote_number_or_None).
    Longest-match-first avoids ;; vs ; and >> vs > ambiguity.
    """
    flags = dict(EMPTY_FLAGS)
    quote_number = None
    remaining = flag_str

    while remaining:
        matched = False
        for symbol, key in MONSTER_FLAGS:
            if remaining.startswith(symbol):
                flags[key] = True
                remaining = remaining[len(symbol):]
                if key == 'has_quote' and len(remaining) >= 2 and remaining[:2].isdigit():
                    quote_number = int(remaining[:2])
                    remaining = remaining[2:]
                matched = True
                break
        if not matched:
            logging.warning('Unknown flag character: %r in %r', remaining[0], flag_str)
            remaining = remaining[1:]

    return flags, quote_number


# ---------------------------------------------------------------------------
# Record parsing
# ---------------------------------------------------------------------------

def parse_monster(record_num: int, fields: list[str]) -> Monster | None:
    """Parse one monster record's fields into a Monster dataclass."""
    logging.debug('Record %d raw fields (%d): %r', record_num, len(fields), fields)
    if len(fields) < 3:
        logging.warning('Record %d: too few fields (%d): %r', record_num, len(fields), fields)
        return None

    try:
        status = int(fields[0])
    except ValueError:
        logging.warning('Record %d: non-integer status %r, skipping', record_num, fields[0])
        return None

    info = fields[1]

    # Optional size digit after 'M.'
    size_char = info[2] if len(info) > 2 else ''

    if size_char.isdigit():
        size  = MONSTER_SIZES.get(int(size_char))
        start = 3
        # logging.debug('Record %d info field: %r  info[2]=%r', record_num, info, info[2] if len(info) > 2 else '(too short)')
        logging.debug('Record %d size: %s', record_num, size)
    else:
        size  = None
        start = 2

    # Split name from flags at '|'
    pipe = info.rfind('|')
    if pipe == -1:
        name        = info[start:].rstrip()
        flags       = dict(EMPTY_FLAGS)
        quote_num   = None
    else:
        name        = info[start:pipe].rstrip()
        flags, quote_num = parse_flags(info[pipe + 1:])

    # Remaining numeric fields — some records omit to_hit
    try:
        strength       = int(fields[2]) if len(fields) > 2 else 0
        special_weapon = int(fields[3]) if len(fields) > 3 else 0
        to_hit         = int(fields[4]) if len(fields) > 4 else 0
    except ValueError as e:
        logging.warning('Record %d: numeric parse error: %s', record_num, e)
        strength, special_weapon, to_hit = 0, 0, 0

    return Monster(
        number         = record_num,
        status         = status,
        name           = name,
        size           = size,
        strength       = strength,
        special_weapon = special_weapon,
        to_hit         = to_hit,
        flags          = flags,
        quote_number   = quote_num,
        description    = None,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def convert(txt_filename: Path = TXT_FILE, json_filename: str = JSON_FILE):
    data = read_file(txt_filename)
    logging.debug('Read %d bytes, first 64: %s', len(data), data[:64].hex(' '))
    expected = read_count(data, RECORD_SIZE)
    logging.debug('Expected monster count: %s', expected)

    monsters = []
    for record_num, fields in iter_records(data, RECORD_SIZE):
        m = parse_monster(record_num, fields)
        if m:
            monsters.append(m)
            logging.debug('Parsed: %s', m)

    if expected and len(monsters) != expected:
        logging.warning('Expected %d monsters, parsed %d', expected, len(monsters))

    with open(json_filename, 'w') as f:
        json.dump([asdict(m) for m in monsters], f, indent=4)
    print(f"Wrote {len(monsters)} monsters to '{json_filename}'.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
    convert()