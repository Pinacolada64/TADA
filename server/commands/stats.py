#!/bin/env python3
"""stats command — port of the 'status' subroutine in SPUR.MISC5.S.

New in TADA: an Allies section (_build_stats_lines) -- SPUR's own STATS/
STAT2 output never mentions party composition at all, checked directly
against the source. Ryan's request."""
from base_classes import (
    Alignment, Guild, PlayerClass, PlayerMoneyTypes, PlayerRace, PlayerStat,
)
from combat.resolution import tier_label
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from items import ItemCategory
from network_context import GameContext

_AP = "'"

# Wizard's Glow duration. SPUR tracks this as a coarse 2-state flag
# decremented on login (SPUR.LOGON.S mid$(zu$,7,1): if instr(...,"23")
# active, else dissipated), not a round count. This port's Player.wizard_
# glow is already documented as "rounds left, decrement at every turn"
# (player.py), but nothing actually casts/decrements it yet -- no real
# spell-casting system exists (see TODO.md's "7/17/26" entry). This max
# is a placeholder for display purposes until that's built.
_WIZARD_GLOW_MAX_ROUNDS = 20


# ---------------------------------------------------------------------------
# Current alignment from honor points (vk, lines 199-201)
# ---------------------------------------------------------------------------

def _current_alignment(honor: int) -> str:
    """Map honor points to a display label (SPUR.MISC5.S lines 199-201).

    The honor scale has five bands; the middle three map to Alignment but
    the extremes ('Saintly' and the implied lowest evil) don't fit the
    three-value enum so we keep them as plain strings here.
    """
    if honor > 1600:
        return 'Saintly'
    if honor > 1200:
        return str(Alignment.GOOD)
    if honor > 799:
        return str(Alignment.NEUTRAL)
    if honor > 399:
        return 'Bad'
    return str(Alignment.EVIL)


# ---------------------------------------------------------------------------
# BHR formula: hp + (level*2) + ((energy+dex+str)/2) + ((shield+armor)/4)
# (SPUR.MISC5.S line 174)
# ---------------------------------------------------------------------------

def _bhr(player) -> int:
    stats    = getattr(player, 'stats', {})
    energy   = stats.get(PlayerStat.EGY, 0) or 0
    dex      = stats.get(PlayerStat.DEX, 0) or 0
    strength = stats.get(PlayerStat.STR, 0) or 0
    shield   = getattr(player, 'shield', 0) or 0
    armor    = getattr(player, 'armor',  0) or 0
    return int(
        player.hit_points
        + (int(getattr(player, 'xp_level', 1) or 1) * 2)
        + (energy + dex + strength) / 2
        + (shield + armor) / 4
    )


# ---------------------------------------------------------------------------
# Ally flag tags (New in TADA -- see _build_stats_lines's Allies section)
# ---------------------------------------------------------------------------

# Ordered so related flags read together: divinity, combat role, then
# Allies' Guild / Jake's Stable training. GOD/GODDESS are mutually
# exclusive with everything else in practice (SPUR NPCs), but the tags
# just reflect whatever flags are actually set.
_ALLY_FLAG_LABELS = [
    ('GOD',            'God'),
    ('GODDESS',        'Goddess'),
    ('ELITE',          'Elite'),
    ('MECHANICAL',     'Mechanical'),
    ('MOUNT',          'Mount'),
    ('SADDLED',        'Saddled'),
    ('ARMORED',        'Armored'),
    ('COMBAT_TRAINED', 'Combat Trained'),
    ('TRACKING',       'Tracking'),
    ('FIND_THINGS',    'Finder'),
    ('BODY_BUILD',     'Body Built'),
]


def _ally_weapon_display(ally) -> str:
    """Return the ally's readied weapon name, with rounds remaining appended
    for ammo-using weapons -- same needs_ammo test as the player's own
    "Weapon readied" line above (combat/resolution.py's _needs_ammo), so an
    ally's Uzi shows (12/50) just like the player's would. 'None' when
    nothing is readied (commands/give.py auto-readies a Weapon on GIVE, so
    this is only unset for allies never given one) -- Ryan's request, to
    read as "never readied" rather than a blank/placeholder dash.

    Parens, not brackets, around the round count: this return value gets
    wrapped in its own "[Wpn: ...]" Notes tag by the caller, and
    formatting.py's highlight_brackets() only understands one level of
    [...] nesting -- a second, inner "[12/50]" broke it, leaving a stray
    "]" and a color split mid-tag for ANSI clients. Found live via
    tools/bot_stat_weapon_ally_check.py against a real running server."""
    weapon = getattr(ally, 'readied_weapon', None)
    if weapon is None:
        return 'None'
    wc = getattr(weapon, 'weapon_class', None)
    wc_str = (wc.value if hasattr(wc, 'value') else str(wc)) if wc else ''
    needs_ammo = (wc_str in ('projectile', 'energy')
                  and 'STORM' not in (weapon.name or '').upper())
    if needs_ammo:
        ammo_rounds = int(getattr(ally, 'ammo_rounds', 0) or 0)
        ammo_max    = int(getattr(ally, 'ammo_max',    0) or 0)
        return f'{weapon.name} ({ammo_rounds}/{ammo_max})'
    return weapon.name


def _ally_worn_display(ally) -> str:
    """Return the ally's worn armor/shield names for the Notes "Worn" tag
    (commands/give.py auto-wears an armor- or shield-type Item on GIVE,
    same idea as _ally_weapon_display above for readied_weapon). 'None'
    when nothing is worn, joined with '/' when both slots are filled."""
    names = [getattr(w, 'name', None)
             for w in (getattr(ally, 'readied_armor', None), getattr(ally, 'readied_shield', None))
             if w is not None]
    return '/'.join(n for n in names if n) or 'None'


def _ally_flag_tags(ally) -> list[str]:
    """Return every AllyFlags member set on *ally* as "[Tag]" strings, in a
    fixed display order. Tracking/Finder/Body Built append their magnitude
    (ally.tracking_range / find_percentage / body_build) since those flags
    represent a level, not just an on/off trait."""
    from bar.ally_data import AllyFlags

    flags = ally.flags or []
    tags  = []
    for flag_name, label in _ALLY_FLAG_LABELS:
        flag = getattr(AllyFlags, flag_name, None)
        if flag is None or flag not in flags:
            continue
        if flag_name == 'TRACKING' and getattr(ally, 'tracking_range', 0):
            label = f'{label} r{ally.tracking_range}'
        elif flag_name == 'FIND_THINGS' and getattr(ally, 'find_percentage', 0):
            label = f'{label} {ally.find_percentage}%'
        elif flag_name == 'BODY_BUILD' and getattr(ally, 'body_build', 0):
            label = f'{label} +{ally.body_build}'
        tags.append(f'[{label}]')
    return tags


# ---------------------------------------------------------------------------
# Core display — returns list[str], no I/O
# ---------------------------------------------------------------------------

def _build_stats_lines(player, ctx=None) -> list[str]:
    stats  = getattr(player, 'stats', {})
    qf     = player.query_flag

    def st(key) -> int:
        return int(stats.get(key, 0) or 0)

    ps = st(PlayerStat.STR)
    pt = st(PlayerStat.CON)
    pi = st(PlayerStat.INT)
    pd = st(PlayerStat.DEX)
    pw = st(PlayerStat.WIS)
    pe = st(PlayerStat.EGY)
    pc = st(PlayerStat.CHR)
    sh = int(getattr(player, 'shield', 0) or 0)
    ar = int(getattr(player, 'armor',  0) or 0)

    silver_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)
    silver_bank = player.get_silver(PlayerMoneyTypes.IN_BANK)
    silver_bar  = player.get_silver(PlayerMoneyTypes.IN_BAR)

    experience  = int(getattr(player, 'experience',    0) or 0)
    mk          = int(getattr(player, 'monsters_killed', 0) or 0)
    honor       = int(getattr(player, 'honor',         0) or 0)
    level       = int(getattr(player, 'xp_level',      1) or 1)
    total_moves = int(getattr(player, 'moves_today',   0) or 0)

    guild           = getattr(player, 'guild',      Guild.CIVILIAN)
    char_class      = getattr(player, 'char_class', None)
    char_race       = getattr(player, 'char_race',  None)

    bhr = _bhr(player)

    lines: list[str] = []

    # Header
    lines += [
        f"{player.name}{_AP}s Current Stats: (BHR={bhr})",
        '',
    ]

    # Silver
    lines += [
        f"{'Silver - In Hand:':>20} {silver_hand:>12,}",
        f"{'         In Bank:':>20} {silver_bank:>12,}",
        f"{'         In Bar :':>20} {silver_bar:>12,}",
        '',
    ]

    # Experience / HP / kills / level
    lines += [
        f"{'Experience Pts:':>16} {experience:>5,}   {'Hit Pts:':>8} {player.hit_points:>3}",
        f"{'Monsters Killed:':>16} {mk:>5,}   {'Level:':>8} {level:>3}",
        f"{'Total Moves:':>16} {total_moves:>5,}",
        '',
    ]

    # Six ability scores, two per line (value + percentage)
    def stat_pair(label_l, val_l, label_r, val_r) -> str:
        pct_l = val_l * 4
        pct_r = val_r * 4
        return (
            f"{label_l:<10} {val_l:>2} {pct_l:>3}%   "
            f"{label_r:<10} {val_r:>2} {pct_r:>3}%"
        )

    lines += [
        stat_pair("Strength:",  ps, "Const'n  :", pt),
        stat_pair("Intel   :",  pi, "Dexterity:", pd),
        stat_pair("Wisdom  :",  pw, "Energy   :", pe),
        f"{'Charisma:':<10} {pc:>2} {pc * 4:>3}%",
        '',
    ]

    # Shield / armor -- percentage plus which item (by active_shield_id/
    # active_armor_id, set by commands/use.py's shield USE and every
    # commands/wear.py armor-equip path) is actually backing that rating,
    # looked up against ctx.server.items the same way commands/connect.py's
    # _login_equipment_lines() does. ctx is optional (many tests build
    # stats lines without one), so the name is omitted rather than looked
    # up when there's no ctx to resolve objects.json against.
    def _worn_name(item_id) -> str:
        if not item_id or ctx is None:
            return ''
        for raw in getattr(ctx.server, 'items', None) or []:
            number = raw.get('number') if isinstance(raw, dict) else getattr(raw, 'number', None)
            if number != item_id:
                continue
            name = raw.get('name') if isinstance(raw, dict) else getattr(raw, 'name', None)
            return f' ({name})' if name else ''
        return ''

    # Readied weapon -- Ryan's request: name it, and if it's an ammo-using
    # weapon (projectile/energy, non-STORM -- same test as combat/
    # resolution.py's _needs_ammo, so STAT and actual combat agree on which
    # weapons show a round count) show rounds remaining out of the loaded
    # capacity (player.ammo_rounds/ammo_max, set by commands/use.py's ammo
    # branch).
    weapon = getattr(player, 'readied_weapon', None)
    if weapon is not None:
        wc = getattr(weapon, 'weapon_class', None)
        wc_str = (wc.value if hasattr(wc, 'value') else str(wc)) if wc else ''
        needs_ammo = (wc_str in ('projectile', 'energy')
                      and 'STORM' not in (weapon.name or '').upper())
        if needs_ammo:
            ammo_rounds = int(getattr(player, 'ammo_rounds', 0) or 0)
            ammo_max = int(getattr(player, 'ammo_max', 0) or 0)
            lines.append(f'Weapon readied: {weapon.name} [{ammo_rounds}/{ammo_max} rounds]')
        else:
            lines.append(f'Weapon readied: {weapon.name}')
    else:
        lines.append('Weapon readied: None')

    shield_name = _worn_name(getattr(player, 'active_shield_id', None))
    armor_name  = _worn_name(getattr(player, 'active_armor_id',  None))
    lines += [
        f"{'Shield  :':>10} {sh:>3}%{shield_name}   {'Armor    :':>10} {ar:>3}%{armor_name}",
    ]

    # Shield skill: real tracked per-item proficiency (player.shield_
    # proficiency, keyed by player.active_shield_id, 0-99), incremented per
    # successful block -- see player.py's gain_shield_proficiency() /
    # combat/resolution.py's shield_exp_bonus(). Previously a formula
    # stand-in (1 + level, doubled for Paladin); now that blocks are
    # actually tracked, this shows the real value for the currently
    # equipped shield (0 if no shield is equipped / identified).
    _active_shield_id = getattr(player, 'active_shield_id', None)
    _shield_prof      = getattr(player, 'shield_proficiency', {}) or {}
    shield_skill      = int(_shield_prof.get(str(_active_shield_id), 0)) if _active_shield_id is not None else 0
    shield_flag       = getattr(PlayerFlags, 'SHIELD_TRAINED', None)
    shield_trained    = ('Yes' if qf(shield_flag) else 'No') if shield_flag else 'No'
    lines += [
        f"Shield skill: {shield_skill} {tier_label(shield_skill)}, Formal training: {shield_trained}",
        '',
    ]

    # Class and race
    class_name = str(char_class).split('.')[-1].title() if char_class else 'Unknown'
    race_name  = str(char_race).split('.')[-1].title()  if char_race  else 'Unknown'
    lines += [
        f"Class : {class_name:<10}  Race: {race_name}",
    ]

    # Alignment
    from characters import natural_alignment_for_race
    nat_align = natural_alignment_for_race(char_race)
    cur_align = _current_alignment(honor)
    lines += [
        f"Natural alignment: {nat_align}.  ",
        f"Current alignment: {cur_align} ({honor:,} Honor points)",
        '',
    ]

    # Guild follower -- only for real guild members. SPUR gates this on
    # vv>=3 (SPUR.MISC5.S:202), and vv=1/2 (Civilian/Outlaw) are both
    # below that cutoff -- Outlaw was previously missed here (only
    # CIVILIAN was excluded), showing "Guild Follow" for a player who
    # isn't in Sword/Claw/Fist. Ryan's request.
    if guild not in (Guild.CIVILIAN, Guild.OUTLAW):
        follower = 'On' if player.query_flag(PlayerFlags.GUILD_FOLLOW_MODE) else 'Off'
        lines.append(f"Guild Follow: {follower}")

    # Status conditions
    lines.append('POISONED!' if qf(PlayerFlags.POISON)  else 'Not poisoned')
    lines.append('DISEASED!' if qf(PlayerFlags.DISEASE) else 'Not diseased')

    if qf(PlayerFlags.RING_WORN) and player.has_item(category=ItemCategory.ITEM, name="RING"):
        lines.append('Ring worn.')
    if qf(PlayerFlags.GAUNTLETS_WORN) and player.has_item(category=ItemCategory.ITEM, name="GAUNTLETS"):
        lines.append('Gauntlets worn.')

    # Amulet of life
    if qf(PlayerFlags.AMULET_OF_LIFE_ENERGIZED) and player.has_item(category=ItemCategory.ITEM, name="Amulet of Life"):
        lines.append('Amulet of life -  ENERGIZED!')
    else:
        # TODO: check if player (or ally) carries item #076 (Amulet of Life)
        pass

    # Wizard's Glow -- Ryan's request: show remaining rounds for Wizards
    # specifically, not just an on/off flag. "Not cast" when inactive
    # rather than "[0/20 rounds left]", which reads like it just ran
    # out rather than never having been cast at all.
    if char_class == PlayerClass.WIZARD:
        glow_rounds = int(getattr(player, 'wizard_glow', None) or 0)
        if glow_rounds > 0:
            lines.append(f'Wizard Glow: [{glow_rounds}/{_WIZARD_GLOW_MAX_ROUNDS} rounds left]')
        else:
            lines.append('Wizard Glow: Not cast')

    lines.append('')

    # New in TADA: SPUR.MISC5.S's "status" subroutine (STATS/STAT2) never
    # mentions allies at all -- Ryan asked for one, since a player's party
    # composition/condition is otherwise only visible via bar/fat_olaf.py's
    # shop menus or commands/editplayer.py's admin editor. Rendered as a
    # table.py Table (Ally/Str/HP/Hit%/Notes columns) per Ryan's request;
    # Notes carries every AllyFlags member (see _ally_flag_tags), any
    # non-default AllyStatus tag, a Wpn tag for the ally's readied weapon
    # (see _ally_weapon_display -- commands/give.py auto-readies a Weapon
    # on GIVE), and a Worn tag for readied_armor/readied_shield (see
    # _ally_worn_display -- commands/give.py auto-wears an armor/shield
    # Item the same way, added 2026-08-09). Not its own fixed-width table
    # column -- that starved Notes' width on narrow/C64 screens when tried
    # (see test_stats_allies.py's test_multiple_flags_all_tagged).
    from bar.ally_data import AllyStatus
    from bar.allies import owned_allies
    allies = owned_allies(player)
    lines.append(f"Allies: {len(allies)}/3")
    if allies:
        from table import Align, Column, Table, SINGLE

        if ctx is not None:
            from formatting import border_style_for_ctx
            border_style = border_style_for_ctx(ctx)
            width = getattr(ctx.player.client_settings, 'screen_columns', 78)
        else:
            border_style = SINGLE
            width = 78

        # C64's 40-column screen wraps a bordered table -- drop the
        # +--+ / | frame there and rely on padding alone. Ryan's request.
        # Zebra-striped cyan/light_blue rows with a white header, also
        # Ryan's request.
        t = Table(
            headers=[
                Column('Ally',  min_width=12),
                Column('Str',   align=Align.RIGHT, min_width=3),
                Column('HP',    align=Align.RIGHT, min_width=3),
                Column('Hit%',  align=Align.RIGHT, min_width=4),
                Column('Notes', min_width=6),
            ],
            border=(border_style != 'petscii'),
            border_style=border_style,
            header_color='white',
            text_color=['cyan', 'light_blue'],
        )
        for a in allies:
            status_tag = f'[{a.status.name}]' if a.status not in (AllyStatus.FREE, AllyStatus.SERVANT) else ''
            weapon_tag = f'[Wpn: {_ally_weapon_display(a)}]'
            worn_tag   = f'[Worn: {_ally_worn_display(a)}]'
            # Comma-delimited, not just space-joined -- Ryan's request, for
            # readability once a row carries several tags at once.
            notes = ', '.join(part for part in
                               (*_ally_flag_tags(a), status_tag, weapon_tag, worn_tag)
                               if part)
            t.add_row([a.name, str(a.strength), str(a.hit_points), f'{a.to_hit * 10}%', notes])
        lines.extend(t.render(width=width))
    else:
        lines.append('  No allies... sniff...')
    lines.append('')

    # World bosses
    lines.append(
        'King of the Wraiths: '
        + ('Alive!' if qf(PlayerFlags.WRAITH_KING_ALIVE) else 'Dead.')
    )
    lines.append(
        'SPUR: ' + ('Alive!' if qf(PlayerFlags.SPUR_ALIVE) else 'Dead.')
    )

    # Dwarf (encounters/dwarf.py) -- one shared world NPC/room/hoard, but
    # "have I personally killed him" is tracked per-player
    # (PlayerFlags.DWARF_ALIVE): once you kill him he stops robbing you
    # specifically, even though he keeps roaming/stealing from everyone
    # else until (if ever) they kill him too.
    dwarf_alive = qf(PlayerFlags.DWARF_ALIVE)
    if dwarf_alive:
        from config import config as server_config
        lines.append(f'Dwarf: Alive!  [{server_config.dwarf_silver:,} silver]')
    else:
        lines.append('Dwarf: Dead...')

    # Tut's treasure (quest #16, quests/tuts_treasure.py)
    tuts_treasure = getattr(player, 'tuts_treasure', None)
    if tuts_treasure and tuts_treasure.taken:
        tuts_status = 'Looted..'
    elif tuts_treasure and tuts_treasure.examined:
        tuts_status = 'Examined..'
    else:
        tuts_status = 'Somewhere..'
    lines.append("Tut{_AP}s Treasure: {status}".format(_AP=_AP, status=tuts_status))

    # Hourglass / time remaining
    time_remaining = getattr(player, 'time_remaining_minutes', None)
    if time_remaining is not None:
        lines.append(f'Hourglass: {time_remaining} mins.')

    return lines


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class StatCommand(Command):
    name    = 'stat'
    aliases = ['stats', 'status', 'score']
    modes   = {Mode.GAME}

    help = Help(
        category    = HelpCategory.GENERAL,
        summary     = "Show your current character stats",
        description = (
            "Displays your character sheet: money, ability scores, alignment, "
            "status conditions, allies, and world-state flags."
        ),
        usage    = [('stat', 'Show your stats')],
        examples = [('stat', 'STAT (also stats/status/score) takes no arguments -- '
                              "typing it displays your full character sheet: money, "
                              "ability scores, current alignment (see HONOR), Bad "
                              "Hombre Rating, status conditions, allies, and world-"
                              "state flags like The Dwarf, all in one screen.")],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        lines = _build_stats_lines(ctx.player, ctx)
        await ctx.send(lines)
        return CommandResult.ok()
