#!/bin/env python3
"""
convert_item_data.py
(old version is convert_object_data.py; still has some useful notes and TODOs in it)

Reads items.txt (SPUR binary, record size TBD) and writes items.json.

Item name field format (from file-formats.txt):

    T.ROCKS|081SLING
    ^  ^    ^^ ^
    |  |    || `--- weapon name the ammo goes with
    |  |    |`---- damage rating (1 digit)
    |  |    `---- number of rounds (2 digits)
    |  `---------- item name (or ammo name)
    `------------- item type (T=treasure, A=armor, S=shield, B=book,
                              C=container/cursed, P=compass)

Ammunition items have a '|' in the name field followed by:
    2-digit round count + 1-digit damage + weapon name

Ammunition carriers (bandoliers etc.) share the same '|' syntax
but are distinguished by being hard-coded items 147-150 in the
original game, or by a '*' active flag in some variants.

Schema per item:
  number, active, item_type, name, price
  ammo: {rounds, damage, weapon_name} | null
"""

import json
import logging
from dataclasses import dataclass, field, asdict

from gbbs_io import read_file, iter_records, read_count

TXT_FILE    = '../SPUR-data/items.txt'
JSON_FILE   = './items.json'

# Record size confirmed from hexdump: 30 bytes per record.
# Field layout: active_flag \r type.name \r price \r [null padding]
RECORD_SIZE = 30

ITEM_TYPES = {
    'T': 'treasure',
    'A': 'armor',
    'S': 'shield',
    'B': 'book',
    'C': 'cursed',      # also used for containers and coffins
    'P': 'compass',
    'F': 'food',        # from stores.txt
    'D': 'drink',       # from stores.txt
}

# Items 147-150 are ammo carriers (hard-coded in original SPUR source)
AMMO_CARRIER_NUMBERS = {147, 148, 149, 150}


@dataclass
class AmmoInfo:
    rounds:    int
    damage:    int
    used_with: str | None   # weapon name substring, or None for ammo carriers


@dataclass
class Item:
    number:    int
    active:    bool          # CB$: '1' = active, '*' = inactive
    item_type: str | None
    name:      str
    price:     int
    ammo:      AmmoInfo | None = None
    is_carrier: bool = False  # True for bandoliers etc.

    def __str__(self):
        return f'#{self.number} {self.name}'


# ---------------------------------------------------------------------------
# Ammo parsing
# ---------------------------------------------------------------------------

def parse_ammo(name_raw: str, after_pipe: str) -> AmmoInfo | None:
    """
    Parse the ammo spec after '|' in an item name field.
    Format: 2-digit rounds + 1-digit damage + weapon name
    e.g. '081SLING' -> AmmoInfo(rounds=8, damage=1, weapon_name='SLING')
         '064357 MAG' -> AmmoInfo(rounds=6, damage=4, weapon_name='357 MAG')
    Returns None if the string doesn't match the expected format.
    """
    if len(after_pipe) < 4:
        logging.warning('Ammo spec too short: %r [%s]', after_pipe, name_raw)
        return None
    try:
        rounds      = int(after_pipe[0:2])
        damage      = int(after_pipe[2:3])
        weapon_name = after_pipe[3:].strip()
        return AmmoInfo(rounds=rounds, damage=damage, used_with=weapon_name)
    except ValueError:
        logging.warning('Could not parse ammo spec: %r', after_pipe)
        return None


# ---------------------------------------------------------------------------
# Record parsing
# ---------------------------------------------------------------------------

def parse_item(record_num: int, fields: list[str]) -> Item | None:
    """Parse one item record's fields into an Item dataclass."""
    if len(fields) < 2:
        logging.warning('Record %d: too few fields (%d), skipping', record_num, len(fields))
        return None

    # Field 0: active flag ('1' = active, '*' = inactive)
    active_raw = fields[0].strip()
    active = active_raw == '1'

    # Field 1: type prefix + name (+ optional ammo spec)
    info = fields[1]

    # Type is first character, followed by '.'
    if len(info) >= 2 and info[1] == '.':
        item_type = ITEM_TYPES.get(info[0], info[0].lower())
        name_raw  = info[2:]
    else:
        item_type = None
        name_raw  = info

    # Split on '|' for ammo spec
    pipe = name_raw.find('|')
    if pipe == -1:
        name = name_raw.strip()
        ammo = None
    else:
        name = name_raw[:pipe].strip()
        ammo = parse_ammo(name_raw, name_raw[pipe + 1:])

    # Field 2: price
    try:
        price   = int(fields[2]) if len(fields) > 2 else 0
    except ValueError as e:
        logging.warning('Record %d: numeric parse error: %s', record_num, e)
        price = 0

    is_carrier = record_num in AMMO_CARRIER_NUMBERS

    return Item(
        number     = record_num,
        active     = active,
        item_type  = item_type,
        name       = name,
        price      = price,
        ammo       = ammo,
        is_carrier = is_carrier,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def convert(txt_filename: str = TXT_FILE, json_filename: str = JSON_FILE,
            record_size: int = RECORD_SIZE):
    data = read_file(txt_filename)
    expected = read_count(data, record_size)

    items = []
    for record_num, fields in iter_records(data, record_size):
        item = parse_item(record_num, fields)
        if item:
            items.append(item)
            logging.debug('Parsed: %s', item)

    if expected and len(items) != expected:
        logging.warning('Expected %d items, parsed %d', expected, len(items))

    with open(json_filename, 'w') as f:
        json.dump([asdict(i) for i in items], f, indent=4)
    print(f"Wrote {len(items)} items to '{json_filename}'.")


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(message)s')
    convert()
