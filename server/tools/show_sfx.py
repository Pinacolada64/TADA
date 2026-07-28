#!/bin/env python3
"""
show_sfx.py

Displays and edits each weapon's sound_effect (miss/hit strings), for
validation against the original ACOS source and item_system.WEAPON_SFX.

weapons.json stores sound_effect directly as [miss, hit] -- it's read
straight off each weapon's raw record by convert_weapon_data.py (the
per-weapon digit at SPUR.WEAPON.S:43's "vr = val(zz$)*6+1"), not derived
from weapon_class. The numbered table below is just an editing aid so you
can pick a known-good pair by index instead of retyping strings by hand.

Usage:
    python3 tools/show_sfx.py
    python3 tools/show_sfx.py --weapons path/to/weapons.json
"""

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

WEAPONS_FILE = Path(__file__).parent / '..' / 'weapons.json'

# Miss/hit sound pairs, in item_system.WEAPON_SFX order -- an editing aid,
# not the source of truth (that's each weapon's own sound_effect field).
WEAPON_SOUNDS = [
    ['CRACK!',    'CRACK!'],    # 0
    ['SWISH!',    'SLASH!'],    # 1
    ['SWISH!',    'BASH!'],     # 2
    ['SWISH!',    'THUNK!'],    # 3
    ['SWISH!',    'STAB!'],     # 4
    ['KA-PWING!', 'BLAM!'],     # 5 -- pistols/muskets
    ['FIZZLE!',   'BOOOM!'],    # 6
    ['SIZZLE!',   'SIZZLE!'],   # 7  -- energy weapons, heat damage
    ['SWISH!',    'CRASH!'],    # 8
    ['BRRRT!',    'BRRRT!'],    # 9  -- full-auto guns
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sfx_pair(weapon: dict) -> tuple[str, str]:
    """Return (miss_sfx, hit_sfx) for a weapon, or placeholders if unset."""
    sfx = weapon.get('sound_effect')
    if not sfx or len(sfx) != 2:
        return '(?)', '(?)'
    return sfx[0], sfx[1]


def prompt(msg: str, default: str = '') -> str:
    suffix = f' [{default}]' if default else ''
    val = input(f'{msg}{suffix}: ').strip()
    return val if val else default


def confirm(msg: str) -> bool:
    return prompt(f'{msg} (y/n)', 'n').lower() == 'y'


def print_sfx_table():
    """Print the reference table of known miss/hit pairs."""
    print("\n=== Known SFX pairs ===")
    print(f"  {'Idx':>3}  {'Miss':<10} {'Hit'}")
    print(f"  {'---':>3}  {'-'*10} {'-'*10}")
    for i, (miss, hit) in enumerate(WEAPON_SOUNDS):
        print(f"  {i:>3}  {miss:<10} {hit}")


def print_weapons(weapons: list[dict]):
    """Print all weapons with their current sound_effect."""
    print(f"\n  {'#':>3}  {'Name':<24} {'Class':<12} {'Miss':<10} {'Hit'}")
    print(f"  {'---':>3}  {'-'*24} {'-'*12} {'-'*10} {'-'*10}")
    for w in weapons:
        miss, hit = sfx_pair(w)
        print(f"  {w['number']:>3}  {w['name']:<24} "
              f"{w.get('weapon_class', '?'):<12} {miss:<10} {hit}")


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------

def edit_sfx(weapons: list[dict]) -> bool:
    """
    Prompt the user to select a weapon and change its sound_effect.
    Returns True if any changes were made.
    """
    raw = prompt("Weapon # to edit (or Enter to cancel)").strip()
    if not raw:
        return False

    if not raw.isdigit():
        print("Invalid weapon number.")
        return False

    wnum = int(raw)
    matches = [w for w in weapons if w['number'] == wnum]
    if not matches:
        print(f"No weapon #{wnum} found.")
        return False

    weapon = matches[0]
    miss, hit = sfx_pair(weapon)
    print(f"\n  #{weapon['number']} {weapon['name']} ({weapon.get('weapon_class', '?')})")
    print(f"  Current sound_effect: miss={miss}  hit={hit}")

    print_sfx_table()

    raw = prompt(f"Pick a pair by index [0-{len(WEAPON_SOUNDS)-1}], "
                 f"or type 'MISS,HIT' directly (Enter to cancel)").strip()
    if not raw:
        print("No change.")
        return False

    if raw.isdigit():
        idx = int(raw)
        if not (0 <= idx < len(WEAPON_SOUNDS)):
            print(f"Invalid index. Must be 0-{len(WEAPON_SOUNDS)-1}.")
            return False
        new_miss, new_hit = WEAPON_SOUNDS[idx]
    elif ',' in raw:
        new_miss, new_hit = (part.strip() for part in raw.split(',', 1))
    else:
        print("Enter an index number or 'MISS,HIT'.")
        return False

    print(f"  New sound_effect: miss={new_miss}  hit={new_hit}")

    if not confirm("Apply change?"):
        print("Cancelled.")
        return False

    weapon['sound_effect'] = [new_miss, new_hit]
    print(f"  Updated #{weapon['number']} {weapon['name']}.")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Display and edit weapon sound effects.')
    parser.add_argument('--weapons', default=str(WEAPONS_FILE),
                        help=f'Path to weapons.json (default: {WEAPONS_FILE})')
    args = parser.parse_args()

    try:
        with open(args.weapons) as f:
            weapons = json.load(f)
    except FileNotFoundError:
        print(f"Weapons file not found: '{args.weapons}'")
        sys.exit(1)

    original = deepcopy(weapons)
    dirty    = False

    while True:
        print_weapons(weapons)
        print()
        print("  1. Edit sound_effect")
        print("  2. Show SFX table")
        print("  3. Save")
        print("  0. Quit")
        choice = prompt("Choose")

        if choice == '1':
            if edit_sfx(weapons):
                dirty = True

        elif choice == '2':
            print_sfx_table()

        elif choice == '3':
            with open(args.weapons, 'w') as f:
                json.dump(weapons, f, indent=4)
            print(f"Saved {len(weapons)} weapons to '{args.weapons}'.")
            original = deepcopy(weapons)
            dirty    = False

        elif choice == '0':
            if dirty and not confirm("Unsaved changes. Quit anyway?"):
                continue
            break


if __name__ == '__main__':
    main()
