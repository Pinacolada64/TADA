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
        ('Game Options', [
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
