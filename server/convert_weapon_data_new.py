#!/bin/env python3
"""
convert_weapon_data.py

Reads weapons.txt (SPUR binary, record size 34) and writes weapons.json.

Schema per weapon:
  number, location, name, kind, sound_effect, stability, to_hit,
  price, weapon_class, flags: [str]
"""

import json
import logging
from dataclasses import dataclass, field, asdict

from gbbs_io import read_file, iter_records, read_count

TXT_FILE    = '../SPUR-data/weapons.txt'
JSON_FILE   = 'weapons.json'
RECORD_SIZE = 34

WEAPON_KINDS = {
    'M.': 'magic',
    'S.': 'standard',
    'C.': 'cursed',
}

WEAPON_CLASSES = {
    1: 'energy',
    2: 'bash_slash',
    3: 'poke_jab',
    5: 'pole_range',
    8: 'projectile',
    9: 'proximity',
}

# Sound effect index (0-9) stored in weapon record as the digit after kind prefix.
# Derived at runtime via: vr = sfx_class * 6 + 1 (1-based index into sound table).
# The actual sounds are looked up from WEAPON_SOUNDS at display time.
WEAPON_SOUNDS = [
    ['CRACK!',    'CRACK!'],    # 0
    ['SWISH!',    'SLASH!'],    # 1
    ['SWISH!',    'BASH!'],     # 2
    ['SWISH!',    'THUNK!'],    # 3
    ['SWISH!',    'STAB!'],     # 4
    ['KA-PWING!', 'BLAM!'],     # 5
    ['FIZZLE!',   'BOOOM!'],    # 6
    ['SIZZLE!',   'SIZZLE!'],   # 7 -- secondary heat damage (phaser, fireball, etc.)
    ['SWISH!',    'CRASH!'],    # 8
    ['BRRRT!',    'BRRRT!'],    # 9
]

# Only 'x' defined so far; kept as a list for consistency with monster flags
WEAPON_FLAGS = {
    'x': 'future_expansion',
}


@dataclass
class Weapon:
    number:       int
    location:     int           # 0=on player, 1=in room, 2=in shoppe
    name:         str
    kind:         str           # magic / standard / cursed
    sfx_index:    int | None    # sound effect index (0-9); runtime: vr = sfx_index * 6 + 1
    stability:    int           # ease-of-use %, already multiplied by 10
    to_hit:       int           # base damage %, already multiplied by 10
    price:        int
    weapon_class: str | None
    flags:        list = field(default_factory=list)

    def __str__(self):
        return f'#{self.number} {self.name}'


# ---------------------------------------------------------------------------
# Record parsing
# ---------------------------------------------------------------------------

def parse_weapon(record_num: int, fields: list[str]) -> Weapon | None:
    """Parse one weapon record's fields into a Weapon dataclass."""
    if len(fields) < 5:
        logging.warning('Record %d: too few fields (%d), skipping', record_num, len(fields))
        return None

    try:
        location = int(fields[0])
    except ValueError:
        logging.warning('Record %d: non-integer location %r, skipping', record_num, fields[0])
        return None

    info = fields[1]

    # Kind prefix: first 2 chars ('M.', 'S.', 'C.')
    kind_raw = info[:2]
    kind = WEAPON_KINDS.get(kind_raw)
    if kind is None:
        logging.warning('Record %d: unknown kind prefix %r', record_num, kind_raw)
        kind = 'unknown'

    # Sound effect class digit after kind prefix
    sfx_char = info[2] if len(info) > 2 else ''
    if sfx_char.isdigit():
        sfx_index = int(sfx_char)
        start     = 3
    else:
        sfx_index = None
        start     = 2

    # Split name from flags at '|'
    pipe = info.rfind('|')
    if pipe == -1:
        name      = info[start:].rstrip()
        flag_list = []
    else:
        name      = info[start:pipe].rstrip()
        flag_str  = info[pipe + 1:]
        flag_list = [v for k, v in WEAPON_FLAGS.items() if k in flag_str]
        if flag_str and not flag_list:
            logging.warning('Record %d: unrecognised weapon flags %r', record_num, flag_str)

    try:
        stability     = int(fields[2]) * 10
        to_hit        = int(fields[3]) * 10
        price         = int(fields[4])
        weapon_class  = WEAPON_CLASSES.get(int(fields[5])) if len(fields) > 5 else None
    except ValueError as e:
        logging.warning('Record %d: numeric parse error: %s', record_num, e)
        stability, to_hit, price, weapon_class = 0, 0, 0, None

    return Weapon(
        number       = record_num,
        location     = location,
        name         = name,
        kind         = kind,
        sfx_index    = sfx_index,
        stability    = stability,
        to_hit       = to_hit,
        price        = price,
        weapon_class = weapon_class,
        flags        = flag_list,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def convert(txt_filename: str = TXT_FILE, json_filename: str = JSON_FILE):
    data = read_file(txt_filename)
    expected = read_count(data, RECORD_SIZE)

    weapons = []
    for record_num, fields in iter_records(data, RECORD_SIZE):
        w = parse_weapon(record_num, fields)
        if w:
            weapons.append(w)
            logging.debug('Parsed: %s', w)

    if expected and len(weapons) != expected:
        logging.warning('Expected %d weapons, parsed %d', expected, len(weapons))

    with open(json_filename, 'w') as f:
        json.dump([asdict(w) for w in weapons], f, indent=4)
    print(f"Wrote {len(weapons)} weapons to '{json_filename}'.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
    convert()
