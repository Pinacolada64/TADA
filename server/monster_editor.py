#!/bin/env python3
"""
monster_editor.py

Async terminal editor for monsters.json, using TerminalContext and menu_system.
Run locally:  python3 monster_editor.py
"""

import json
import logging
import sys
from copy import deepcopy
from pathlib import Path

from convert_monster_data_fixed import ALL_FLAG_KEYS, MONSTER_SIZES
from monsters import monster_flag_labels, load_monsters, save_monsters
from menu_system import Menu, MenuItem, run_menu
from terminal_context import TerminalContext, run_local
from tada_utilities import header, input_yes_no, input_number_range

MONSTER_FILE = 'monsters.json'
QUOTES_FILE  = 'monster_quotes.json'
WEAPONS_FILE = 'weapons.json'
LEVEL_FILES  = [Path('..') / 'SPUR-data' / f'level-{i}' / f'level-{i}.json'
                for i in range(1, 8)]


# ---------------------------------------------------------------------------
# Load helpers
# ---------------------------------------------------------------------------

def load_quotes(path: str) -> dict[int, str]:
    try:
        with open(path) as f:
            data = json.load(f)
        logging.info("Loaded %d quotes from '%s'", len(data), path)
        return {q['number']: q['quote'] for q in data}
    except FileNotFoundError:
        logging.warning("'%s' not found, quotes unavailable.", path)
        return {}


def load_weapons(path: str) -> dict[int, str]:
    try:
        with open(path) as f:
            data = json.load(f)
        logging.info("Loaded %d weapons from '%s'", len(data), path)
        return {w['number']: w['name'] for w in data}
    except FileNotFoundError:
        logging.warning("'%s' not found, weapon names unavailable.", path)
        return {}


def load_monster_locations(level_files: list) -> dict[int, list[tuple[int, int, str]]]:
    locations: dict[int, list[tuple[int, int, str]]] = {}
    for path in level_files:
        try:
            level_num = int(Path(path).stem.split('-')[1])
        except (IndexError, ValueError):
            continue
        try:
            with open(path) as f:
                data = json.load(f)
        except FileNotFoundError:
            continue
        for room in data.get('rooms', []):
            mnum = room.get('monster', 0)
            if mnum:
                locations.setdefault(mnum, []).append(
                    (level_num, room['number'], room.get('name', '?'))
                )
    return locations


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def active_flags(monster: dict) -> list[str]:
    return [k for k, v in monster.get('flags', {}).items() if v]


def format_monster(m: dict, quotes: dict[int, str],
                   weapons: dict[int, str],
                   locations: dict[int, list]) -> list[str]:
    """Return a list of lines describing a monster (no I/O)."""
    wpn_id   = m['special_weapon']
    wpn_name = weapons.get(wpn_id, f'(unknown #{wpn_id})') if wpn_id else '(none)'
    locs     = locations.get(m['number'], [])
    loc_str  = ', '.join(f'L{lv} R{rn} ({rname})'
                         for lv, rn, rname in sorted(locs)) or '(not placed)'

    qnum  = m.get('quote_number')
    qtext = ''
    if m.get('flags', {}).get('has_quote') and qnum:
        raw   = quotes.get(qnum, '')
        qtext = raw.replace('$', '<player_name>')

    flags = active_flags(m)
    flag_str = ', '.join(monster_flag_labels.get(f, f) for f in flags) or '(none)'

    lines = [
        f"  Status  : {'Active' if m['status'] == 1 else 'Inactive'}",
        f"  Size    : {m['size'] or '(none)'}",
        f"  Strength: {m['strength']}",
        f"  Spec.wpn: {wpn_name}",
        f"  To-hit %: {m['to_hit']}",
        f"  Location: {loc_str}",
    ]
    if m.get('description'):
        lines.append(f"  Desc    : {m['description']}")
    if qtext:
        lines.append(f"  Quote #{qnum}: {qtext}")
    lines.append(f"  Flags   : {flag_str}")
    return lines


async def show_monster(ctx, m: dict, quotes: dict[int, str],
                       weapons: dict[int, str],
                       locations: dict[int, list]):
    await header(ctx, f"#{m['number']} {m['name']}")
    await ctx.send(format_monster(m, quotes, weapons, locations))


# ---------------------------------------------------------------------------
# Quote picker submenu
# ---------------------------------------------------------------------------

def build_quote_menu(m: dict, quotes: dict[int, str],
                     on_select) -> Menu:
    """Build a submenu listing all quotes. on_select(ctx, qnum) called on pick."""
    menu = Menu(title='Select Quote')
    for qnum, text in sorted(quotes.items()):
        display = text.replace('$', '<player_name>')
        # capture qnum in default arg to avoid closure issue
        def make_action(n=qnum):
            async def _action(ctx):
                await on_select(ctx, n)
            return _action
        menu.add_item(MenuItem(
            text          = f'#{qnum:>3}: {display[:50]}',
            dot_leader_handler = lambda ctx, n=qnum: '<<' if m.get('quote_number') == n else '',
            action        = make_action(),
        ))
    return menu


# ---------------------------------------------------------------------------
# Flags submenu
# ---------------------------------------------------------------------------

def build_flags_menu(m: dict, dirty_ref: list) -> Menu:
    """
    Build a flags toggle menu. dirty_ref is a one-element list so the
    action closure can signal that a change was made.
    """
    menu = Menu(title=f"Flags: {m['name']}")
    flags = m.setdefault('flags', {k: False for k in ALL_FLAG_KEYS})

    for key in ALL_FLAG_KEYS:
        label = monster_flag_labels.get(key, key)
        def make_action(k=key):
            async def _toggle(ctx):
                flags[k] = not flags.get(k, False)
                state = 'ON' if flags[k] else 'off'
                await ctx.send(f'  {monster_flag_labels.get(k, k)} -> {state}')
                dirty_ref[0] = True
            return _toggle
        menu.add_item(MenuItem(
            text               = label,
            dot_leader_handler = lambda ctx, k=key: 'ON ' if flags.get(k) else 'off',
            action             = make_action(),
        ))
    return menu


# ---------------------------------------------------------------------------
# Edit basic attributes menu
# ---------------------------------------------------------------------------

def build_edit_menu(m: dict, quotes: dict[int, str],
                    weapons: dict[int, str], dirty_ref: list) -> Menu:
    """
    Build the per-field edit menu for a monster.
    Each item shows the current value via dot_leader_handler and prompts
    for a new value when selected.
    """
    menu = Menu(title=f"Edit: {m['name']}")

    # --- Name ---
    async def edit_name(ctx):
        raw = await ctx.prompt(f"Name [{m['name']}]")
        if raw:
            m['name'] = raw.upper()
            dirty_ref[0] = True

    menu.add_item(MenuItem(
        text               = 'Name',
        shortcuts          = ['N'],
        dot_leader_handler = lambda ctx: m['name'],
        action             = edit_name,
    ))

    # --- Size ---
    size_options = list(MONSTER_SIZES.values()) + ['(none)']

    async def edit_size(ctx):
        await ctx.send('Sizes:')
        for i, s in enumerate(size_options, 1):
            await ctx.send(f'  {i}. {s}')
        raw = await ctx.prompt(f'Choose [1-{len(size_options)}]')
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(size_options):
                chosen   = size_options[idx]
                m['size'] = None if chosen == '(none)' else chosen
                dirty_ref[0] = True
            else:
                await ctx.send('Out of range, size unchanged.')
        elif raw:
            await ctx.send('Invalid input, size unchanged.')

    menu.add_item(MenuItem(
        text               = 'Size',
        shortcuts          = ['Z'],
        dot_leader_handler = lambda ctx: m['size'] or '(none)',
        action             = edit_size,
    ))

    # --- Strength ---
    async def edit_strength(ctx):
        raw = await ctx.prompt(f"Strength [{m['strength']}]")
        if raw.isdigit():
            m['strength'] = int(raw)
            dirty_ref[0]  = True
        elif raw:
            await ctx.send('Invalid number, unchanged.')

    menu.add_item(MenuItem(
        text               = 'Strength',
        shortcuts          = ['S'],
        dot_leader_handler = lambda ctx: str(m['strength']),
        action             = edit_strength,
    ))

    # --- Special weapon ---
    async def edit_weapon(ctx):
        if weapons:
            items = sorted(weapons.items())
            await ctx.send('  *. Any / clear weapon')
            for num, name in items:
                await ctx.send(f'  {num:>3}. {name}')
            raw = await ctx.prompt("Weapon # ('*' to clear)")
            if raw == '*':
                m['special_weapon'] = 0
                dirty_ref[0] = True
            elif raw.isdigit():
                wid = int(raw)
                if wid in dict(items):
                    m['special_weapon'] = wid
                    dirty_ref[0] = True
                else:
                    await ctx.send('Unknown weapon number.')
        else:
            raw = await ctx.prompt(f"Special weapon # [{m['special_weapon']}]")
            if raw.isdigit():
                m['special_weapon'] = int(raw)
                dirty_ref[0] = True

    wpn_label = lambda ctx: (weapons.get(m['special_weapon'],
                              f"#{m['special_weapon']}")
                              if m['special_weapon'] else '(none)')
    menu.add_item(MenuItem(
        text               = 'Special weapon',
        shortcuts          = ['W'],
        dot_leader_handler = wpn_label,
        action             = edit_weapon,
    ))

    # --- To-hit ---
    async def edit_to_hit(ctx):
        raw = await ctx.prompt(f"To-hit % [{m['to_hit']}]")
        if raw.isdigit():
            m['to_hit']  = int(raw)
            dirty_ref[0] = True
        elif raw:
            await ctx.send('Invalid number, unchanged.')

    menu.add_item(MenuItem(
        text               = 'To-hit %',
        shortcuts          = ['T'],
        dot_leader_handler = lambda ctx: str(m['to_hit']),
        action             = edit_to_hit,
    ))

    # --- Description ---
    async def edit_desc(ctx):
        current = m.get('description') or ''
        raw     = await ctx.prompt(f'Description [{current or "none"}]')
        if raw:
            m['description'] = raw
            dirty_ref[0]     = True
        elif current:
            clear = await input_yes_no(ctx, 'Clear description?')
            if clear:
                m['description'] = None
                dirty_ref[0]     = True

    menu.add_item(MenuItem(
        text               = 'Description',
        shortcuts          = ['D'],
        dot_leader_handler = lambda ctx: (m.get('description') or '')[:40] or '(none)',
        action             = edit_desc,
    ))

    # --- Quote ---
    async def edit_quote(ctx):
        if not quotes:
            await ctx.send('No quotes loaded.')
            return

        async def on_select(ctx, qnum):
            m['quote_number']            = qnum
            m.setdefault('flags', {})['has_quote'] = True
            dirty_ref[0]                 = True
            await ctx.send(f'Quote #{qnum} selected.')

        quote_menu = build_quote_menu(m, quotes, on_select)
        await run_menu(ctx, quote_menu)

    qnum = m.get('quote_number')
    menu.add_item(MenuItem(
        text               = 'Quote',
        shortcuts          = ['Q'],
        dot_leader_handler = lambda ctx: (f'#{m.get("quote_number")}' if m.get('quote_number') else '(none)'),
        action             = edit_quote,
    ))

    # --- Flags (submenu) ---
    async def open_flags(ctx):
        flags_menu = build_flags_menu(m, dirty_ref)
        await run_menu(ctx, flags_menu)

    menu.add_item(MenuItem(
        text               = 'Flags',
        shortcuts          = ['F'],
        dot_leader_handler = lambda ctx: ', '.join(active_flags(m)) or '(none)',
        action             = open_flags,
    ))

    return menu


# ---------------------------------------------------------------------------
# Per-monster menu
# ---------------------------------------------------------------------------

def build_monster_list_menu(monsters: list[dict], quotes: dict[int, str],
                            weapons: dict[int, str],
                            locations: dict[int, list],
                            dirty_ref: list) -> Menu:
    """Build the monster list menu, each item going straight to the edit menu."""
    menu = Menu(title='Select Monster')
    for m in monsters:
        async def show_and_edit(ctx, mon=m):
            await show_monster(ctx, mon, quotes, weapons, locations)
            await run_menu(ctx, build_edit_menu(mon, quotes, weapons, dirty_ref))
        menu.add_item(MenuItem(
            text      = f"#{m['number']:>3} {m['name']}",
            shortcuts = [],
            action    = show_and_edit,
        ))
    return menu


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

async def search_by_name(ctx, monsters: list[dict],
                         quotes, weapons, locations, dirty_ref):
    term    = await ctx.prompt('Search name')
    results = [m for m in monsters if term.upper() in m['name']]
    if not results:
        await ctx.send('No matches.')
        return
    menu = Menu(title=f'Results for "{term}"')
    for m in results:
        menu.add_item(MenuItem(
            text      = f"#{m['number']:>3} {m['name']}",
            shortcuts = [],
            action    = lambda ctx, mon=m: run_menu(
                ctx, build_monster_menu(mon, quotes, weapons, locations, dirty_ref)),
        ))
    await run_menu(ctx, menu)


async def search_by_flag(ctx, monsters: list[dict]):
    flag_menu = Menu(title='Select Flag')
    for key in ALL_FLAG_KEYS:
        label = monster_flag_labels.get(key, key)
        count = sum(1 for m in monsters if m.get('flags', {}).get(key))

        def make_action(k=key, lbl=label):
            async def _show(ctx):
                results = [m for m in monsters if m.get('flags', {}).get(k)]
                if not results:
                    await ctx.send(f'No monsters with flag: {lbl}')
                    return
                await ctx.send(f'\nMonsters with [{lbl}]:')
                for m in results:
                    await ctx.send(f"  #{m['number']:>3} {m['name']}")
                await ctx.prompt('Press Enter to continue')
            return _show

        flag_menu.add_item(MenuItem(
            text               = label,
            dot_leader_handler = lambda ctx, k=key: str(
                sum(1 for m in monsters if m.get('flags', {}).get(k))),
            action             = make_action(),
        ))
    await run_menu(ctx, flag_menu)


async def search_by_attribute(ctx, monsters: list[dict], weapons: dict[int, str]):
    searchable = [
        ('status',         'Status',         int),
        ('size',           'Size',           str),
        ('strength',       'Strength',       int),
        ('special_weapon', 'Special weapon', int),
        ('to_hit',         'To-hit %',       int),
    ]
    attr_menu = Menu(title='Search by attribute')
    for attr, label, typ in searchable:
        def make_action(a=attr, lbl=label, t=typ):
            async def _search(ctx):
                if a == 'special_weapon' and weapons:
                    items = sorted(weapons.items())
                    await ctx.send('  *. Any non-zero special weapon')
                    for num, name in items:
                        await ctx.send(f'  {num:>3}. {name}')
                    raw = await ctx.prompt("Weapon # or '*' for any")
                    if raw == '*':
                        results = [m for m in monsters if m.get('special_weapon', 0)]
                        await header(ctx, 'Monsters requiring any special weapon')
                    elif raw.isdigit():
                        tid  = int(raw)
                        results = [m for m in monsters if m.get('special_weapon') == tid]
                        await header(ctx, f'Monsters requiring: {weapons.get(tid, f"#{tid}")}')
                    else:
                        return
                elif t == int:
                    raw = await ctx.prompt(f'{lbl} (exact value)')
                    if not raw.lstrip('-').isdigit():
                        await ctx.send('Invalid number.')
                        return
                    val     = int(raw)
                    results = [m for m in monsters if m.get(a) == val]
                    await header(ctx, f'Monsters with {lbl} = {val}')
                else:
                    raw     = await ctx.prompt(f'{lbl} (substring match)')
                    results = [m for m in monsters
                               if raw.lower() in str(m.get(a, '')).lower()]
                    await header(ctx, f'Monsters with {lbl} matching "{raw}"')

                if not results:
                    await ctx.send('  No matches.')
                else:
                    for m in results:
                        wpn_id  = m.get('special_weapon', 0)
                        wpn_str = (f'  [{weapons.get(wpn_id, f"#{wpn_id}")}]'
                                   if wpn_id and weapons else '')
                        await ctx.send(f"  #{m['number']:>3} {m['name']}{wpn_str}")
                await ctx.prompt('Press Enter to continue')
            return _search

        attr_menu.add_item(MenuItem(text=label, action=make_action()))
    await run_menu(ctx, attr_menu)


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

async def main():
    ctx = TerminalContext()

    try:
        monsters = load_monsters(MONSTER_FILE)
    except FileNotFoundError:
        await ctx.send(f"'{MONSTER_FILE}' not found. Run convert_monster_data.py first.")
        sys.exit(1)

    quotes    = load_quotes(QUOTES_FILE)
    weapons   = load_weapons(WEAPONS_FILE)
    locations = load_monster_locations(LEVEL_FILES)

    # dirty_ref: one-element list so closures can mutate it
    dirty_ref = [False]

    # --- Main menu ---
    main_menu = Menu(title='Monster Editor')

    main_menu.add_item(MenuItem(
        text               = 'Monster count',
        dot_leader_handler = lambda ctx: str(len(monsters)),
    ))

    main_menu.add_item(MenuItem(
        text               = 'Unsaved changes',
        dot_leader_handler = lambda ctx: '*YES*' if dirty_ref[0] else 'No',
    ))

    main_menu.add_item(MenuItem(text='List / edit monsters', shortcuts=['L'],
        action=lambda ctx: run_menu(
            ctx, build_monster_list_menu(
                monsters, quotes, weapons, locations, dirty_ref))))

    main_menu.add_item(MenuItem(text='Search by name',      shortcuts=['N'],
        action=lambda ctx: search_by_name(
            ctx, monsters, quotes, weapons, locations, dirty_ref)))

    main_menu.add_item(MenuItem(text='Search by flag',      shortcuts=['F'],
        action=lambda ctx: search_by_flag(ctx, monsters)))

    main_menu.add_item(MenuItem(text='Search by attribute', shortcuts=['A'],
        action=lambda ctx: search_by_attribute(ctx, monsters, weapons)))

    async def do_save(ctx):
        save_monsters(monsters, MONSTER_FILE)
        dirty_ref[0] = False
        await ctx.send(f"Saved {len(monsters)} monsters to '{MONSTER_FILE}'.")

    main_menu.add_item(MenuItem(text='Save', shortcuts=['S'], action=do_save))

    await run_menu(ctx, main_menu)

    if dirty_ref[0]:
        if await input_yes_no(ctx, 'Unsaved changes. Save before quitting?'):
            save_monsters(monsters, MONSTER_FILE)


if __name__ == '__main__':
    logging.basicConfig(format='%(levelname)10s | %(funcName)20s() | %(message)s',
                        level=logging.DEBUG)
    run_local(main())
