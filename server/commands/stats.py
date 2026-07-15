#!/bin/env python3
"""stats command — port of the 'status' subroutine in SPUR.MISC5.S."""
from base_classes import (
    Alignment, Guild, PlayerMoneyTypes, PlayerRace, PlayerStat,
)
from combat.resolution import tier_label
from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import PlayerFlags
from network_context import GameContext

_AP = "'"


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
# Core display — returns list[str], no I/O
# ---------------------------------------------------------------------------

def _build_stats_lines(player) -> list[str]:
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
    sh = int(getattr(player, 'shield', 0) or 0)
    ar = int(getattr(player, 'armor',  0) or 0)

    silver_hand = player.get_silver(PlayerMoneyTypes.IN_HAND)
    silver_bank = player.get_silver(PlayerMoneyTypes.IN_BANK)
    silver_bar  = player.get_silver(PlayerMoneyTypes.IN_BAR)

    experience  = int(getattr(player, 'experience',    0) or 0)
    mk          = len(getattr(player, 'monsters_killed', []) or [])
    honor       = int(getattr(player, 'honor',         0) or 0)
    level       = int(getattr(player, 'xp_level',      1) or 1)

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
        f"{'Experience Pts:':>16} {experience:>5}   {'Hit Points:':>12} {player.hit_points:>3}",
        f"{'Monsters Kills:':>16} {mk:>5}   {'Player Level:':>12} {level:>3}",
        '',
    ]

    # Six ability scores, two per line (value + percentage)
    def stat_pair(label_l, val_l, label_r, val_r) -> str:
        pct_l = val_l * 4
        pct_r = val_r * 4
        return (
            f"{label_l:<10} {val_l:>2} {pct_l:>4}%   "
            f"{label_r:<10} {val_r:>2} {pct_r:>4}%"
        )

    lines += [
        stat_pair("Strength:",  ps, "Const'n  :", pt),
        stat_pair("Intel   :",  pi, "Dexterity:", pd),
        stat_pair("Wisdom  :",  pw, "Energy   :", pe),
        '',
    ]

    # Shield / armor
    lines += [
        f"{'Shield  :':>10}    {sh:>3}%   {'Armor    :':>10}   {ar:>3}%",
    ]

    # Shield skill: real tracked per-item proficiency (player.shield_
    # proficiency, keyed by player.active_shield_id, 0-99), incremented per
    # successful block -- see player.py's gain_shield_proficiency() /
    # combat/resolution.py's shield_exp_bonus(). Previously a formula
    # stand-in (1 + level, doubled for Paladin); now that blocks are
    # actually tracked, this shows the real value for the currently
    # equipped shield (0 if no shield is equipped / identified).
    _active_shield_id = getattr(player, 'active_shield_id', None)
    _shield_prof = getattr(player, 'shield_proficiency', {}) or {}
    shield_skill = int(_shield_prof.get(str(_active_shield_id), 0)) if _active_shield_id is not None else 0
    shield_flag = getattr(PlayerFlags, 'SHIELD_TRAINED', None)
    shield_trained = ('Yes' if qf(shield_flag) else 'No') if shield_flag else 'No'
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
        f"Current alignment: {cur_align} ({honor} Honor points)",
        '',
    ]

    # Guild follower (only for guild members, vv>=3 in original)
    if guild != Guild.CIVILIAN:
        follower = 'On' if player.query_flag(PlayerFlags.GUILD_FOLLOW_MODE) else 'Off'
        lines.append(f"Guild Follow: {follower}")

    # Status conditions
    lines.append('POISONED!' if qf(PlayerFlags.POISON)  else 'Not poisoned')
    lines.append('DISEASED!' if qf(PlayerFlags.DISEASE) else 'Not diseased')

    if qf(PlayerFlags.RING_WORN):
        lines.append('Ring worn..')
    if qf(PlayerFlags.GAUNTLETS_WORN):
        lines.append('Gauntlets worn..')

    # Amulet of life
    if qf(PlayerFlags.AMULET_OF_LIFE_ENERGIZED) and player.inventory.find("Amulet of Life") is not None:
        lines.append('Amulet of life -  ENERGIZED!')
    else:
        # TODO: check if player (or ally) carries item #076 (Amulet of Life)
        pass

    # Wizard's glow
    if getattr(player, 'wizard_glow', False):
        lines.append("Wizard{_AP}s Glow spell active!".format(_AP=_AP))

    lines.append('')

    # World bosses
    lines.append(
        'King of the Wraiths: '
        + ('Dead..' if not qf(PlayerFlags.WRAITH_KING_ALIVE) else 'Alive..')
    )
    lines.append(
        'SPUR: ' + ('Alive!' if qf(PlayerFlags.SPUR_ALIVE) else 'Dead...')
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
            "status conditions, and world-state flags."
        ),
        usage    = [('stat', 'Show your stats')],
        examples = [('stat', 'Display your character sheet')],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        lines = _build_stats_lines(ctx.player)
        await ctx.send(lines)
        return CommandResult.ok()
