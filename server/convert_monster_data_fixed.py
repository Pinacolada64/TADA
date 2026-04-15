#!/bin/env python3
"""
convert_monster_data.py

Reads monsters.txt and writes monsters.json with a normalized schema:
  - All keys always present (no omitted falsy fields)
  - Flags stored as dict of {snake_case_key: bool} for O(1) lookup
  - Longest-match-first flag parsing to avoid ;; vs ; and >> vs > ambiguity
  - Quote flag stores its numeric argument separately
"""

import json
import logging
from dataclasses import dataclass, field, asdict


# ---------------------------------------------------------------------------
# Flag definitions — ORDER MATTERS: longer keys must come before shorter ones
# that share a prefix (e.g. ';;' before ';', '>>' before '>')
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
    ('?',   'no_article'),          # suppress "THE" before name
    ('AC',  'charmable'),
    ('!',   'has_quote'),           # 2-digit quote number follows
]

# All valid flag keys, for use in the editor
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

    def __str__(self):
        return f'#{self.number} {self.name}'


# ---------------------------------------------------------------------------
# File reading helpers
# ---------------------------------------------------------------------------

def diskin(fh):
    """Read one non-comment line from fh, stripping newline."""
    while True:
        data = fh.readline().strip('\n')
        if not data.startswith('#'):
            logging.info(f'keep {data=}')
            return data
        logging.info(f'toss {data=}')


def read_stanza(fh):
    """
    Read one 5-line monster stanza, skipping comment lines.
    Stanzas are delimited by '^' lines (which are discarded by the caller).
    """
    lines = []
    while len(lines) < 5:
        line = diskin(fh)
        if line != '^':
            lines.append(line)
    return lines


# ---------------------------------------------------------------------------
# Flag parsing
# ---------------------------------------------------------------------------

def parse_flags(flag_str: str) -> tuple[dict, int | None]:
    """
    Parse the flag string (everything after '|') into a flags dict.
    Returns (flags_dict, quote_number_or_None).

    Uses longest-match-first so ';;' is matched before ';', etc.
    The '!' flag is followed immediately by a 2-digit quote number.
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
                if key == 'has_quote':
                    # consume the 2-digit number that follows '!'
                    if len(remaining) >= 2 and remaining[:2].isdigit():
                        quote_number = int(remaining[:2])
                        remaining = remaining[2:]
                matched = True
                break
        if not matched:
            logging.warning(f'Unknown flag character: {remaining[0]!r} in {flag_str!r}')
            remaining = remaining[1:]

    return flags, quote_number


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def convert(txt_filename: str, json_filename: str):
    monster_list = []

    with open(txt_filename) as fh:
        # First non-comment line is the monster count
        num_monsters = int(diskin(fh))
        logging.info(f'{num_monsters=}')
        # Discard the '^' separator after the count
        diskin(fh)

        for count in range(1, num_monsters + 1):
            data = read_stanza(fh)

            status = int(data[0])
            info   = data[1]

            # Parse optional size digit after 'M.'
            size_char = info[2]
            if size_char.isdigit():
                size = MONSTER_SIZES.get(int(size_char))
                start = 3
            else:
                size = None
                start = 2

            # Split name from flags at '|'
            pipe = info.rfind('|')
            if pipe == -1:
                name       = info[start:].rstrip()
                flags      = dict(EMPTY_FLAGS)
                quote_num  = None
            else:
                name       = info[start:pipe].rstrip()
                flags, quote_num = parse_flags(info[pipe + 1:])

            strength       = int(data[2])
            special_weapon = int(data[3])
            to_hit         = int(data[4])

            # Discard trailing '^' (last monster has no trailing '^')
            peek = diskin(fh)
            if peek not in ('^', ''):
                logging.warning(f'Expected ^ after monster {count}, got {peek!r}')

            monster = Monster(
                number         = count,
                status         = status,
                name           = name,
                size           = size,
                strength       = strength,
                special_weapon = special_weapon,
                to_hit         = to_hit,
                flags          = flags,
                quote_number   = quote_num,
            )
            logging.info(f'Parsed: {monster}')
            monster_list.append(monster)

    with open(json_filename, 'w') as out:
        json.dump([asdict(m) for m in monster_list], out, indent=4)
    print(f"Wrote {len(monster_list)} monsters to '{json_filename}'")


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(message)s')
    convert('monsters.txt', 'monsters.json')
