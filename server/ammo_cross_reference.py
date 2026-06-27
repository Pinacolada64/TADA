#!/bin/env python3
"""
cross_reference.py

Cross-references items.json against weapons.json to:
  - Match each ammo item's 'used_with' field against weapon names
  - Flag ammo items with no matching weapon
  - Flag ammo carriers (used_with=None)
  - Optionally list all weapons and which ammo types feed them

Usage:
    python3 cross_reference.py
    python3 cross_reference.py --weapons path/to/weapons.json
                               --items   path/to/items.json
    python3 cross_reference.py --unmatched-only
"""

import json
import argparse
from pathlib import Path


ITEMS_FILE   = 'items.json'
WEAPONS_FILE = 'weapons.json'


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def find_weapon(used_with: str, weapons: list[dict]) -> list[dict]:
    """
    Return all weapons whose name contains 'used_with' as a substring.
    Case-insensitive, since weapon names are uppercase and used_with may vary.
    """
    needle = used_with.upper()
    return [w for w in weapons if needle in w['name'].upper()]


def cross_reference(items: list[dict], weapons: list[dict],
                    unmatched_only: bool = False):
    """
    Print a report matching ammo items to their weapons.
    """
    ammo_items    = [i for i in items if i.get('ammo')]
    carrier_items = [i for i in ammo_items
                     if i['ammo'].get('used_with') is None]
    loader_items  = [i for i in ammo_items
                     if i['ammo'].get('used_with') is not None]

    # --- Ammo carriers (no used_with) ---
    print(f"\n=== Ammo carriers ({len(carrier_items)}) ===")
    for item in carrier_items:
        ammo = item['ammo']
        print(f"  #{item['number']:>3} {item['name']:<30}"
              f"  capacity={ammo['rounds']}  caliber={ammo['damage']}")

    # --- Ammo loaders (have used_with) ---
    matched   = []
    unmatched = []

    for item in loader_items:
        used_with = item['ammo']['used_with']
        hits = find_weapon(used_with, weapons)
        if hits:
            matched.append((item, hits))
        else:
            unmatched.append(item)

    if not unmatched_only:
        print(f"\n=== Matched ammo ({len(matched)}) ===")
        for item, hits in matched:
            ammo = item['ammo']
            weapon_names = ', '.join(w['name'] for w in hits)
            print(f"  #{item['number']:>3} {item['name']:<30}"
                  f"  rounds={ammo['rounds']}  damage={ammo['damage']}"
                  f"  -> {weapon_names}")

    print(f"\n=== Unmatched ammo ({len(unmatched)}) ===")
    if unmatched:
        for item in unmatched:
            ammo = item['ammo']
            print(f"  #{item['number']:>3} {item['name']:<30}"
                  f"  used_with={ammo['used_with']!r}"
                  f"  rounds={ammo['rounds']}  damage={ammo['damage']}")
    else:
        print("  (none -- all ammo matched successfully!)")

    # --- Weapon feed summary ---
    if not unmatched_only:
        print(f"\n=== Weapons by ammo type ===")
        for weapon in sorted(weapons, key=lambda w: w['number']):
            feeds = [item for item, hits in matched
                     if any(h['number'] == weapon['number'] for h in hits)]
            if feeds:
                ammo_names = ', '.join(
                    f"#{i['number']} {i['name']}" for i in feeds)
                print(f"  #{weapon['number']:>3} {weapon['name']:<30}  <- {ammo_names}")

    # --- Summary counts ---
    print(f"\n=== Summary ===")
    print(f"  Total items     : {len(items)}")
    print(f"  Ammo items      : {len(ammo_items)}")
    print(f"    Carriers      : {len(carrier_items)}")
    print(f"    Loaders       : {len(loader_items)}")
    print(f"      Matched     : {len(matched)}")
    print(f"      Unmatched   : {len(unmatched)}")
    print(f"  Total weapons   : {len(weapons)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Cross-reference ammo items against weapons.')
    parser.add_argument('--items',   default=ITEMS_FILE,
                        help=f'Path to items.json (default: {ITEMS_FILE})')
    parser.add_argument('--weapons', default=WEAPONS_FILE,
                        help=f'Path to weapons.json (default: {WEAPONS_FILE})')
    parser.add_argument('--unmatched-only', action='store_true',
                        help='Only show unmatched ammo items')
    args = parser.parse_args()

    try:
        items = load_json(args.items)
    except FileNotFoundError:
        print(f"Items file not found: '{args.items}'")
        return

    try:
        weapons = load_json(args.weapons)
    except FileNotFoundError:
        print(f"Weapons file not found: '{args.weapons}'")
        return

    cross_reference(items, weapons, unmatched_only=args.unmatched_only)


if __name__ == '__main__':
    main()
