#!/bin/env python3
"""
show_sfx.py

Displays and edits each weapon's sfx_index alongside the corresponding
miss/hit sound effect strings, for validation against the original ACOS source.

Runtime formula (from SPUR.WEAPON.S):
    vr = sfx_index * 6 + 1    (1-based offset into sound table)

Usage:
    python3 show_sfx.py
    python3 show_sfx.py --weapons path/to/weapons.json
"""

import json
import argparse
import sys
from copy import deepcopy

WEAPONS_FILE = 'weapons.json'

# Miss/hit sound pairs indexed by sfx_index (0-9).
# Source: SPUR.WEAPON.S comment block and convert_weapon_data.py
WEAPON_SOUNDS = [
    ['CRACK!',    'CRACK!'],    # 0
    ['SWISH!',    'SLASH!'],    # 1
    ['SWISH!',    'BASH!'],     # 2
    ['SWISH!',    'THUNK!'],    # 3
    ['SWISH!',    'STAB!'],     # 4
    ['KA-PWING!', 'BLAM!'],     # 5 -- projectile weapons (guns, etc.)
    ['FIZZLE!',   'BOOOM!'],    # 6
    ['SIZZLE!',   'SIZZLE!'],   # 7  -- proximity (e.g., fireball: secondary heat damage)
    ['SWISH!',    'CRASH!'],    # 8
    ['BRRRT!',    'BRRRT!'],    # 9
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sfx_strings(sfx_index: int | None) -> tuple[str, str]:
    """Return (miss_sfx, hit_sfx) for a given sfx_index, or placeholders."""
    if sfx_index is None or not (0 <= sfx_index < len(WEAPON_SOUNDS)):
        return '(?)', '(?)'
    return WEAPON_SOUNDS[sfx_index][0], WEAPON_SOUNDS[sfx_index][1]


def prompt(msg: str, default: str = '') -> str:
    suffix = f' [{default}]' if default else ''
    val = input(f'{msg}{suffix}: ').strip()
    return val if val else default


def confirm(msg: str) -> bool:
    return prompt(f'{msg} (y/n)', 'n').lower() == 'y'


def print_sfx_table():
    """Print the full SFX index reference table."""
    print("\n=== SFX index reference ===")
    print(f"  {'Idx':>3}  {'vr':>3}  {'Miss':<10} {'Hit'}")
    print(f"  {'---':>3}  {'---':>3}  {'-'*10} {'-'*10}")
    for i, (miss, hit) in enumerate(WEAPON_SOUNDS):
        vr = i * 6 + 1
        print(f"  {i:>3}  {vr:>3}  {miss:<10} {hit}")


def print_weapons(weapons: list[dict]):
    """Print all weapons with their current sfx_index and sounds."""
    print(f"\n  {'#':>3}  {'Name':<24} {'Idx':>3}  {'vr':>3}  {'Miss':<10} {'Hit'}")
    print(f"  {'---':>3}  {'-'*24} {'---':>3}  {'---':>3}  {'-'*10} {'-'*10}")
    for w in weapons:
        idx  = w.get('sfx_index')
        miss, hit = sfx_strings(idx)
        vr   = (idx * 6 + 1) if idx is not None else '?'
        print(f"  {w['number']:>3}  {w['name']:<24} "
              f"{str(idx) if idx is not None else '?':>3}  "
              f"{str(vr):>3}  "
              f"{miss:<10} {hit}")


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------

def edit_sfx(weapons: list[dict]) -> bool:
    """
    Prompt the user to select a weapon and change its sfx_index.
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
    idx    = weapon.get('sfx_index')
    miss, hit = sfx_strings(idx)
    print(f"\n  #{weapon['number']} {weapon['name']}")
    print(f"  Current sfx_index: {idx}  ->  miss={miss}  hit={hit}")

    print_sfx_table()

    raw = prompt(f"New sfx_index [0-{len(WEAPON_SOUNDS)-1}] (Enter to cancel)").strip()
    if not raw:
        print("No change.")
        return False

    if not raw.isdigit() or not (0 <= int(raw) < len(WEAPON_SOUNDS)):
        print(f"Invalid index. Must be 0-{len(WEAPON_SOUNDS)-1}.")
        return False

    new_idx       = int(raw)
    new_miss, new_hit = sfx_strings(new_idx)
    print(f"  New sfx_index: {new_idx}  ->  miss={new_miss}  hit={new_hit}")

    if not confirm("Apply change?"):
        print("Cancelled.")
        return False

    weapon['sfx_index'] = new_idx
    print(f"  Updated #{weapon['number']} {weapon['name']}.")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Display and edit weapon sound effect indices.')
    parser.add_argument('--weapons', default=WEAPONS_FILE,
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
        print("  1. Edit sfx_index")
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
