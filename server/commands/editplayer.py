"""commands/editplayer.py

Interactive player editor — admin tool for viewing and modifying player data.

Menu layout mirrors the original C64 TADA Player Editor (tep v2.07):

  Player Editor
  ├─  1. Alignment         natural + current alignment
  ├─  2. Armor/Shield      (stub)
  ├─  3. Attributes        stats (CHA, CON, DEX, EGO, INT, STR, WIS, Energy)
  ├─  4. Character Names   player name; allies and horse (stubs)
  ├─  5. Combinations      locker, elevator, castle, booby traps
  ├─  6. Flags/Counters    all PlayerFlags grouped by category
  ├─  7. Hit Points        (stub)
  ├─  8. Map Information   (stub)
  ├─  9. Money             (stub)
  ├─ 10. Statistics        age, class, guild, race, ...
  └─ 11. Weapons           (stub)
"""

import logging
import re
from typing import Optional

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import FlagDisplayTypes, PlayerFlags, new_player_default_flags
from menu_system import Menu, MenuItem, run_menu

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class EditPlayerCommand(Command):
    name    = 'editplayer'
    aliases = ['ep']
    modes   = {Mode.GAME}

    help = Help(
        summary     = 'Edit player attributes, flags, and settings.',
        description = 'Interactive editor for player data. Mirrors the original C64 player editor.',
        category    = HelpCategory.MISCELLANEOUS,
        usage       = [('editplayer', 'Open the interactive player editor.')],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        await ctx.send(f'|yellow|Player Editor|reset| — {ctx.player.name}')
        await run_menu(ctx, _build_main_menu(ctx))
        return CommandResult.ok('Player editor closed.')


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _flag_status(player, flag: PlayerFlags) -> str:
    """Return 'Yes'/'No' or 'On'/'Off' for the given flag."""
    status = player.query_flag(flag)
    for f, display_type, _ in new_player_default_flags:
        if f == flag:
            if display_type == FlagDisplayTypes.YESNO:
                return 'Yes' if status else 'No'
            break
    return 'On' if status else 'Off'


async def _not_implemented(ctx) -> None:
    await ctx.send('|yellow|Not implemented yet.|reset|')


async def _prompt_int(ctx, label: str, current: int,
                      lo: int, hi: int) -> Optional[int]:
    """Prompt for an integer in [lo, hi]. Returns None on cancel/bad input."""
    while True:
        raw = await ctx.prompt(
            f'{label} [{lo}-{hi}]',
            preamble_lines=[f'Current: {current}  —  blank to cancel'],
        )
        if raw is None or not raw.strip():
            return None
        try:
            val = int(raw.strip())
        except ValueError:
            await ctx.send('Please enter a number.')
            continue
        if lo <= val <= hi:
            return val
        await ctx.send(f'Enter a number between {lo} and {hi}.')


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def _build_main_menu(ctx) -> Menu:
    menu = Menu(title=f'Player Editor — {ctx.player.name}')
    menu.add_item(MenuItem('Alignment',        shortcuts='al', submenu=_alignment_menu(ctx)))
    menu.add_item(MenuItem('Armor/Shield',     shortcuts='as', action=_not_implemented))
    menu.add_item(MenuItem('Attributes',       shortcuts='at', submenu=_attributes_menu(ctx)))
    menu.add_item(MenuItem('Character Names',  shortcuts='cn', submenu=_names_menu(ctx)))
    menu.add_item(MenuItem('Combinations',     shortcuts='co', submenu=_combinations_menu(ctx)))
    menu.add_item(MenuItem('Flags/Counters',   shortcuts='fl', submenu=_flags_menu(ctx)))
    menu.add_item(MenuItem('Hit Points',       shortcuts='hp', action=_not_implemented))
    menu.add_item(MenuItem('Inventory',        shortcuts='in', action=_inventory_action(ctx)))
    menu.add_item(MenuItem('Map Information',  shortcuts='mi', action=_not_implemented))
    menu.add_item(MenuItem('Money',            shortcuts='mo', action=_not_implemented))
    menu.add_item(MenuItem('Statistics',       shortcuts='st', submenu=_statistics_menu(ctx)))
    menu.add_item(MenuItem('Weapons',          shortcuts='we', action=_not_implemented))
    return menu


# ---------------------------------------------------------------------------
# Submenus
# ---------------------------------------------------------------------------

def _alignment_menu(ctx) -> Menu:
    from base_classes import Alignment
    p    = ctx.player
    menu = Menu(title='Alignment')

    async def edit_alignment(ctx, attr: str, label: str) -> None:
        options  = list(Alignment)
        current  = getattr(p, attr, None)
        preamble = [f'Current: {current}'] + [
            f'{i+1}: {a.value}' for i, a in enumerate(options)
        ]
        raw = await ctx.prompt(label, preamble_lines=preamble)
        if not raw or not raw.strip().isdigit():
            await ctx.send(f'{label} unchanged.')
            return
        idx = int(raw.strip()) - 1
        if 0 <= idx < len(options):
            setattr(p, attr, options[idx])
            await ctx.send(f'{label} set to {options[idx].value}.')
        else:
            await ctx.send('Invalid selection.')

    menu.add_item(MenuItem(
        'Natural Alignment', shortcuts='n',
        dot_leader_handler=lambda ctx: str(getattr(p, 'natural_alignment', '?')),
        action=lambda ctx: edit_alignment(ctx, 'natural_alignment', 'Natural Alignment'),
    ))
    menu.add_item(MenuItem(
        'Current Alignment', shortcuts='c',
        dot_leader_handler=lambda ctx: str(getattr(p, 'current_alignment', '?')),
        action=lambda ctx: edit_alignment(ctx, 'current_alignment', 'Current Alignment'),
    ))
    return menu


def _attributes_menu(ctx) -> Menu:
    from base_classes import PlayerStat
    p    = ctx.player
    menu = Menu(title='Attributes')

    # Per the BASIC: attributes 1-7 are capped at 18, Energy at 25.
    _range = {PlayerStat.EGY: (1, 25)}

    def _get(stat):
        if hasattr(p, 'get_stat'):
            return p.get_stat(stat)
        return (p.stats or {}).get(stat, 0)

    def _set(stat, val):
        if hasattr(p, 'set_stat_absolute'):
            p.set_stat_absolute(stat, val)
        else:
            p.stats[stat] = val

    def make_action(stat):
        lo, hi = _range.get(stat, (1, 18))
        async def action(ctx):
            val = await _prompt_int(ctx, stat.value, _get(stat), lo, hi)
            if val is not None:
                _set(stat, val)
                await ctx.send(f'{stat.value} set to {val}.')
        return action

    for stat in PlayerStat:
        menu.add_item(MenuItem(
            stat.value,
            shortcuts=stat.name[:2].lower(),
            dot_leader_handler=lambda ctx, s=stat: str(_get(s)),
            action=make_action(stat),
        ))
    return menu


def _names_menu(ctx) -> Menu:
    p    = ctx.player
    menu = Menu(title='Character Names')

    async def edit_name(ctx) -> None:
        raw = await ctx.prompt(
            'Player Name',
            preamble_lines=[f'Current: {p.name}', 'Blank to cancel:'],
        )
        if not raw or not raw.strip():
            await ctx.send('Name unchanged.')
            return
        p.name = raw.strip()
        await ctx.send(f'Name changed to: {p.name}')

    menu.add_item(MenuItem(
        'Player Name', shortcuts='p',
        dot_leader_handler=lambda ctx: p.name,
        action=edit_name,
    ))
    menu.add_item(MenuItem('Ally 1', shortcuts='1', action=_not_implemented))
    menu.add_item(MenuItem('Ally 2', shortcuts='2', action=_not_implemented))
    menu.add_item(MenuItem('Ally 3', shortcuts='3', action=_not_implemented))
    menu.add_item(MenuItem('Horse',  shortcuts='h', action=_not_implemented))
    return menu


def _combinations_menu(ctx) -> Menu:
    from base_classes import Combination, CombinationTypes
    p    = ctx.player
    menu = Menu(title='Combinations')

    def _fmt(combo_type) -> str:
        combos = getattr(p, 'combinations', None) or {}
        obj = (combos.get(combo_type)
               or combos.get(combo_type.value)
               or combos.get(combo_type.name))
        if obj is None:
            return '(none)'
        comb = getattr(obj, 'combination', None)
        if isinstance(comb, (list, tuple)) and len(comb) == 3:
            return '-'.join(f'{int(v):02d}' for v in comb)
        return str(comb or '(none)')

    async def edit_combo(ctx, combo_type) -> None:
        raw = await ctx.prompt(
            f'{combo_type.value} (xx-xx-xx)',
            preamble_lines=[
                f'Current: {_fmt(combo_type)}',
                'Enter three numbers like 04-05-09, or blank to cancel:',
            ],
        )
        if not raw or not raw.strip():
            await ctx.send('Combination unchanged.')
            return
        digits = re.findall(r'\d{1,2}', raw.strip())
        if len(digits) != 3:
            await ctx.send('Invalid format — expected three numbers e.g. 04-05-09.')
            return
        if not hasattr(p, 'combinations') or not isinstance(p.combinations, dict):
            p.combinations = {}
        combo = Combination(combo_type)
        combo.combination = tuple(int(d) for d in digits)
        p.combinations[combo_type] = combo
        p.combinations[combo_type.value] = combo
        p.combinations[combo_type.name]  = combo
        canonical = '-'.join(f'{int(d):02d}' for d in digits)
        await ctx.send(f'{combo_type.value} set to {canonical}.')

    for ct in CombinationTypes:
        menu.add_item(MenuItem(
            ct.value,
            shortcuts=ct.name[:2].lower(),
            dot_leader_handler=lambda ctx, c=ct: _fmt(c),
            action=lambda ctx, c=ct: edit_combo(ctx, c),
        ))
    return menu


def _flags_menu(ctx) -> Menu:
    p    = ctx.player
    menu = Menu(title='Flags/Counters')

    # Groups mirror the BASIC's two-page layout (lines {:3010} and {:3115}).
    _groups = [
        ('Option Toggles', [
            PlayerFlags.EXPERT_MODE,
            PlayerFlags.HOURGLASS,
            PlayerFlags.MORE_PROMPT,
            PlayerFlags.ROOM_DESCRIPTIONS,
            PlayerFlags.DEBUG_MODE,
        ]),
        ('Player Status', [
            PlayerFlags.ADMIN,
            PlayerFlags.ARCHITECT,
            PlayerFlags.DUNGEON_MASTER,
            PlayerFlags.ORATOR,
            PlayerFlags.GUILD_AUTODUEL,
            PlayerFlags.GUILD_FOLLOW_MODE,
            PlayerFlags.GUILD_MEMBER,
            PlayerFlags.DISEASE,
            PlayerFlags.HUNGER,
            PlayerFlags.POISON,
            PlayerFlags.THIRST,
            PlayerFlags.TIRED,
            PlayerFlags.UNCONSCIOUS,
            PlayerFlags.HAS_HORSE,
            PlayerFlags.MOUNTED,
        ]),
        ('Game Objectives', [
            PlayerFlags.AMULET_OF_LIFE_ENERGIZED,
            PlayerFlags.COMPASS_USED,
            PlayerFlags.DWARF_ALIVE,
            PlayerFlags.GAUNTLETS_WORN,
            PlayerFlags.RING_WORN,
            PlayerFlags.SPUR_ALIVE,
            PlayerFlags.THUG_ATTACK,
            PlayerFlags.WRAITH_KING_ALIVE,
            PlayerFlags.WRAITH_MASTER,
        ]),
    ]

    used: set = set()

    def _sc(flag: PlayerFlags) -> str:
        for n in range(1, len(flag.name) + 1):
            s = flag.name[:n].lower()
            if s not in used:
                used.add(s)
                return s
        return flag.name.lower()

    def make_toggle(flag: PlayerFlags):
        async def toggle(ctx):
            p.toggle_flag(flag)
            await ctx.send(f'{flag.value}: {_flag_status(p, flag)}')
        return toggle

    for section, flags in _groups:
        menu.add_item(MenuItem(text=f'— {section} —'))
        for flag in flags:
            menu.add_item(MenuItem(
                flag.value,
                shortcuts=_sc(flag),
                dot_leader_handler=lambda ctx, f=flag: _flag_status(p, f),
                action=make_toggle(flag),
            ))

    return menu


def _statistics_menu(ctx) -> Menu:
    p    = ctx.player
    menu = Menu(title='Statistics')

    async def edit_age(ctx) -> None:
        cur = getattr(p, 'age', 0) or 0
        val = await _prompt_int(ctx, 'Age', cur, 15, 50)
        if val is not None:
            p.age = val
            await ctx.send(f'Age set to {val}.')

    async def edit_class(ctx) -> None:
        from base_classes import PlayerClass
        options  = list(PlayerClass)
        preamble = [f'Current: {getattr(p, "char_class", "?")}'] + [
            f'{i+1}: {c.value}' for i, c in enumerate(options)
        ]
        raw = await ctx.prompt('Class', preamble_lines=preamble)
        if not raw or not raw.strip().isdigit():
            await ctx.send('Class unchanged.')
            return
        idx = int(raw.strip()) - 1
        if 0 <= idx < len(options):
            p.char_class = options[idx]
            await ctx.send(f'Class set to {options[idx].value}.')

    async def edit_guild(ctx) -> None:
        from base_classes import Guild
        options  = list(Guild)
        preamble = [f'Current: {getattr(p, "guild", "?")}'] + [
            f'{i+1}: {g.value}' for i, g in enumerate(options)
        ]
        raw = await ctx.prompt('Guild', preamble_lines=preamble)
        if not raw or not raw.strip().isdigit():
            await ctx.send('Guild unchanged.')
            return
        idx = int(raw.strip()) - 1
        if 0 <= idx < len(options):
            p.guild = options[idx]
            await ctx.send(f'Guild set to {options[idx].value}.')

    async def edit_race(ctx) -> None:
        from base_classes import PlayerRace
        options  = list(PlayerRace)
        preamble = [f'Current: {getattr(p, "char_race", "?")}'] + [
            f'{i+1}: {r.value}' for i, r in enumerate(options)
        ]
        raw = await ctx.prompt('Race', preamble_lines=preamble)
        if not raw or not raw.strip().isdigit():
            await ctx.send('Race unchanged.')
            return
        idx = int(raw.strip()) - 1
        if 0 <= idx < len(options):
            p.char_race = options[idx]
            await ctx.send(f'Race set to {options[idx].value}.')

    menu.add_item(MenuItem(
        'Age', shortcuts='ag',
        dot_leader_handler=lambda ctx: str(getattr(p, 'age', '?')),
        action=edit_age,
    ))
    menu.add_item(MenuItem('Birthday',   shortcuts='bi', action=_not_implemented))
    menu.add_item(MenuItem(
        'Class', shortcuts='cl',
        dot_leader_handler=lambda ctx: str(getattr(p, 'char_class', '?')),
        action=edit_class,
    ))
    menu.add_item(MenuItem('Experience', shortcuts='ex', action=_not_implemented))
    menu.add_item(MenuItem(
        'Guild', shortcuts='gu',
        dot_leader_handler=lambda ctx: str(getattr(p, 'guild', '?')),
        action=edit_guild,
    ))
    menu.add_item(MenuItem(
        'Race', shortcuts='ra',
        dot_leader_handler=lambda ctx: str(getattr(p, 'char_race', '?')),
        action=edit_race,
    ))
    menu.add_item(MenuItem('Moves to date',   shortcuts='mo', action=_not_implemented))
    menu.add_item(MenuItem('Monsters killed', shortcuts='mk', action=_not_implemented))
    return menu


# ---------------------------------------------------------------------------
# Inventory management
# ---------------------------------------------------------------------------

async def _pick_from_matches(ctx, matches: list, label_fn) -> Optional[object]:
    """Generic disambiguation prompt for a list of matches.

    label_fn(item) → str   — formats one item for the numbered list.

    Returns the selected item, or None if the user cancels or there are
    no matches.  Single-match lists are returned immediately without prompting.

    Use this anywhere you need to let the admin pick one item from a
    filtered list — weapons, rations, allies, items, etc.  Example:

        matches = [a for a in allies if term in a.name.lower()]
        chosen  = await _pick_from_matches(
            ctx, matches,
            lambda a: f'{a.name}  [{a.strength} str]',
        )
    """
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    lines = [f'{len(matches)} matches:']
    for i, item in enumerate(matches, 1):
        lines.append(f'  {i:>2}. {label_fn(item)}')
    await ctx.send(lines)

    raw = await ctx.prompt(f'Choose 1-{len(matches)}, or blank to cancel')
    if not raw or not raw.strip():
        return None
    try:
        idx = int(raw.strip()) - 1
        if not (0 <= idx < len(matches)):
            raise ValueError
    except ValueError:
        await ctx.send('Invalid selection.')
        return None
    return matches[idx]


def _weapon_from_dict(d: dict):
    """Build a Weapon item object from a weapons.json dict."""
    from items import Weapon
    from base_classes import WeaponClass
    _wc_map = {wc.value.lower(): wc for wc in WeaponClass}
    wc_str  = (d.get('weapon_class') or '').lower()
    wc      = _wc_map.get(wc_str)
    return Weapon(
        id_number   = d.get('number', 0),
        name        = d.get('name', '?'),
        kind        = d.get('kind'),
        stability   = d.get('stability', 0),
        to_hit      = d.get('to_hit', 0),
        price       = d.get('price', 0),
        weapon_class= wc,
        sound_effect= tuple(d.get('sound_effect') or ('', '')),
    )


def _inventory_action(ctx):
    """Return an async action that drives the inventory management flow."""
    async def action(ctx):
        await _show_inventory(ctx)
        while True:
            raw = await ctx.prompt(
                '[G]ive weapon  [A]rmor  [S]pell  [O]bject  [B]ook  [R]ation'
                '  [L]ist weapons  [I]nventory  [Q]uit',
            )
            if raw is None:
                break
            cmd = raw.strip().lower()[:1]

            if cmd in ('q', ''):
                break
            elif cmd == 'i':
                await _show_inventory(ctx)
            elif cmd == 'l':
                await _list_weapons(ctx)
            elif cmd == 'g':
                await _give_weapon(ctx)
            elif cmd == 'r':
                await _give_ration(ctx)
            elif cmd == 'a':
                await _give_object(ctx, {'armor', 'shield'}, 'armor/shield')
            elif cmd == 'b':
                await _give_object(ctx, {'book'}, 'book')
            elif cmd == 'o':
                _OBJ_TYPES = {'treasure', 'compass', 'container', 'ammunition',
                              'power', 'cursed'}
                await _give_object(ctx, _OBJ_TYPES, 'object')
            elif cmd == 's':
                await ctx.send('Spell giving not ready yet.')
            else:
                await ctx.send('Unknown option.')

    return action


async def _show_inventory(ctx) -> None:
    """Display the player's current inventory."""
    inv = getattr(ctx.player, 'inventory', None)
    entries = list(inv.entries()) if inv and hasattr(inv, 'entries') else []
    if not entries:
        await ctx.send('Inventory is empty.')
        return
    lines = ['Current inventory:']
    for e in entries:
        name = getattr(e.item, 'name', '?')
        qty  = getattr(e, 'quantity', 1)
        lines.append(f'  {name}' + (f' ×{qty}' if qty > 1 else ''))
    await ctx.send(lines)


async def _list_weapons(ctx) -> None:
    """List all weapons, optionally filtered by a search term."""
    weapons = getattr(ctx.server, 'weapons', []) or []
    raw  = await ctx.prompt('Search (blank = show all)')
    term = (raw or '').strip().lower()
    hits = [w for w in weapons if term in (w.get('name') or '').lower()] if term else weapons

    if not hits:
        await ctx.send(f'No weapons matching "{term}".')
        return

    lines = [f'Weapons ({len(hits)} found):']
    for w in hits:
        lines.append(
            f'  #{w.get("number","?"):>3}  {w.get("name","?"):<22}'
            f'  {w.get("weapon_class",""):<12}  stability {w.get("stability", 0)}'
        )
    await ctx.send(lines)


async def _give_weapon(ctx) -> None:
    """Search for a weapon by name and add it to the player's inventory."""
    weapons = getattr(ctx.server, 'weapons', []) or []
    if not weapons:
        await ctx.send('No weapon data loaded on server.')
        return

    raw = await ctx.prompt('Weapon name (or part of name)')
    if not raw or not raw.strip():
        return

    term    = raw.strip().lower()
    matches = [w for w in weapons if term in (w.get('name') or '').lower()]
    if not matches:
        await ctx.send(f'No weapons matching "{raw.strip()}".')
        return

    chosen = await _pick_from_matches(ctx, matches, lambda w: w.get('name', '?'))
    if chosen is None:
        return

    inv = getattr(ctx.player, 'inventory', None)
    if inv is None:
        await ctx.send('Player has no inventory object.')
        return

    if inv.add(_weapon_from_dict(chosen)):
        ctx.player.unsaved_changes = True
        await ctx.send(f'Added {chosen["name"]} to {ctx.player.name}\'s inventory.')
    else:
        await ctx.send('Inventory is full.')


async def _give_ration(ctx) -> None:
    """Search for a ration by name and add it to the player's inventory."""
    from items import Rations
    rations = getattr(ctx.server, 'rations', []) or []
    if not rations:
        await ctx.send('No ration data loaded on server.')
        return

    raw = await ctx.prompt('Ration name (or part of name, blank = show all)')
    term    = (raw or '').strip().lower()
    matches = [r for r in rations if term in (r.get('name') or '').lower()] if term else rations
    if not matches:
        await ctx.send(f'No rations matching "{raw.strip()}".')
        return

    def _label(r):
        return f'{r.get("name","?"):<24}  [{r.get("kind","?")}]'

    chosen = await _pick_from_matches(ctx, matches, _label)
    if chosen is None:
        return

    inv = getattr(ctx.player, 'inventory', None)
    if inv is None:
        await ctx.send('Player has no inventory object.')
        return

    item = Rations(
        number = chosen.get('number', 0),
        name   = chosen.get('name', '?'),
        kind   = chosen.get('kind', 'food'),
        price  = chosen.get('price', 0),
    )
    if inv.add(item):
        ctx.player.unsaved_changes = True
        await ctx.send(f'Added {chosen["name"]} to {ctx.player.name}\'s inventory.')
    else:
        await ctx.send('Inventory is full.')


async def _give_object(ctx, type_filter: set, label: str) -> None:
    """Search objects.json for items matching type_filter and add to inventory.

    Use this for any item category sourced from objects.json (server.items):
        armor/shield → _give_object(ctx, {'armor','shield'}, 'armor/shield')
        books        → _give_object(ctx, {'book'}, 'book')
        misc objects → _give_object(ctx, {'treasure','compass',...}, 'object')
    """
    from items import Item, ItemCategory
    all_objects = getattr(ctx.server, 'items', []) or []
    pool = [o for o in all_objects if (o.get('type') or '').lower() in type_filter]
    if not pool:
        await ctx.send(f'No {label} data loaded on server.')
        return

    raw = await ctx.prompt(f'{label.capitalize()} name (or part of name)')
    if not raw or not raw.strip():
        return

    term    = raw.strip().lower()
    matches = [o for o in pool if term in (o.get('name') or '').lower()]
    if not matches:
        await ctx.send(f'No {label} matching "{raw.strip()}".')
        return

    def _label(o):
        return f'{o.get("name","?"):<28}  [{o.get("type","?")}]'

    chosen = await _pick_from_matches(ctx, matches, _label)
    if chosen is None:
        return

    inv = getattr(ctx.player, 'inventory', None)
    if inv is None:
        await ctx.send('Player has no inventory object.')
        return

    item = Item(
        id_number = chosen.get('number', 0),
        name      = chosen.get('name', '?'),
        flags     = chosen.get('flags', {}),
        category  = ItemCategory.ITEM,
    )
    if inv.add(item):
        ctx.player.unsaved_changes = True
        await ctx.send(f'Added {chosen["name"]} to {ctx.player.name}\'s inventory.')
    else:
        await ctx.send('Inventory is full.')
