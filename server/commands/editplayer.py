"""commands/editplayer.py

Interactive player editor — admin tool for viewing and modifying player data.

Menu layout mirrors the original C64 TADA Player Editor (tep v2.07):

  Player Editor
  ├─  1. Alignment         natural + current alignment
  ├─  2. Armor/Shield      armor / shield protection values
  ├─  3. Attributes        stats (CHA, CON, DEX, EGO, INT, STR, WIS, Energy)
  ├─  4. Character Names   player name; rename allies and horse
  ├─  5. Combinations      locker, elevator, castle, booby traps
  ├─  6. Flags/Counters    all PlayerFlags grouped by category
  ├─  7. Hit Points        current HP
  ├─  8. Inventory         give weapons/armor/rations/objects
  ├─  9. Map Information   dungeon level, room number
  ├─ 10. Money             in hand / in bank / in bar
  ├─ 11. Statistics        age, birthday, class, experience, guild, race,
  │                        moves to date, monsters killed
  └─ 12. Weapons           readied weapon, per-weapon battle experience
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
        category    = HelpCategory.ADMINISTRATIVE,
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


async def _apply_and_report_alignment(ctx, player) -> None:
    """Recompute natural_alignment from the player's current race and say so.

    Race, not class, actually drives this (SPUR.MISC5.S:196-199) -- called
    after either edit anyway so an admin sees the same message regardless
    of which field they touched, and editing class alone correctly reports
    "unchanged" since it never affects the result.
    """
    from characters import apply_natural_alignment
    changed, new_alignment = apply_natural_alignment(player)
    if changed:
        player.unsaved_changes = True
        await ctx.send(f'Natural alignment updated to {new_alignment.value}.')
    else:
        await ctx.send(f'Natural alignment unchanged ({new_alignment.value}).')


async def _warn_if_incompatible(ctx, player) -> None:
    """Flag a class/race combo character creation would refuse outright.

    Same table as commands/new_player.py's validate_class_race_combo() (both
    call characters.is_class_race_compatible()), but non-blocking here — an
    admin editing class and race as two separate menu actions may well want
    an "invalid" combo mid-edit, or deliberately for testing, so this only
    warns instead of rejecting the change.
    """
    from characters import is_class_race_compatible
    char_class = getattr(player, 'char_class', None)
    char_race  = getattr(player, 'char_race', None)
    if not is_class_race_compatible(char_class, char_race):
        await ctx.send(
            f'|yellow|Warning: {char_race.value} {char_class.value} is not '
            'normally a valid combination.|reset|'
        )


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
# Hit-points action
# ---------------------------------------------------------------------------

def _hp_action(ctx):
    async def action(ctx):
        p   = ctx.player
        cur = int(getattr(p, 'hit_points', 0) or 0)
        await ctx.send(f'Current HP: {cur}')
        val = await _prompt_int(ctx, 'Hit Points', cur, 0, 999)
        if val is not None:
            p.hit_points = val
            p.unsaved_changes = True
            await ctx.send(f'Hit points set to {val}.')
    return action


# ---------------------------------------------------------------------------
# Money menu
# ---------------------------------------------------------------------------

def _money_menu(ctx) -> Menu:
    from base_classes import PlayerMoneyTypes
    p    = ctx.player
    menu = Menu(title='Money')

    _entries = [
        (PlayerMoneyTypes.IN_HAND, 'In Hand', 'ih'),
        (PlayerMoneyTypes.IN_BANK, 'In Bank', 'ib'),
        (PlayerMoneyTypes.IN_BAR,  'In Bar',  'ir'),
    ]

    def _get(kind):
        return int(p.get_silver(kind) or 0)

    def make_action(kind, label):
        async def action(ctx):
            cur = _get(kind)
            val = await _prompt_int(ctx, label, cur, 0, 9_999_999)
            if val is not None:
                p.set_silver_absolute(kind, val)
                p.unsaved_changes = True
                await ctx.send(f'{label} set to {val:,} silver.')
        return action

    for kind, label, sc in _entries:
        menu.add_item(MenuItem(
            label,
            shortcuts=sc,
            dot_leader_handler=lambda ctx, k=kind: f'{_get(k):,}',
            action=make_action(kind, label),
        ))
    return menu


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def _build_main_menu(ctx) -> Menu:
    menu = Menu(title=f'Player Editor — {ctx.player.name}')
    menu.add_item(MenuItem('Alignment',        shortcuts='al', submenu=_alignment_menu(ctx)))
    menu.add_item(MenuItem('Armor/Shield',     shortcuts='as', submenu=_armor_shield_menu(ctx)))
    menu.add_item(MenuItem('Attributes',       shortcuts='at', submenu=_attributes_menu(ctx)))
    menu.add_item(MenuItem('Character Names',  shortcuts='cn', submenu=_names_menu(ctx)))
    menu.add_item(MenuItem('Combinations',     shortcuts='co', submenu=_combinations_menu(ctx)))
    menu.add_item(MenuItem('Flags/Counters',   shortcuts='fl', submenu=_flags_menu(ctx)))
    menu.add_item(MenuItem('Hit Points',       shortcuts='hp', action=_hp_action(ctx)))
    menu.add_item(MenuItem('Inventory',        shortcuts='in', action=_inventory_action(ctx)))
    menu.add_item(MenuItem('Map Information',  shortcuts='mi', submenu=_map_info_menu(ctx)))
    menu.add_item(MenuItem('Money',            shortcuts='mo', submenu=_money_menu(ctx)))
    menu.add_item(MenuItem('Statistics',       shortcuts='st', submenu=_statistics_menu(ctx)))
    menu.add_item(MenuItem('Weapons',          shortcuts='we', submenu=_weapons_menu(ctx)))
    return menu


# ---------------------------------------------------------------------------
# Armor/Shield menu
# ---------------------------------------------------------------------------

def _armor_shield_menu(ctx) -> Menu:
    p    = ctx.player
    menu = Menu(title='Armor/Shield')

    def _get(attr: str) -> int:
        return int(getattr(p, attr, 0) or 0)

    def make_action(attr: str, label: str):
        async def action(ctx):
            cur = _get(attr)
            val = await _prompt_int(ctx, label, cur, 0, 999)
            if val is not None:
                setattr(p, attr, val)
                p.unsaved_changes = True
                await ctx.send(f'{label} set to {val}.')
        return action

    menu.add_item(MenuItem(
        'Armor', shortcuts='ar',
        dot_leader_handler=lambda ctx: str(_get('armor')),
        action=make_action('armor', 'Armor'),
    ))
    menu.add_item(MenuItem(
        'Shield', shortcuts='sh',
        dot_leader_handler=lambda ctx: str(_get('shield')),
        action=make_action('shield', 'Shield'),
    ))
    return menu


# ---------------------------------------------------------------------------
# Map Information menu
# ---------------------------------------------------------------------------

def _map_info_menu(ctx) -> Menu:
    p    = ctx.player
    menu = Menu(title='Map Information')

    async def edit_level(ctx) -> None:
        cur = int(getattr(p, 'map_level', 1) or 1)
        val = await _prompt_int(ctx, 'Dungeon Level', cur, 1, 7)
        if val is not None:
            p.map_level = val
            p.unsaved_changes = True
            await ctx.send(f'Dungeon Level set to {val}.')

    async def edit_room(ctx) -> None:
        cur = int(getattr(p, 'map_room', 1) or 1)
        val = await _prompt_int(ctx, 'Room Number', cur, 1, 999)
        if val is not None:
            p.map_room = val
            p.unsaved_changes = True
            await ctx.send(f'Room Number set to {val}.')

    menu.add_item(MenuItem(
        'Dungeon Level', shortcuts='dl',
        dot_leader_handler=lambda ctx: str(getattr(p, 'map_level', '?')),
        action=edit_level,
    ))
    menu.add_item(MenuItem(
        'Room Number', shortcuts='rn',
        dot_leader_handler=lambda ctx: str(getattr(p, 'map_room', '?')),
        action=edit_room,
    ))
    return menu


# ---------------------------------------------------------------------------
# Weapons menu — readied weapon + per-weapon battle experience
# ---------------------------------------------------------------------------

def _weapons_menu(ctx) -> Menu:
    p    = ctx.player
    menu = Menu(title='Weapons')

    def _readied_label() -> str:
        w = getattr(p, 'readied_weapon', None)
        return getattr(w, 'name', None) or '(none)'

    async def clear_readied(ctx) -> None:
        weapon = getattr(p, 'readied_weapon', None)
        if weapon is None:
            await ctx.send('No weapon readied.')
            return
        name = getattr(weapon, 'name', '?')
        p.readied_weapon = None
        p.unsaved_changes = True
        await ctx.send(f'{name} unreadied.')

    async def edit_battle_exp(ctx) -> None:
        weapons = getattr(ctx.server, 'weapons', []) or []
        raw = await ctx.prompt('Weapon name (or part of name)')
        if not raw or not raw.strip():
            return
        term    = raw.strip().lower()
        matches = [w for w in weapons if term in (w.get('name') or '').lower()]
        chosen  = await _pick_from_matches(ctx, matches, lambda w: w.get('name', '?'))
        if chosen is None:
            if not matches:
                await ctx.send(f'No weapons matching "{raw.strip()}".')
            return
        key = str(chosen.get('number', 0))
        exp = getattr(p, 'weapon_experience', None)
        if exp is None:
            exp = {}
            p.weapon_experience = exp
        cur = int(exp.get(key, 0))
        val = await _prompt_int(ctx, f'Battle Exp — {chosen["name"]}', cur, 0, 99)
        if val is not None:
            exp[key] = val
            p.unsaved_changes = True
            await ctx.send(f'Battle experience with {chosen["name"]} set to {val}.')

    menu.add_item(MenuItem(
        'Readied Weapon', shortcuts='rw',
        dot_leader_handler=lambda ctx: _readied_label(),
        action=clear_readied,
    ))
    menu.add_item(MenuItem('Battle Experience', shortcuts='be', action=edit_battle_exp))
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


async def _rename_ally(ctx, ally) -> None:
    raw = await ctx.prompt(
        f"{ally.name}'s New Name",
        preamble_lines=[f'Current: {ally.name}', 'Blank to cancel:'],
    )
    if not raw or not raw.strip():
        await ctx.send('Name unchanged.')
        return
    old = ally.name
    ally.name = raw.strip()
    ctx.player.unsaved_changes = True
    await ctx.send(f'{old} renamed to {ally.name}.')


def _names_menu(ctx) -> Menu:
    from bar.allies import owned_allies
    from bar.ally_data import AllyFlags, AllyStatus

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

    def _ally_label(slot: int) -> str:
        allies = owned_allies(p)
        if slot >= len(allies):
            return '(empty)'
        a = allies[slot]
        tag = f' [{a.status.name}]' if a.status in (AllyStatus.UNCONSCIOUS, AllyStatus.DEAD) else ''
        return f'{a.name}  Str {a.strength}{tag}'

    async def edit_ally(ctx, slot: int) -> None:
        allies = owned_allies(p)
        if slot >= len(allies):
            await ctx.send('No ally in that slot.')
            return
        await _rename_ally(ctx, allies[slot])

    async def edit_horse(ctx) -> None:
        mount = next((a for a in owned_allies(p) if AllyFlags.MOUNT in (a.flags or [])), None)
        if mount is None:
            await ctx.send('No horse owned.')
            return
        await _rename_ally(ctx, mount)

    menu.add_item(MenuItem(
        'Player Name', shortcuts='p',
        dot_leader_handler=lambda ctx: p.name,
        action=edit_name,
    ))
    for i in range(3):
        menu.add_item(MenuItem(
            f'Ally {i + 1}', shortcuts=str(i + 1),
            dot_leader_handler=lambda ctx, s=i: _ally_label(s),
            action=lambda ctx, s=i: edit_ally(ctx, s),
        ))
    menu.add_item(MenuItem('Horse', shortcuts='h', action=edit_horse))
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
                'Enter three numbers like 04-05-09, X to clear, or blank to cancel:',
            ],
        )
        if not raw or not raw.strip():
            await ctx.send('Combination unchanged.')
            return
        if raw.strip().lower() == 'x':
            if isinstance(p.combinations, dict):
                obj = (p.combinations.get(combo_type)
                       or p.combinations.get(combo_type.value)
                       or p.combinations.get(combo_type.name))
                if obj is not None:
                    # All three alias keys (enum/.value/.name) point at the
                    # same Combination instance -- clearing .combination on
                    # it updates every alias at once, no dict surgery needed,
                    # and _fmt() already renders a None combination as
                    # '(none)'.
                    obj.combination = None
            await ctx.send(f'{combo_type.value} cleared.')
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
            p.unsaved_changes = True
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
        from characters import birthday_for_age
        cur = getattr(p, 'age', 0) or 0
        val = await _prompt_int(ctx, 'Age', cur, 15, 50)
        if val is not None:
            p.age = val
            p.unsaved_changes = True
            await ctx.send(f'Age set to {val}.')
            # Keep birthday's year consistent with the new age -- same
            # month/day, recomputed year (see edit_birthday()).
            old_birthday = getattr(p, 'birthday', None)
            if old_birthday is not None:
                p.birthday = birthday_for_age(val, old_birthday.month, old_birthday.day)
                await ctx.send(f'Birthday adjusted to {p.birthday.strftime("%B %d, %Y")}.')

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
            p.unsaved_changes = True
            await ctx.send(f'Class set to {options[idx].value}.')
            await _warn_if_incompatible(ctx, p)
            await _apply_and_report_alignment(ctx, p)

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
            from flags import PlayerFlags
            if options[idx] in (Guild.CLAW, Guild.SWORD, Guild.FIST):
                p.set_flag(PlayerFlags.GUILD_MEMBER)
            else:
                p.clear_flag(PlayerFlags.GUILD_MEMBER)
            p.unsaved_changes = True
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
            p.unsaved_changes = True
            await ctx.send(f'Race set to {options[idx].value}.')
            await _warn_if_incompatible(ctx, p)
            await _apply_and_report_alignment(ctx, p)

    async def edit_birthday(ctx) -> None:
        import calendar
        from characters import birthday_for_age
        cur = getattr(p, 'birthday', None)
        cur_str = cur.strftime('%B %d, %Y') if cur else '(not set)'
        raw = await ctx.prompt(
            'Birthday (MM-DD)',
            preamble_lines=[
                f'Current: {cur_str}',
                f"Birth year is derived from age ({getattr(p, 'age', 0) or 0}); enter month/day only.",
                'Blank to cancel:',
            ],
        )
        if not raw or not raw.strip():
            await ctx.send('Birthday unchanged.')
            return
        parts = raw.strip().split('-')
        try:
            month = int(parts[0])
            day   = int(parts[1])
            if not (1 <= month <= 12):
                raise ValueError
            # Validate against a leap year so Feb 29 is always accepted here;
            # birthday_for_age() falls back to Feb 28 if the derived year
            # (from age) isn't itself a leap year.
            max_day = calendar.monthrange(2000, month)[1]
            if not (1 <= day <= max_day):
                raise ValueError
        except (ValueError, IndexError):
            await ctx.send('Invalid date — expected MM-DD.')
            return
        p.birthday = birthday_for_age(getattr(p, 'age', 0), month, day)
        p.unsaved_changes = True
        await ctx.send(f'Birthday set to {p.birthday.strftime("%B %d, %Y")}.')

    async def edit_experience(ctx) -> None:
        cur_level = int(getattr(p, 'xp_level', 1) or 1)
        level = await _prompt_int(ctx, 'Character Level', cur_level, 1, 99)
        if level is not None:
            p.xp_level = level
            p.unsaved_changes = True

        cur_exp = int(getattr(p, 'experience', 0) or 0)
        exp = await _prompt_int(ctx, 'Experience Points', cur_exp, 0, 999_999)
        if exp is not None:
            p.experience = exp
            p.unsaved_changes = True

        await ctx.send(
            f'Level set to {getattr(p, "xp_level", "?")}, '
            f'Experience set to {getattr(p, "experience", "?")}.'
        )

    async def edit_moves(ctx) -> None:
        cur = int(getattr(p, 'moves_today', 0) or 0)
        val = await _prompt_int(ctx, 'Moves to Date', cur, 0, 999_999)
        if val is not None:
            p.moves_today = val
            p.unsaved_changes = True
            await ctx.send(f'Moves to date set to {val}.')

    async def edit_monsters_killed(ctx) -> None:
        monsters = getattr(ctx.server, 'monsters', []) or []
        killed = getattr(p, 'monsters_killed', None)
        if killed is None:
            killed = []
            p.monsters_killed = killed

        def _name_for(num) -> str:
            m = next((m for m in monsters if m.get('number') == num), None)
            return m.get('name', f'#{num}') if m else f'#{num}'

        while True:
            if killed:
                lines = ['Monsters killed:'] + [
                    f'  {i + 1}. {_name_for(n)}' for i, n in enumerate(killed)
                ]
            else:
                lines = ['Monsters killed: (none)']
            await ctx.send(lines)

            raw = await ctx.prompt('[A]dd  [R]emove  [Q]uit')
            if not raw or not raw.strip():
                break
            cmd = raw.strip().lower()[:1]

            if cmd == 'q':
                break
            elif cmd == 'a':
                term_raw = await ctx.prompt('Monster name (or part of name)')
                if not term_raw or not term_raw.strip():
                    continue
                term    = term_raw.strip().lower()
                matches = [m for m in monsters if term in (m.get('name') or '').lower()]
                chosen  = await _pick_from_matches(ctx, matches, lambda m: m.get('name', '?'))
                if chosen is None:
                    if not matches:
                        await ctx.send(f'No monsters matching "{term_raw.strip()}".')
                    continue
                num = chosen.get('number')
                if num in killed:
                    await ctx.send(f'{chosen["name"]} is already on the kill list.')
                else:
                    killed.append(num)
                    p.unsaved_changes = True
                    await ctx.send(f'Added {chosen["name"]} to kill list.')
            elif cmd == 'r':
                if not killed:
                    await ctx.send('Nothing to remove.')
                    continue
                idx_raw = await ctx.prompt(f'Remove which (1-{len(killed)})')
                try:
                    idx = int((idx_raw or '').strip()) - 1
                    if not (0 <= idx < len(killed)):
                        raise ValueError
                except ValueError:
                    await ctx.send('Invalid selection.')
                    continue
                removed = killed.pop(idx)
                p.unsaved_changes = True
                await ctx.send(f'Removed {_name_for(removed)} from kill list.')
            else:
                await ctx.send('Unknown option.')

    menu.add_item(MenuItem(
        'Age', shortcuts='ag',
        dot_leader_handler=lambda ctx: str(getattr(p, 'age', '?')),
        action=edit_age,
    ))
    menu.add_item(MenuItem(
        'Birthday', shortcuts='bi',
        dot_leader_handler=lambda ctx: (
            p.birthday.strftime('%b %d, %Y') if getattr(p, 'birthday', None) else '(not set)'
        ),
        action=edit_birthday,
    ))
    menu.add_item(MenuItem(
        'Class', shortcuts='cl',
        dot_leader_handler=lambda ctx: str(getattr(p, 'char_class', '?')),
        action=edit_class,
    ))
    menu.add_item(MenuItem(
        'Experience', shortcuts='ex',
        dot_leader_handler=lambda ctx: (
            f'L{getattr(p, "xp_level", "?")} / {getattr(p, "experience", "?")}'
        ),
        action=edit_experience,
    ))
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
    menu.add_item(MenuItem(
        'Moves to date', shortcuts='mo',
        dot_leader_handler=lambda ctx: str(getattr(p, 'moves_today', '?')),
        action=edit_moves,
    ))
    menu.add_item(MenuItem(
        'Monsters killed', shortcuts='mk',
        dot_leader_handler=lambda ctx: str(len(getattr(p, 'monsters_killed', None) or [])),
        action=edit_monsters_killed,
    ))
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


async def _send_labeled_list(ctx, header: str, items: list, label_fn) -> None:
    """Format and send *items* one per line via label_fn(item), matching
    _pick_from_matches()'s own labeling convention. Shared by the '?'
    inline listing in _give_ration()/_give_object()."""
    lines = [f'{header} ({len(items)}):']
    for item in items:
        lines.append(f'  {label_fn(item)}')
    await ctx.send(lines)


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


_READ_NUMBER_RE = re.compile(r'r\s*(\d+)', re.IGNORECASE)


async def _read_numbered_item(ctx, number: int) -> None:
    """Read inventory slot *number* (1-based, matching _show_inventory()'s
    numbering) by delegating to the real ReadCommand -- reuses all of its
    dispatch (scrap of paper/claim tag/scrolls/recovered book text)
    instead of duplicating any of it here."""
    inv = getattr(ctx.player, 'inventory', None)
    entries = list(inv.entries()) if inv and hasattr(inv, 'entries') else []
    if not (1 <= number <= len(entries)):
        await ctx.send('No such inventory item.')
        return
    name = getattr(entries[number - 1].item, 'name', '')
    from commands.read import ReadCommand
    await ReadCommand().execute(ctx, *name.split())


def _inventory_action(ctx):
    """Return an async action that drives the inventory management flow."""
    async def action(ctx):
        await _show_inventory(ctx)
        while True:
            raw = await ctx.prompt(
                'Command',
                preamble_lines=[
                    '[W]eapon  [A]rmor  [S]pell  [O]bject  [B]ook (r<#>=Read)  [R]ation',
                    '[L]ist weapons  [I]nventory  [Q]uit',
                ],
            )
            if raw is None:
                break
            stripped = raw.strip()

            read_match = _READ_NUMBER_RE.fullmatch(stripped)
            if read_match:
                await _read_numbered_item(ctx, int(read_match.group(1)))
                continue

            cmd = stripped.lower()[:1]

            if cmd in ('q', ''):
                break
            elif cmd == 'i':
                await _show_inventory(ctx)
            elif cmd == 'l':
                await _list_weapons(ctx)
            elif cmd == 'w':
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
    """Display the player's current inventory, numbered so 'r<#>' can
    read a book straight out of this list (see _inventory_action())."""
    inv = getattr(ctx.player, 'inventory', None)
    entries = list(inv.entries()) if inv and hasattr(inv, 'entries') else []
    if not entries:
        await ctx.send('Inventory is empty.')
        return
    lines = ['Current inventory:']
    for i, e in enumerate(entries, 1):
        name = getattr(e.item, 'name', '?')
        qty  = getattr(e, 'quantity', 1)
        lines.append(f'  {i:>2}. {name}' + (f' ×{qty}' if qty > 1 else ''))
    await ctx.send(lines)


async def _send_weapon_list(ctx, weapons) -> None:
    """Format and send a list of weapon dicts. Shared by _list_weapons()
    (the 'L' menu option) and _give_weapon()'s inline '?' listing."""
    lines = [f'Weapons ({len(weapons)}):']
    for w in weapons:
        lines.append(
            f'  #{w.get("number","?"):>3}  {w.get("name","?"):<22}'
            f'  {w.get("weapon_class",""):<12}  stability {w.get("stability", 0)}'
        )
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

    await _send_weapon_list(ctx, hits)


async def _give_weapon(ctx) -> None:
    """Search for a weapon by name and add it to the player's inventory."""
    weapons = getattr(ctx.server, 'weapons', []) or []
    if not weapons:
        await ctx.send('No weapon data loaded on server.')
        return

    while True:
        raw = await ctx.prompt("Weapon name (or part of name, '?' to list all)")
        if raw and raw.strip() == '?':
            await _send_weapon_list(ctx, weapons)
            continue
        break
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

    def _label(r):
        return f'{r.get("name","?"):<24}  [{r.get("kind","?")}]'

    while True:
        raw = await ctx.prompt("Ration name (or part of name, blank = show all, '?' to list all)")
        if raw and raw.strip() == '?':
            await _send_labeled_list(ctx, 'Rations', rations, _label)
            continue
        break
    term    = (raw or '').strip().lower()
    matches = [r for r in rations if term in (r.get('name') or '').lower()] if term else rations
    if not matches:
        await ctx.send(f'No rations matching "{raw.strip()}".')
        return

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

    def _label(o):
        return f'{o.get("name","?"):<28}  [{o.get("type","?")}]'

    while True:
        raw = await ctx.prompt(f"{label.capitalize()} name (or part of name, '?' to list all)")
        if raw and raw.strip() == '?':
            await _send_labeled_list(ctx, label.capitalize(), pool, _label)
            continue
        break
    if not raw or not raw.strip():
        return

    term    = raw.strip().lower()
    matches = [o for o in pool if term in (o.get('name') or '').lower()]
    if not matches:
        await ctx.send(f'No {label} matching "{raw.strip()}".')
        return

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
