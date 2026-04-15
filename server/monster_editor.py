#!/bin/env python3
"""
monster_editor.py

Plain terminal editor for monsters.json.
No curses/rich -- just input() and print(), so output is safe for
any client including PetSCII translators.

Menu structure is kept in simple functions so it can be replaced later
with your menu_system.py library.
"""

import json
import logging
import sys
from copy import deepcopy

from convert_monster_data_fixed import ALL_FLAG_KEYS, MONSTER_SIZES

JSON_FILE   = 'monsters.json'
QUOTES_FILE = 'monster_quotes.json'

FLAG_LABELS = {
    'heavy_armor':          'Heavy armor',
    'light_armor':          'Light armor',
    'chance_find_gold_2x':  '2x chance find gold',
    'chance_find_gold':     'Chance find gold',
    'cast_multiple_spells': 'Cast multiple spells',
    'cast_one_spell':       'Cast one spell',
    'double_attacks':       'Double attacks',
    'mechanical':           'Mechanical being',
    'increase_strength':    'Increase strength',
    'evil':                 'Evil',
    'good':                 'Good',
    're_animates':          'Re-animates',
    'cast_turn_to_stone':   'Cast turn to stone',
    'poisonous_attack':     'Poisonous attack',
    'diseased_attack':      'Diseased attack',
    'experience_drain':     'Experience drain',
    'magic_resistant':      'Magic resistant',
    'appears_unaffected':   'Appears unaffected',
    'fire_attack':          'Fire attack',
    'no_gold':              'No gold on body',
    'multiple_monsters':    'Multiple monsters',
    'no_article':           'No article (suppress THE)',
    'charmable':            'Charmable',
    'has_quote':            'Has quote',
}


# ---------------------------------------------------------------------------
# I/O helpers -- swap these out for menu_system.py calls later
# ---------------------------------------------------------------------------

def prompt(msg: str, default: str = '') -> str:
    suffix = f' [{default}]' if default else ''
    val = input(f'{msg}{suffix}: ').strip()
    return val if val else default


def confirm(msg: str) -> bool:
    return prompt(f'{msg} (y/n)', 'n').lower() == 'y'


def pause():
    input('Press Enter to continue...')


def header(title: str):
    print()
    print(f'=== {title} ===')


def numbered_menu(items: list[str], title: str = '') -> int | None:
    """
    Display a numbered list and return the 1-based choice, or None to cancel.
    Items are paginated 20 at a time.
    """
    if title:
        header(title)
    page_size = 20
    start = 0
    while True:
        chunk = items[start:start + page_size]
        for i, item in enumerate(chunk, start=start + 1):
            print(f'  {i:>3}. {item}')
        nav = []
        if start + page_size < len(items):
            nav.append('N=next')
        if start > 0:
            nav.append('P=prev')
        nav.append('0=cancel')
        print('  ' + '  '.join(nav))
        raw = prompt('Choose').upper()
        if raw == 'N' and start + page_size < len(items):
            start += page_size
        elif raw == 'P' and start > 0:
            start -= page_size
        elif raw == '0':
            return None
        else:
            try:
                choice = int(raw)
                if 1 <= choice <= len(items):
                    return choice
            except ValueError:
                pass
            print('Invalid choice.')


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_quotes(path: str) -> dict[int, str]:
    """Load quotes JSON into a dict keyed by quote number."""
    try:
        with open(path) as f:
            data = json.load(f)
        logging.info("Loaded %d quotes from '%s'", len(data), path)
        return {q['number']: q['quote'] for q in data}
    except FileNotFoundError:
        logging.warning("'%s' not found, quotes unavailable.", path)
        return {}


def load_monsters(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def save_monsters(monsters: list[dict], path: str):
    with open(path, 'w') as f:
        json.dump(monsters, f, indent=4)
    print(f"Saved {len(monsters)} monsters to '{path}'.")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def active_flags(monster: dict) -> list[str]:
    return [k for k, v in monster.get('flags', {}).items() if v]


def show_monster(m: dict, quotes: dict[int, str]):
    header(f"#{m['number']} {m['name']}")
    print(f"  Status  : {m['status']}")
    print(f"  Size    : {m['size'] or '(none)'}")
    print(f"  Strength: {m['strength']}")
    print(f"  Spec.wpn: {m['special_weapon']}")
    print(f"  To-hit %: {m['to_hit']}")

    if m.get('flags', {}).get('has_quote'):
        qnum = m.get('quote_number')
        if qnum is None:
            print('  Quote   : (has_quote set but no quote_number)')
        else:
            text = quotes.get(qnum)
            if text is None:
                print(f'  Quote #{qnum}: (not found in {QUOTES_FILE})')
            else:
                display = text.replace('$', '<player_name>')
                print(f'  Quote #{qnum}: {display}')

    flags = active_flags(m)
    if flags:
        print(f"  Flags   : {', '.join(FLAG_LABELS.get(f, f) for f in flags)}")
    else:
        print('  Flags   : (none)')


# ---------------------------------------------------------------------------
# Editors
# ---------------------------------------------------------------------------

def edit_basic(m: dict):
    """Edit non-flag attributes."""
    header(f"Edit attributes: {m['name']}")
    print('(Press Enter to keep current value)')

    name = prompt('Name', m['name'])
    m['name'] = name.upper()

    raw = prompt('Status', str(m['status']))
    try:
        m['status'] = int(raw)
    except ValueError:
        print('Invalid status, unchanged.')

    size_options = list(MONSTER_SIZES.values()) + ['(none)']
    current = m['size'] or '(none)'
    print(f"\n  Current size: {current}")
    for i, s in enumerate(size_options, 1):
        print(f'    {i}. {s}')
    raw = prompt(f'Choose size [1-{len(size_options)}, Enter to keep]')
    if raw:
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(size_options):
                chosen = size_options[idx]
                m['size'] = None if chosen == '(none)' else chosen
            else:
                print('Out of range, size unchanged.')
        except ValueError:
            print('Invalid input, size unchanged.')

    for attr in ('strength', 'special_weapon', 'to_hit'):
        raw = prompt(attr.replace('_', ' ').title(), str(m[attr]))
        try:
            m[attr] = int(raw)
        except ValueError:
            print(f'Invalid value for {attr}, unchanged.')

    raw = prompt('Quote number (blank = none)', str(m.get('quote_number') or ''))
    m['quote_number'] = int(raw) if raw.isdigit() else None


def edit_flags(m: dict):
    """Toggle monster flags one at a time."""
    while True:
        header(f"Flags: {m['name']}")
        flags = m.setdefault('flags', {k: False for k in ALL_FLAG_KEYS})
        for i, key in enumerate(ALL_FLAG_KEYS, 1):
            state = 'ON ' if flags.get(key) else 'off'
            label = FLAG_LABELS.get(key, key)
            print(f'  {i:>2}. [{state}] {label}')
        print('   0. Done')
        raw = prompt('Toggle flag #')
        if raw == '0':
            break
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(ALL_FLAG_KEYS):
                key = ALL_FLAG_KEYS[idx]
                flags[key] = not flags.get(key, False)
                state = 'ON' if flags[key] else 'off'
                print(f'  {FLAG_LABELS.get(key, key)} -> {state}')
            else:
                print('Out of range.')
        except ValueError:
            print('Invalid input.')


def edit_monster(m: dict, quotes: dict[int, str]):
    """Per-monster edit menu."""
    while True:
        show_monster(m, quotes)
        print()
        print('  1. Edit attributes')
        print('  2. Edit flags')
        print('  0. Back')
        choice = prompt('Choose')
        if choice == '1':
            edit_basic(m)
        elif choice == '2':
            edit_flags(m)
        elif choice == '0':
            break


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main():
    try:
        monsters = load_monsters(JSON_FILE)
    except FileNotFoundError:
        print(f"'{JSON_FILE}' not found. Run convert_monster_data.py first.")
        sys.exit(1)

    quotes  = load_quotes(QUOTES_FILE)
    original = deepcopy(monsters)
    dirty   = False

    while True:
        header('Monster Editor')
        print(f'  Loaded: {len(monsters)} monsters  |  {"*UNSAVED CHANGES*" if dirty else "No changes"}')
        print()
        print('  1. List / edit monsters')
        print('  2. Search by name')
        print('  3. Search by flag')
        print('  4. Save')
        print('  0. Quit')
        choice = prompt('Choose')

        if choice == '1':
            names = [f"#{m['number']:>3} {m['name']}" for m in monsters]
            idx = numbered_menu(names, 'Select Monster')
            if idx is not None:
                before = deepcopy(monsters[idx - 1])
                edit_monster(monsters[idx - 1], quotes)
                if monsters[idx - 1] != before:
                    dirty = True

        elif choice == '2':
            term = prompt('Search name').upper()
            results = [m for m in monsters if term in m['name']]
            if not results:
                print('No matches.')
                pause()
            else:
                names = [f"#{m['number']:>3} {m['name']}" for m in results]
                idx = numbered_menu(names, f'Results for "{term}"')
                if idx is not None:
                    chosen = results[idx - 1]
                    before = deepcopy(chosen)
                    edit_monster(chosen, quotes)
                    if chosen != before:
                        dirty = True

        elif choice == '3':
            labels = [FLAG_LABELS.get(k, k) for k in ALL_FLAG_KEYS]
            idx = numbered_menu(labels, 'Select Flag')
            if idx is not None:
                key = ALL_FLAG_KEYS[idx - 1]
                results = [m for m in monsters if m.get('flags', {}).get(key)]
                if not results:
                    print(f'No monsters with flag: {FLAG_LABELS.get(key, key)}')
                    pause()
                else:
                    print(f'\nMonsters with [{FLAG_LABELS.get(key, key)}]:')
                    for m in results:
                        print(f"  #{m['number']:>3} {m['name']}")
                    pause()

        elif choice == '4':
            save_monsters(monsters, JSON_FILE)
            original = deepcopy(monsters)
            dirty = False

        elif choice == '0':
            if dirty and not confirm('Unsaved changes. Quit anyway?'):
                continue
            break


if __name__ == '__main__':
    main()