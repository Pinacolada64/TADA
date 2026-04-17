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

MONSTER_FILE = 'monsters.json'
QUOTES_FILE  = 'monster_quotes.json'
WEAPONS_FILE = 'weapons.json'

FLAG_LABELS = {
    # flags with [?] are uncertain usage
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
    'appears_unaffected':   'Appears unaffected [?]',
    'fire_attack':          'Fire attack',
    'no_gold':              'No gold on body',
    'multiple_monsters':    'Multiple monsters',
    'no_article':           'No article (suppress THE) [?]',
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

def load_monsters(path: str) -> list[dict]:
    with open(path) as f:
        monsters = json.load(f)
    logging.info("Loaded %d monsters from '%s'", len(monsters), path)
    return monsters


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


def load_weapons(path: str) -> dict[int, str]:
    """Load weapons JSON into a dict keyed by weapon number."""
    try:
        with open(path) as f:
            data = json.load(f)
        logging.info("Loaded %d weapons from '%s'", len(data), path)
        return {w['number']: w['name'] for w in data}
    except FileNotFoundError:
        logging.warning("'%s' not found, weapon names unavailable.", path)
        return {}


def save_monsters(monsters: list[dict], path: str):
    with open(path, 'w') as f:
        json.dump(monsters, f, indent=4)
    print(f"Saved {len(monsters)} monsters to '{path}'.")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def active_flags(monster: dict) -> list[str]:
    return [k for k, v in monster.get('flags', {}).items() if v]


def show_monster(m: dict, quotes: dict[int, str], weapons: dict[int, str]):
    header(f"#{m['number']} {m['name']}")
    print(f"  Status  : {m['status']}")
    print(f"  Size    : {m['size'] or '(none)'}")
    print(f"  Strength: {m['strength']}")

    wpn_id = m['special_weapon']
    wpn_name = weapons.get(wpn_id, f'(unknown #{wpn_id})') if wpn_id else '(none)'
    print(f"  Spec.wpn: {wpn_name}")

    print(f"  To-hit %: {m['to_hit']}")

    if m.get('description'):
        print(f"  Desc    : {m['description']}")

    if m.get('flags', {}).get('has_quote'):
        qnum = m.get('quote_number')
        prefix = '  Quote   : '
        if qnum is None:
            print(f'{prefix}(has_quote set but no quote_number)')
        else:
            text = quotes.get(qnum)
            if text is None:
                print(f'{prefix}[{qnum}] (not found in {QUOTES_FILE})')
            else:
                display = text.replace('$', '<player_name>')
                print(f'{prefix}[{qnum}]: {display}')

    flags = active_flags(m)
    if flags:
        print(f"  Flags   : {', '.join(FLAG_LABELS.get(f, f) for f in flags)}")
    else:
        print('  Flags   : (none)')


# ---------------------------------------------------------------------------
# Editors
# ---------------------------------------------------------------------------

def list_quotes(quotes: dict[int, str]) -> int | None:
    """Display quotes in a numbered menu, return the selected quote number or None."""
    # Build a list of (number, text) pairs so we can map selection back to quote number
    items = sorted(quotes.items())  # list of (quote_number, text)
    display = [f'#{num:>3}: {text}' for num, text in items]
    idx = numbered_menu(display, 'Monster quotes')
    if idx is None:
        return None
    logging.info("Selected quote index: %d", idx)
    return items[idx][0]


def edit_basic(m: dict, quotes: dict[int, str], weapons: dict[int, str]):
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

    for attr in ('strength', 'to_hit'):
        raw = prompt(attr.replace('_', ' ').title(), str(m[attr]))
        try:
            m[attr] = int(raw)
        except ValueError:
            print(f'Invalid value for {attr}, unchanged.')

    # Special weapon -- show menu if weapons loaded, else raw number
    if weapons:
        wpn_id = m['special_weapon']
        current_name = weapons.get(wpn_id, '(none)') if wpn_id else '(none)'
        print(f"\n  Current special weapon: {current_name}")
        items = sorted(weapons.items())
        display = [f'#{num:>3}: {name}' for num, name in items] + ['(none)']
        raw = prompt("Special weapon ('?': list, Enter to keep)")
        if raw == '?':
            idx = numbered_menu(display, 'Special weapons')
            if idx is not None:
                if idx <= len(items):
                    m['special_weapon'] = items[idx - 1][0]
                else:
                    m['special_weapon'] = 0
        elif raw.isdigit():
            m['special_weapon'] = int(raw)
    else:
        raw = prompt('Special weapon #', str(m['special_weapon']))
        try:
            m['special_weapon'] = int(raw)
        except ValueError:
            print('Invalid value for special_weapon, unchanged.')

    raw = prompt('Description (blank = none)', m.get('description') or '')
    m['description'] = raw if raw else None

    raw = prompt("Quote number (blank: none, '?': list)", str(m.get('quote_number') or ''))
    if raw == '?':
        chosen = list_quotes(quotes)
        if chosen is not None:
            # list_quotes() returns the 1-based list index:
            m['quote_number'] = chosen
    elif raw.isdigit():
        m['quote_number'] = int(raw)
    else:
        m['quote_number'] = None


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


def edit_monster(m: dict, quotes: dict[int, str], weapons: dict[int, str]):
    """Per-monster edit menu."""
    while True:
        show_monster(m, quotes, weapons)
        print()
        print('  1. Edit attributes')
        print('  2. Edit flags')
        print('  0. Back')
        choice = prompt('Choose')
        if choice == '1':
            edit_basic(m, quotes, weapons)
        elif choice == '2':
            edit_flags(m)
        elif choice == '0':
            break


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main():
    try:
        monsters = load_monsters(MONSTER_FILE)
    except FileNotFoundError:
        print(f"'{MONSTER_FILE}' not found. Run convert_monster_data.py first.")
        sys.exit(1)

    quotes  = load_quotes(QUOTES_FILE)
    weapons = load_weapons(WEAPONS_FILE)
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
                edit_monster(monsters[idx - 1], quotes, weapons)
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
                    edit_monster(chosen, quotes, weapons)
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
            save_monsters(monsters, MONSTER_FILE)
            original = deepcopy(monsters)
            dirty = False

        elif choice == '0':
            if dirty and not confirm('Unsaved changes. Quit anyway?'):
                continue
            break


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()