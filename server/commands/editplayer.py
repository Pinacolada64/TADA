"""commands/editplayer.py

Interactive player editor — admin tool for viewing and modifying player data.

Menu layout mirrors the original C64 TADA Player Editor (tep v2.07):

  Player Editor
  ├─  1. Alignment         natural + current alignment
  ├─  2. Armor/Shield      armor / shield protection values, shield skill
  ├─  3. Attributes        stats (CHR, CON, DEX, INT, STR, WIS, Energy)
  ├─  4. Character Names   player name; rename allies and horse
  ├─  5. Combinations      locker, elevator, castle, booby traps
  ├─  6. Command Settings  player.command_settings toggles (e.g. whereat hiding)
  ├─  7. Flags/Counters    all PlayerFlags grouped by category
  ├─  8. Hit Points        current HP for player, allies, and horse
  ├─  9. Inventory         give weapons/armor/rations/objects; transfer
  │                        items between characters
  ├─ 10. Map Information   dungeon level, room number; display/reset the
  │                        per-level visited-rooms bitfield (visited_rooms.py)
  ├─ 11. Money             in hand / in bank / in bar / Vinny Loan status
  ├─ 12. Statistics        age, birthday, class, experience, gender, guild,
  │                        honor, race, moves to date, monsters killed
  └─ 13. Weapons           readied weapon, per-weapon battle experience
"""

import logging
import re
from typing import Optional

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from flags import FlagDisplayTypes, PlayerFlags, new_player_default_flags
from menu_system import Menu, MenuItem, run_menu
from tada_utilities import player_class_display_name

log = logging.getLogger(__name__)


def _titled_menu(ctx, title: str) -> Menu:
    """Build a Menu whose title grows an '(unsaved changes)' tag whenever
    ctx.player.unsaved_changes is set. A callable title is re-evaluated on
    every redraw (see menu_system.Menu.rendered_title), so the tag appears
    the moment an edit happens and clears once the player saves, without
    needing to rebuild the menu."""
    def render():
        if getattr(ctx.player, 'unsaved_changes', False):
            return f'{title} |red|(unsaved changes)|reset|'
        return title
    return Menu(title=render)


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
        usage       = [
            ('editplayer', 'Open the interactive player editor for yourself.'),
            ('editplayer <playername>', "Edit another player's saved data. "
                                        'Offers to save (and, if that player '
                                        'is online, live-sync) on exit.'),
        ],
    )

    async def execute(self, ctx, *args) -> CommandResult:
        admin = ctx.player
        target_name = args[0] if args else None

        if not target_name or target_name.lower() == admin.name.lower():
            await ctx.send(f'|yellow|Player Editor|reset| — {admin.name}')
            await run_menu(ctx, _build_main_menu(ctx))
            return CommandResult.ok('Player editor closed.')

        found = await _find_character(ctx, target_name)
        if found is None:
            await ctx.send(f'No player found matching "{target_name}".')
            return CommandResult.fail('No such player.')
        live_player, is_online = found

        from player import Player
        if is_online:
            # Flush the live session's actual current state to disk before
            # building the edit buffer below -- without this, the edit
            # buffer loads whatever was last saved (e.g. at their last
            # login), missing anything picked up/changed since. Saving
            # target (with the admin's edits) back over that stale file
            # and then live_player._load()-ing it into the live session
            # further down would silently revert the connected player's
            # actual progress (inventory, HP, position, ...) to that old
            # snapshot. Found live: Gadget lost inventory items she'd
            # picked up mid-session the first time an admin ran editplayer
            # on her while she was online.
            live_player.save(force=True)
        # A fresh Player() with an id loads from disk in __init__ (see
        # Player._load()) -- an edit buffer fully decoupled from any live
        # session, even if *target_name* is online right now. Deliberately
        # not editing the live object directly: an admin bailing out with
        # 'N' at the save prompt below must leave a connected player's
        # actual session untouched. _find_character() above (also used by
        # the Inventory Transfer feature) is only needed here to resolve
        # the id and, if online, to know who to notify afterward.
        target = Player(name=live_player.name, id=live_player.id,
                        weapons_data=getattr(ctx.server, 'weapons', None))

        status = ' |cyan|(online)|reset|' if is_online else ''
        await ctx.send(f'|yellow|Player Editor|reset| — {target.name}{status}')

        ctx.player = target
        # Borrow the admin's real terminal settings for the duration of the
        # edit -- ctx.send()/ctx.prompt() format against ctx.player.
        # client_settings, and a freshly-loaded target only has default
        # settings, not the admin's actual screen width/translation/return
        # key. Must be restored below before any save, or the admin's
        # settings get persisted into the target's save file (found live:
        # editing Gadget's inventory clobbered her terminal settings with
        # the admin's).
        target_client_settings = target.client_settings
        target.client_settings = admin.client_settings
        try:
            await run_menu(ctx, _build_main_menu(ctx))
        finally:
            ctx.player = admin
            target.client_settings = target_client_settings

        if getattr(target, 'unsaved_changes', False):
            raw = await ctx.prompt(
                'Confirm',
                preamble_lines=[f'Save changes to {target.name}? (Y/N)'])
            if raw and raw.strip().lower().startswith('y'):
                target.save(force=True)
                await ctx.send(f'Saved {target.name}.')
                if is_online:
                    # Re-run the same _load() merge login uses to refresh
                    # the connected player's live object from what was
                    # just written to disk, instead of hand-copying fields.
                    live_player._load()
                    live_player.unsaved_changes = False
                    online_ctx = _online_ctx_for(ctx, live_player)
                    if online_ctx is not None:
                        await online_ctx.send(
                            '[You feel magically touched by the spirit of the '
                            'dungeon -- you feel different.]'
                        )
            else:
                await ctx.send('Changes discarded.')

        return CommandResult.ok('Player editor closed.')


def _online_ctx_for(ctx, player):
    """Return the connected client's ctx for *player*, or None if it can't
    be found (e.g. they disconnected while being edited)."""
    for client in getattr(ctx.server, 'clients', {}).values():
        other_ctx = getattr(client, 'ctx', None)
        if getattr(other_ctx, 'player', None) is player:
            return other_ctx
    return None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# RING_WORN/GAUNTLETS_WORN are otherwise-plain YESNO flags (see
# new_player_default_flags), but the flag alone doesn't mean much if the
# player isn't actually carrying the item -- mirrors stats.py's worn-item
# display, which gates on both the flag AND Player.has_item(). Ryan's
# request.
_WORN_ITEM_NAMES = {
    PlayerFlags.RING_WORN: 'RING',
    PlayerFlags.GAUNTLETS_WORN: 'GAUNTLETS',
}


def _flag_status(player, flag: PlayerFlags) -> str:
    """Return 'Yes'/'No' or 'On'/'Off' for the given flag -- except
    RING_WORN/GAUNTLETS_WORN, which report 'Not held' whenever the player
    doesn't actually have the item, and 'On'/'Off' otherwise."""
    item_name = _WORN_ITEM_NAMES.get(flag)
    if item_name is not None:
        from items import ItemCategory
        if not player.has_item(category=ItemCategory.ITEM, name=item_name):
            return 'Not held'
        return 'On' if player.query_flag(flag) else 'Off'
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
            preamble_lines=[f'Current: {current}  —  {ctx.player.return_key} to cancel'],
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


async def _prompt_battle_exp_value(ctx, label: str, current: int,
                                   lo: int = 0, hi: int = 99) -> Optional[int]:
    """Prompt for a battle-experience value: an absolute number in
    [lo, hi], or a +N/-N adjustment relative to *current*. Returns None
    on cancel/blank. int() already parses a leading +/- as a sign, so
    'current + int(text)' handles both the absolute and relative forms
    with the same line of code.
    """
    while True:
        raw = await ctx.prompt(
            f'{label} battle experience',
            preamble_lines=[
                f'Current: {current}  (enter {lo}-{hi}, or +N/-N to adjust)  '
                f'—  {ctx.player.return_key} to cancel'
            ],
        )
        if raw is None or not raw.strip():
            return None
        text = raw.strip()
        try:
            val = current + int(text) if text[0] in '+-' else int(text)
        except ValueError:
            await ctx.send('Please enter a number, or +N/-N to adjust.')
            continue
        if lo <= val <= hi:
            return val
        await ctx.send(f'Result must stay between {lo} and {hi}.')


# ---------------------------------------------------------------------------
# Hit-points menu
# ---------------------------------------------------------------------------

async def _edit_hit_points(ctx, name: str, get, set_) -> None:
    cur = int(get() or 0)
    await ctx.send(f'{name} current HP: {cur}')
    val = await _prompt_int(ctx, 'Hit Points', cur, 0, 999)
    if val is not None:
        set_(val)
        ctx.player.unsaved_changes = True
        await ctx.send(f'{name} hit points set to {val}.')


def _hp_menu(ctx) -> Menu:
    from bar.allies import owned_allies
    from bar.ally_data import AllyFlags

    p    = ctx.player
    menu = _titled_menu(ctx, 'Hit Points')

    def _get_player():
        return getattr(p, 'hit_points', 0)

    def _set_player(val):
        p.hit_points = val

    async def edit_player(ctx) -> None:
        await _edit_hit_points(ctx, p.name, _get_player, _set_player)

    def _regular_allies() -> list:
        # Excludes the MOUNT-flagged horse -- it has its own dedicated
        # Horse item below, so a horse-only party (no regular allies)
        # must still show all 3 Ally slots as empty rather than the
        # horse showing up under "Ally 1".
        return [a for a in owned_allies(p) if AllyFlags.MOUNT not in (a.flags or [])]

    def _ally_label(slot: int) -> str:
        allies = _regular_allies()
        if slot >= len(allies):
            return '(empty)'
        a = allies[slot]
        return f'{a.name}  HP {a.hit_points}'

    async def edit_ally(ctx, slot: int) -> None:
        allies = _regular_allies()
        if slot >= len(allies):
            await ctx.send('No ally in that slot.')
            return
        ally = allies[slot]

        def _get_ally():
            return ally.hit_points

        def _set_ally(val):
            ally.hit_points = val

        await _edit_hit_points(ctx, ally.name, _get_ally, _set_ally)

    def _horse() -> Optional[object]:
        return next((a for a in owned_allies(p) if AllyFlags.MOUNT in (a.flags or [])), None)

    def _horse_label(ctx) -> str:
        mount = _horse()
        return f'{mount.name}  HP {mount.hit_points}' if mount else '(no horse)'

    async def edit_horse(ctx) -> None:
        mount = _horse()
        if mount is None:
            await ctx.send('No horse owned.')
            return

        def _get_horse():
            return mount.hit_points

        def _set_horse(val):
            mount.hit_points = val

        await _edit_hit_points(ctx, mount.name, _get_horse, _set_horse)

    menu.add_item(MenuItem(
        'Player', shortcuts='p',
        dot_leader_handler=lambda ctx: str(_get_player()),
        action=edit_player,
    ))
    for i in range(3):
        menu.add_item(MenuItem(
            f'Ally {i + 1}', shortcuts="A" + str(i + 1),
            dot_leader_handler=lambda ctx, s=i: _ally_label(s),
            action=lambda ctx, s=i: edit_ally(ctx, s),
        ))
    menu.add_item(MenuItem('Horse', shortcuts='h', dot_leader_handler=_horse_label, action=edit_horse))
    return menu


# ---------------------------------------------------------------------------
# Money menu
# ---------------------------------------------------------------------------

def _money_menu(ctx) -> Menu:
    from base_classes import PlayerMoneyTypes
    p    = ctx.player
    menu = _titled_menu(ctx, 'Money')

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

    def _loan_status(ctx) -> str:
        amount = int(getattr(p, 'loan_amount', 0) or 0)
        if not amount:
            return 'None'
        days = int(getattr(p, 'loan_days', 0) or 0)
        return f'{amount:,}s, {days} day{"s" if days != 1 else ""} left'

    async def _edit_vinny_loan(ctx) -> None:
        # Vinny the Loan Shark debt tracking (bar/vinny.py, t_bar_vinney.lbl
        # / SPUR.BAR3.S) -- player.loan_amount (silver owed) and
        # player.loan_days (days left to repay).
        cur_amount = int(getattr(p, 'loan_amount', 0) or 0)
        await ctx.send(f'Current loan: {_loan_status(ctx)}')
        amount = await _prompt_int(ctx, 'Loan amount', cur_amount, 0, 9_999_999)
        if amount is None:
            return
        p.loan_amount = amount
        if amount == 0:
            p.loan_days = 0
            p.unsaved_changes = True
            await ctx.send('Loan cleared.')
            return
        cur_days = int(getattr(p, 'loan_days', 0) or 0)
        days = await _prompt_int(ctx, 'Days to repay', cur_days, 0, 999)
        if days is not None:
            p.loan_days = days
        p.unsaved_changes = True
        await ctx.send(f'Loan set to {_loan_status(ctx)}.')

    menu.add_item(MenuItem(
        'Vinny Loan',
        shortcuts='vl',
        dot_leader_handler=_loan_status,
        action=_edit_vinny_loan,
    ))
    return menu


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def _build_main_menu(ctx) -> Menu:
    menu = _titled_menu(ctx, f'Player Editor — {ctx.player.name}')
    menu.add_item(MenuItem('Alignment',        shortcuts='al', submenu=_alignment_menu(ctx)))
    menu.add_item(MenuItem('Armor/Shield',     shortcuts='as', submenu=_armor_shield_menu(ctx)))
    menu.add_item(MenuItem('Attributes',       shortcuts='at', submenu=_attributes_menu(ctx)))
    menu.add_item(MenuItem('Character Names',  shortcuts='cn', submenu=_names_menu(ctx)))
    menu.add_item(MenuItem('Combinations',     shortcuts='co', submenu=_combinations_menu(ctx)))
    menu.add_item(MenuItem('Command Settings', shortcuts='cs', submenu=_command_settings_menu(ctx)))
    menu.add_item(MenuItem('Flags/Counters',   shortcuts='fl', submenu=_flags_menu(ctx)))
    menu.add_item(MenuItem('Hit Points',       shortcuts='hp', submenu=_hp_menu(ctx)))
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
    # 2026-08-08: per-item durability redesign -- player.armor/
    # player.shield are now a *derived* mirror of the equipped item's own
    # .condition (see player.py's equipped_entry()/refresh_equipped_
    # rating()), not a free-standing number. So these two menu items edit
    # the equipped item's condition instead of setting the mirror directly
    # -- gated on something actually being equipped, same pattern as the
    # Shield Skill submenu below (which has always been keyed per physical
    # shield via active_shield_id, not a flat player stat).
    #
    # Still not wired in: the tep.lbl-style 5-worn-slot model (body armor,
    # shield, gauntlets, helmet, +1), armor_class, weight, and Size gating
    # so e.g. a Size.TINY Pixie can't wield a Size.HUGE shield -- see the
    # project_armor_shield_redesign memory / TODO.md for that still-open,
    # separate future pass. (The character_editor.py prototype this TODO
    # used to point at was deleted 2026-08-01, commit afd9557 -- gone, not
    # a live reference anymore.)
    p    = ctx.player
    menu = _titled_menu(ctx, 'Armor/Shield')

    def _display(slot: str) -> str:
        from player import equipped_entry
        entry = equipped_entry(p, slot)
        rating = int(getattr(p, slot, 0) or 0)
        if entry is None:
            return f'{rating}% (nothing equipped)'
        name = getattr(entry.item, 'name', '?')
        return f'{rating}% ({name})'

    def make_action(slot: str, label: str):
        async def action(ctx):
            from player import equipped_entry, refresh_equipped_rating
            entry = equipped_entry(p, slot)
            if entry is None:
                await ctx.send(f'No {label.lower()} equipped -- nothing to set a condition on.')
                return
            cur = int(getattr(entry.item, 'condition', 100) or 0)
            val = await _prompt_int(ctx, f'{label} condition', cur, 0, 100)
            if val is not None:
                entry.item.condition = val
                new_rating = refresh_equipped_rating(p, slot)
                p.unsaved_changes = True
                await ctx.send(f'{label} condition set to {val}% (rating: {new_rating}%).')
        return action

    menu.add_item(MenuItem(
        'Armor', shortcuts='ar',
        dot_leader_handler=lambda ctx: _display('armor'),
        action=make_action('armor', 'Armor'),
    ))
    menu.add_item(MenuItem(
        'Shield', shortcuts='sh',
        dot_leader_handler=lambda ctx: _display('shield'),
        action=make_action('shield', 'Shield'),
    ))

    def _shield_skill_display(ctx) -> str:
        active_shield_id = getattr(p, 'active_shield_id', None)
        if active_shield_id is None:
            return 'N/A (no shield)'
        prof_dict = getattr(p, 'shield_proficiency', {}) or {}
        return str(int(prof_dict.get(str(active_shield_id), 0)))

    async def _edit_shield_skill(ctx) -> None:
        # player.shield_proficiency (player.py:356), keyed by
        # active_shield_id, 0-99 -- fed into shield-block chance via
        # combat/resolution.py's shield_exp_bonus() / player.py's
        # gain_shield_proficiency(). Editing it requires an equipped,
        # identifiable shield (active_shield_id) since it's tracked
        # per physical shield, not as a flat player skill.
        active_shield_id = getattr(p, 'active_shield_id', None)
        if active_shield_id is None:
            await ctx.send('No shield equipped -- shield skill has nothing to attach to.')
            return
        prof_dict = getattr(p, 'shield_proficiency', None)
        if prof_dict is None:
            prof_dict = {}
            p.shield_proficiency = prof_dict
        key = str(active_shield_id)
        cur = int(prof_dict.get(key, 0))
        val = await _prompt_int(ctx, 'Shield Skill', cur, 0, 99)
        if val is not None:
            prof_dict[key] = val
            p.unsaved_changes = True
            await ctx.send(f'Shield skill set to {val}.')

    menu.add_item(MenuItem(
        'Shield Skill', shortcuts='ss',
        dot_leader_handler=_shield_skill_display,
        action=_edit_shield_skill,
    ))
    return menu


# ---------------------------------------------------------------------------
# Map Information menu
# ---------------------------------------------------------------------------

def _level_rooms(ctx, level: int) -> dict:
    """{room_number: Room} for *level*, or {} if no map data is loaded."""
    game_map = getattr(getattr(ctx, 'server', None), 'game_map', None)
    return game_map.levels.get(level, {}) if game_map else {}


def _room_label(ctx, level: int, room_no: int) -> str:
    """'42' if no room data is loaded for it, else '42 (Rolling Hills)'."""
    room = _level_rooms(ctx, level).get(room_no)
    return f'{room_no} ({room.name})' if room else str(room_no)


def _map_info_menu(ctx) -> Menu:
    p    = ctx.player
    menu = _titled_menu(ctx, 'Map Information')

    async def edit_level(ctx) -> None:
        cur = int(getattr(p, 'map_level', 1) or 1)
        val = await _prompt_int(ctx, 'Dungeon Level', cur, 1, 7)
        if val is not None:
            p.map_level = val
            p.unsaved_changes = True
            await ctx.send(f'Dungeon Level set to {val}.')

    async def edit_room(ctx) -> None:
        level = int(getattr(p, 'map_level', 1) or 1)
        cur   = int(getattr(p, 'map_room', 1) or 1)
        rooms = _level_rooms(ctx, level)

        while True:
            raw = await ctx.prompt(
                'Room Number',
                preamble_lines=[
                    f'Current: {_room_label(ctx, level, cur)}  —  '
                    f"{ctx.player.return_key} to cancel, '?' to list rooms on this level"
                ],
            )
            if raw is None or not raw.strip():
                return
            if raw.strip() == '?':
                if not rooms:
                    await ctx.send(f'No room data loaded for level {level}.')
                    continue
                await _send_labeled_list(
                    ctx, f'Level {level} Rooms',
                    sorted(rooms.values(), key=lambda r: r.number),
                    lambda r: f'#{r.number:<4} {r.name}',
                )
                continue
            try:
                val = int(raw.strip())
            except ValueError:
                await ctx.send("Please enter a number, or '?' to list.")
                continue
            if not (1 <= val <= 999):
                await ctx.send('Enter a number between 1 and 999.')
                continue
            p.map_room = val
            p.unsaved_changes = True
            from visited_rooms import mark_visited
            mark_visited(p, level, val)
            await ctx.send(f'Room Number set to {_room_label(ctx, level, val)}.')
            return

    menu.add_item(MenuItem(
        'Dungeon Level', shortcuts='dl',
        dot_leader_handler=lambda ctx: str(getattr(p, 'map_level', '?')),
        action=edit_level,
    ))
    menu.add_item(MenuItem(
        'Room Number', shortcuts='rn',
        dot_leader_handler=lambda ctx: _room_label(
            ctx, int(getattr(p, 'map_level', 1) or 1), int(getattr(p, 'map_room', 1) or 1)),
        action=edit_room,
    ))

    async def show_visited(ctx) -> None:
        cur = int(getattr(p, 'map_level', 1) or 1)
        level = await _prompt_int(ctx, 'Which Level', cur, 1, 7)
        if level is None:
            return
        from visited_rooms import visited_room_numbers
        seen = visited_room_numbers(p, level)
        if not seen:
            await ctx.send(f"{p.name} hasn't explored any of level {level} yet.")
            return
        from commands.map import render_overview
        game_map = getattr(getattr(ctx, 'server', None), 'game_map', None)
        lines = render_overview(ctx, game_map, level, p, allowed=seen) if game_map else None
        if lines is None:
            await ctx.send(f'No overview data for level {level}.')
            return
        await ctx.send([f'|yellow|{p.name} -- Level {level} rooms visited|reset|', ''] + lines)

    async def reset_visited(ctx) -> None:
        if not getattr(p, 'visited_rooms', None):
            await ctx.send(f'{p.name} has no visited-rooms data to reset.')
            return
        confirm = await ctx.prompt(
            'Confirm',
            preamble_lines=[f"Clear {p.name}'s visited-rooms history on all levels? (y/N)"])
        if not confirm or confirm.strip().lower() != 'y':
            await ctx.send('Cancelled.')
            return
        p.visited_rooms = {}
        p.unsaved_changes = True
        await ctx.send(f"{p.name}'s visited-rooms history has been reset.")

    menu.add_item(MenuItem(
        'Display Visited Rooms', shortcuts='vr',
        action=show_visited,
    ))
    menu.add_item(MenuItem(
        'Reset Visited Rooms', shortcuts='rv',
        action=reset_visited,
    ))
    return menu


# ---------------------------------------------------------------------------
# Command Settings menu — player.command_settings toggles
# ---------------------------------------------------------------------------

def _command_settings_menu(ctx) -> Menu:
    p    = ctx.player
    menu = _titled_menu(ctx, 'Command Settings')

    async def toggle_whereat_hidden(ctx) -> None:
        cs = p.command_settings
        cs.whereat_hidden = not cs.whereat_hidden
        p.unsaved_changes = True
        await ctx.send(f'Whereat Hidden: {"Yes" if cs.whereat_hidden else "No"}')

    menu.add_item(MenuItem(
        'Whereat Hidden', shortcuts='wh',
        dot_leader_handler=lambda ctx: 'Yes' if p.command_settings.whereat_hidden else 'No',
        action=toggle_whereat_hidden,
    ))

    async def toggle_news_show_all(ctx) -> None:
        news = p.command_settings.news
        news.show_all = not news.show_all
        p.unsaved_changes = True
        await ctx.send(f'News Show All: {"Yes" if news.show_all else "No"}')

    async def edit_news_last_read(ctx) -> None:
        import datetime as _datetime

        from date_cursor import INVALID, UNCHANGED, prompt_date_cursor

        news = p.command_settings.news
        current = None
        if news.last_read:
            try:
                current = _datetime.datetime.fromisoformat(news.last_read).date()
            except ValueError:
                current = None

        result = await prompt_date_cursor(
            ctx, p, current, label="news-read cursor",
            note=f"{p.name} will see news posted after this date again at their next login.",
        )
        if result is UNCHANGED or result is INVALID:
            return

        news.last_read = (
            _datetime.datetime.combine(result, _datetime.time.min).isoformat()
            if result else None
        )
        p.unsaved_changes = True

    menu.add_item(MenuItem(
        'News Show All', shortcuts='na',
        dot_leader_handler=lambda ctx: 'Yes' if p.command_settings.news.show_all else 'No',
        action=toggle_news_show_all,
    ))
    menu.add_item(MenuItem(
        'News Last Read', shortcuts='nr',
        dot_leader_handler=lambda ctx: (p.command_settings.news.last_read or '(never)')[:10],
        action=edit_news_last_read,
    ))
    return menu


# ---------------------------------------------------------------------------
# Weapons menu — readied weapon + per-weapon battle experience
# ---------------------------------------------------------------------------

def _weapons_menu(ctx) -> Menu:
    p    = ctx.player
    menu = _titled_menu(ctx, 'Weapons')

    def _readied_label() -> str:
        w = getattr(p, 'readied_weapon', None)
        return getattr(w, 'name', None) or '(none)'

    async def edit_readied_weapon(ctx) -> None:
        """Ready a weapon from inventory, or unready the current one.

        Delegates to the real ReadyCommand/UnreadyCommand (bare, no args)
        instead of reimplementing weapon selection here -- reuses their
        inventory scan/numbered picker and all of ready.py's special-case
        mechanics (STORM, Excalibur, Death Amulet, strength gate) rather
        than the previous action, which only ever cleared the readied
        weapon and never let an admin actually pick one from inventory.
        """
        from commands.ready import ReadyCommand
        from commands.unready import UnreadyCommand

        current = getattr(p, 'readied_weapon', None)
        if current is not None:
            raw = await ctx.prompt(
                preamble_lines=f"Currently readied: {getattr(current, 'name', '?')}.",
                prompt_text=f"[C]hange, [U]nready, or {ctx.player.return_key} to cancel"
            )
            if not raw or not raw.strip():
                return
            choice = raw.strip().lower()
            if choice.startswith('u'):
                await UnreadyCommand().execute(ctx)
                return
            if not choice.startswith('c'):
                await ctx.send('Unchanged.')
                return

        await ReadyCommand().execute(ctx)

    menu.add_item(MenuItem(
        'Readied Weapon', shortcuts='rw',
        dot_leader_handler=lambda ctx: _readied_label(),
        action=edit_readied_weapon,
    ))
    menu.add_item(MenuItem(
        'Battle Experience', shortcuts='be',
        submenu=_battle_experience_menu(ctx),
    ))
    return menu


def _battle_experience_menu(ctx) -> Menu:
    """One row per known weapon, dot-leader showing this player's current
    battle experience with it -- browse/pick instead of guessing a weapon
    name (the old edit_battle_exp() required typing a name/substring)."""
    p       = ctx.player
    weapons = getattr(getattr(ctx, 'server', None), 'weapons', None) or []
    menu    = _titled_menu(ctx, 'Battle Experience')

    def _exp() -> dict:
        exp = getattr(p, 'weapon_experience', None)
        if exp is None:
            exp = {}
            p.weapon_experience = exp
        return exp

    def make_action(key: str, label: str):
        async def action(ctx):
            cur = int(_exp().get(key, 0))
            val = await _prompt_battle_exp_value(ctx, label, cur)
            if val is not None:
                _exp()[key] = val
                p.unsaved_changes = True
                await ctx.send(f'Battle experience with {label} set to {val}.')
        return action

    for w in weapons:
        key   = str(w.get('number', 0))
        label = w.get('name', '?')
        menu.add_item(MenuItem(
            label,
            dot_leader_handler=lambda ctx, k=key: str(_exp().get(k, 0)),
            action=make_action(key, label),
        ))
    return menu


# ---------------------------------------------------------------------------
# Submenus
# ---------------------------------------------------------------------------

def _alignment_menu(ctx) -> Menu:
    from base_classes import Alignment
    p    = ctx.player
    menu = _titled_menu(ctx, 'Alignment')

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
    menu = _titled_menu(ctx, 'Attributes')

    # Per the BASIC: attributes 1-7 are capped at 18, Energy at 25.
    _range = {PlayerStat.EGY: (1, 25)}

    def _get(stat):
        # get_stat() returns None (with a logged warning) for a stat key
        # that isn't in p.stats yet -- true for Charisma on most existing
        # characters, since it was only added to the roll in _STAT_ORDER
        # after they were created. Fall back to 0 so the menu shows a real
        # number instead of "None".
        if hasattr(p, 'get_stat'):
            val = p.get_stat(stat)
            return val if val is not None else 0
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


def _scan_party_ally_owners(ctx) -> dict:
    """Return {ally_name: owning_player_name} for every ally actually
    sitting in *any* player's party right now -- online (the live
    Player.party in memory) or offline (the 'party' list saved in that
    player's own player-*.json) -- independent of what bar/ally_data.py's
    ally-roster.json claims.

    ally-roster.json is only as fresh as its last save_ally_roster() call
    (bar/fat_olaf.py's buy/sell/maintain, this module's add/remove); a
    crash between Party.add()/Party.remove() and that save, or a manual
    edit, would leave it out of sync with each player's own save file --
    the real source of truth for "who has this ally right now." Ryan
    asked for this cross-check before [a]dding an ally so the roster
    saying FREE can't hand out one some player's save file still holds.
    """
    import glob
    import json as _json
    import net_common
    from pathlib import Path
    from bar.ally_data import Ally as _Ally

    owners: dict = {}
    online_names = set()

    for client in getattr(ctx.server, 'clients', {}).values():
        other_ctx    = getattr(client, 'ctx', None)
        other_player = getattr(other_ctx, 'player', None)
        if other_player is None:
            continue
        online_names.add(other_player.name)
        for m in getattr(other_player, 'party', None) or []:
            if isinstance(m, _Ally):
                owners[m.name] = other_player.name

    base = Path(net_common.run_server_dir or 'run/server')
    for path in glob.glob(str(base / 'player-*.json')):
        try:
            with open(path) as fh:
                data = _json.load(fh)
        except (OSError, _json.JSONDecodeError):
            log.exception('_scan_party_ally_owners: failed to read %s', path)
            continue
        owner_name = data.get('name') or Path(path).stem[len('player-'):]
        if owner_name in online_names:
            continue  # live in-memory party is authoritative for this player
        for entry in data.get('party') or []:
            if isinstance(entry, dict) and entry.get('type') == 'ally' and entry.get('name'):
                owners.setdefault(entry['name'], owner_name)

    return owners


def _sync_roster_status(master_list, name: str, status, owner,
                         strength: Optional[int] = None) -> None:
    """Update the ally named *name* in master_list to reflect *status*/*owner*.

    Needed whenever the Ally object actually being mutated (e.g. one pulled
    from owned_allies(), a different Python instance than load_allies()'s
    freshly-built master list) needs that change reflected in the roster
    before save_ally_roster() persists it. Mirrors bar/fat_olaf.py's own
    _sync_to_roster().
    """
    for a in master_list:
        if a.name == name:
            a.status = status
            a.owner  = owner
            if strength is not None:
                a.strength = strength
            break


def _status_label(a) -> str:
    """Human-readable status for ally '?' listings.

    A bare enum name ("SERVANT"/"FREE") doesn't answer "owned by whom" or
    "available from where" -- Ryan asked for "Servant of <player>" and
    "At Olaf's" (where FREE allies are actually hired from) instead, plus
    Unconscious/Dead surfaced since an owned ally can carry either status
    mid-combat while still sitting in its owner's party (see
    combat/engine.py, ally_events/*.py).
    """
    from bar.ally_data import AllyStatus
    if a.status == AllyStatus.DEAD:
        return 'Dead'
    if a.status == AllyStatus.UNCONSCIOUS:
        return 'Unconscious'
    if a.status == AllyStatus.SERVANT:
        return f'Servant of {a.owner}' if a.owner else 'Servant'
    if a.status == AllyStatus.FREE:
        return "At Olaf's"
    return a.status.name.title()


async def _exclude_held_by_others(ctx, candidates: list) -> list:
    """Drop any *candidates* that _scan_party_ally_owners() finds actually
    held by another player despite the roster calling them FREE, warning
    the admin and logging specifics. Shared by [a]dd and swap-in-slot,
    both of which offer FREE allies pulled straight from the roster.
    """
    held = _scan_party_ally_owners(ctx)
    desynced = [a for a in candidates if a.name in held]
    kept     = [a for a in candidates if a.name not in held]
    if desynced:
        log.warning(
            'Ally roster desync: %s',
            ', '.join(f'{a.name} (roster: FREE, actually held by {held[a.name]})'
                      for a in desynced),
        )
        await ctx.send(
            f'Note: excluded {len(desynced)} ally(ies) whose roster status is '
            f'stale (still held by another player) -- see server log.'
        )
    return kept


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
    menu = _titled_menu(ctx, 'Character Names')

    async def edit_name(ctx) -> None:
        raw = await ctx.prompt(
            'Player Name',
            preamble_lines=[f'Current: {p.name}', 'Blank to cancel:'],
        )
        if not raw or not raw.strip():
            await ctx.send('Name unchanged.')
            return
        p.name = raw.strip()
        p.unsaved_changes = True
        await ctx.send(f'Name changed to: {p.name}')

    def _regular_allies() -> list:
        # Excludes the MOUNT-flagged horse -- it has its own dedicated
        # Horse item below, so a horse-only party (no regular allies)
        # must still show all 3 Ally slots as empty rather than the
        # horse showing up under "Ally 1".
        return [a for a in owned_allies(p) if AllyFlags.MOUNT not in (a.flags or [])]

    def _ally_label(slot: int) -> str:
        allies = _regular_allies()
        if slot >= len(allies):
            return '(empty)'
        a = allies[slot]
        tag = f' [{a.status.name}]' if a.status in (AllyStatus.UNCONSCIOUS, AllyStatus.DEAD) else ''
        return f'{a.name}  Str {a.strength}{tag}'

    async def _add_ally(ctx) -> None:
        """Empty-slot flow: offer to add an ally, reusing bar/fat_olaf.py's
        numbered picker (bar.allies.pick_ally) rather than its purchase UI --
        this is an admin assignment, not a paid hire, so no silver charge and
        none of _buy_servant()'s hire bonuses (+5 strength, etc).

        Marks the chosen ally AllyStatus.SERVANT. This codebase has no
        separate "in party" status -- SERVANT already means "owned/hired by
        a player" (see bar/ally_data.py's AllyStatus docstring); actual
        party membership is tracked independently via Party.members, set
        below via player.party.add().
        """
        raw = await ctx.prompt(
            'Add ally',
            preamble_lines=['No ally in that slot. Add one? (Y/N, or ? to list available allies)'],
        )
        if raw and raw.strip() == '?':
            pass  # fall through into pick_ally(), which lists then prompts
        elif not raw or raw.strip().upper() != 'Y':
            return

        from bar.ally_data import load_allies, save_ally_roster
        from bar.allies import filter_allies, pick_ally

        master_list = load_allies()
        owned_names = {a.name for a in _regular_allies()}
        available = [a for a in filter_allies(master_list, AllyStatus.FREE)
                     if a.name not in owned_names]
        if not available:
            await ctx.send('No allies available to add.')
            return

        chosen = await pick_ally(ctx, available, prompt='Add which ally')
        if chosen is None:
            return

        chosen.status = AllyStatus.SERVANT
        chosen.owner  = p.name
        # Allies are created with hit_points=0 (bar/ally_data.py) and nothing
        # else initializes it, which leaves them unable to fight or take
        # damage (combat/engine.py gates ally participation on hit_points >
        # 0) -- seed it here the same way fat_olaf._buy_servant() does,
        # unless it's already set (e.g. re-adding a previously-fielded ally).
        if not chosen.hit_points:
            chosen.hit_points = chosen.strength * 2
        save_ally_roster(master_list)
        await p.party.add(ctx, p, chosen)
        p.unsaved_changes = True

    async def _swap_ally(ctx, slot: int) -> None:
        """[S]wap: replace the ally in *slot* with a different one from
        the master roster, reusing the same FREE-filter/roster-desync
        cross-check as [a]dd (_exclude_held_by_others()) so a swap can't
        hand out an ally another player actually still holds.
        """
        from bar.ally_data import load_allies, save_ally_roster
        from bar.allies import filter_allies

        allies = _regular_allies()
        old    = allies[slot]

        master_list = load_allies()
        owned_names = {a.name for a in allies}
        candidates  = [a for a in filter_allies(master_list, AllyStatus.FREE)
                       if a.name not in owned_names]
        candidates  = await _exclude_held_by_others(ctx, candidates)
        if not candidates:
            await ctx.send('No allies available to swap in.')
            return

        preamble = (
            'Enter a name (or part of a name), [?] to list, or '
            f'{ctx.player.return_key} to cancel.'
        )
        while True:
            raw = await ctx.prompt(f'Swap {old.name} for', preamble_lines=[preamble])
            if raw and raw.strip() == '?':
                await _send_labeled_list(ctx, 'Available allies', candidates, _roster_label)
                continue
            break
        if not raw or not raw.strip():
            return

        term    = raw.strip().lower()
        matches = [a for a in candidates if term in a.name.lower()]
        if not matches:
            await ctx.send(f'No available allies matching "{raw.strip()}".')
            return

        new_ally = await _pick_from_matches(ctx, matches, _roster_label)
        if new_ally is None:
            return

        _sync_roster_status(master_list, old.name, AllyStatus.FREE, None, old.strength)
        old.status = AllyStatus.FREE
        old.owner  = None

        new_ally.status = AllyStatus.SERVANT
        new_ally.owner  = p.name
        if not new_ally.hit_points:
            new_ally.hit_points = new_ally.strength * 2
        save_ally_roster(master_list)

        # Replace in place rather than remove()+add() -- Party.members is a
        # flat list with no real slot concept (see edit_ally()'s comment
        # below), so remove-then-append would push the new ally to the end
        # instead of leaving it in the slot the admin actually picked.
        # *slot* indexes _regular_allies() (the MOUNT is excluded from that
        # numbering), which isn't necessarily *old*'s position in the raw
        # party.members list if a horse sits before it there -- look up
        # the real index rather than assuming they match.
        p.party.members[p.party.members.index(old)] = new_ally
        p.unsaved_changes = True
        await ctx.send(f'{old.name} is replaced by {new_ally.name}.')

    async def edit_ally(ctx, slot: int) -> None:
        allies = _regular_allies()
        if slot >= len(allies):
            # Only the first empty slot offers to add -- allies are a flat
            # list (bar/allies.py's owned_allies(), not real numbered
            # slots), so a new one always lands at index len(allies)
            # regardless of which higher slot number was clicked.
            if slot == len(allies):
                await _add_ally(ctx)
            else:
                await ctx.send('No ally in that slot.')
            return

        ally = allies[slot]
        raw = await ctx.prompt(
            ally.name,
            preamble_lines=[
                f'Current: {ally.name}  Str {ally.strength}  {ally.to_hit * 10}%',
                f"[N]ew name, [S]wap for a different ally, or "
                f"{ctx.player.return_key} to cancel:",
            ],
        )
        choice = (raw or '').strip().lower()
        if not choice:
            await ctx.send('Unchanged.')
        elif choice == 'n':
            await _rename_ally(ctx, ally)
        elif choice == 's':
            await _swap_ally(ctx, slot)
        else:
            await ctx.send("Please choose 'N' or 'S'.")

    def _horse() -> Optional[object]:
        return next((a for a in owned_allies(p) if AllyFlags.MOUNT in (a.flags or [])), None)

    def _horse_label(ctx) -> str:
        mount = _horse()
        if mount is None:
            return '(none)'
        flavor = ' '.join(str(x) for x in (
            getattr(mount, 'color', None), getattr(mount, 'breed', None),
        ) if x)
        label = f'{mount.name}{f" ({flavor})" if flavor else ""}  Str {mount.strength}'
        if mount.status == AllyStatus.BOLTED:
            label += f'  [BOLTED -- Level {mount.bolt_map_level} Room {mount.bolt_room_no}]'
        return label

    async def _add_horse(ctx) -> None:
        """[A] Add Horse: no master roster to pick from -- horses aren't
        part of bar/ally_data.py's ~90-name servant list -- so this rolls
        gender/breed/colour and prompts for a name exactly like a real
        LASSO capture (ally_events/capture_horse.py's capture_mount()):
        same "Your horse seems to be..." announcement and the same
        prompt_horse_name() (typed name, 'R' for random, Enter to cancel).
        """
        import random
        from ally_events.capture_horse import prompt_horse_name
        from bar.ally_data import Ally
        from base_classes import HorseBreed, HorseColor
        from flags import PlayerFlags

        gender      = random.choice(('m', 'f'))
        breed       = random.choice(list(HorseBreed))
        color       = random.choice(list(HorseColor))
        gender_word = 'male' if gender == 'm' else 'female'
        await ctx.send(f'Your horse seems to be a {gender_word} {color} {breed}!')

        name = await prompt_horse_name(ctx, gender)
        if name is None:
            return

        mount = Ally(name=name, gender=gender, strength=20, to_hit=0, flags=[AllyFlags.MOUNT])
        mount.breed       = breed
        mount.color       = color
        mount.status      = AllyStatus.SERVANT
        mount.owner       = p.name
        mount.hit_points  = mount.strength * 2

        await p.party.add(ctx, p, mount)
        p.set_flag(PlayerFlags.HAS_HORSE)
        p.unsaved_changes = True

    async def _remove_horse(ctx) -> None:
        """[R] Remove Horse: releases the mount from the party and clears
        both horse PlayerFlags so they can't go stale -- MOUNTED
        especially, since commands/mount.py/dismount.py only ever *set*
        it, never check "do you still have a horse" before leaving a
        player flagged as riding one that no longer exists.
        """
        from flags import PlayerFlags

        mount = _horse()
        if mount is None:
            await ctx.send('No horse owned.')
            return

        lines = []
        if p.query_flag(PlayerFlags.MOUNTED):
            lines.append(f'You were riding {mount.name} -- dismounting.')
            p.clear_flag(PlayerFlags.MOUNTED)
        p.party.remove(mount)
        mount.status = AllyStatus.FREE
        mount.owner  = None
        p.clear_flag(PlayerFlags.HAS_HORSE)
        lines.append(f'{mount.name} is released and removed from your party.')
        lines.append('(Has Horse and Mounted flags cleared.)')
        p.unsaved_changes = True
        await ctx.send(lines)

    async def _recall_horse(ctx) -> None:
        """[C] Recall Horse: support-desk fix for a mount stuck BOLTED
        (ally_events/horse_bolt.py) -- e.g. the player's search room got
        deleted/relocated out from under them, or an admin just wants to
        test/undo it. Snaps status straight back to SERVANT, same as
        MOUNT's own catch-in-that-room path (try_catch_bolted_mount) but
        without requiring the player to actually be standing there.
        """
        mount = _horse()
        if mount is None or mount.status != AllyStatus.BOLTED:
            await ctx.send('No bolted horse to recall.')
            return
        mount.status         = AllyStatus.SERVANT
        mount.bolt_room_no   = None
        mount.bolt_map_level = None
        p.unsaved_changes = True
        await ctx.send(f'{mount.name} is recalled and rejoins the party.')

    async def edit_horse(ctx) -> None:
        mount = _horse()
        if mount is None:
            raw = await ctx.prompt(
                'Add a horse',
                preamble_lines=[f'No horse owned. [A]dd a horse, or {ctx.player.return_key} to cancel:'],
            )
            choice = (raw or '').strip().lower()
            if choice == 'a':
                await _add_horse(ctx)
            elif choice:
                await ctx.send("Please choose 'A'.")
            return

        bolted = mount.status == AllyStatus.BOLTED
        options = "[N]ew name, [R]emove horse" + (", [C] recall bolted horse" if bolted else "")
        current_line = f'Current: {mount.name}  Str {mount.strength}'
        if bolted:
            current_line += f'  [BOLTED -- Level {mount.bolt_map_level} Room {mount.bolt_room_no}]'
        raw = await ctx.prompt(
            mount.name,
            preamble_lines=[
                current_line,
                f"{options}, or {ctx.player.return_key} to cancel:",
            ],
        )
        choice = (raw or '').strip().lower()
        if not choice:
            await ctx.send('Unchanged.')
        elif choice == 'n':
            await _rename_ally(ctx, mount)
        elif choice == 'r':
            await _remove_horse(ctx)
        elif choice == 'c' and bolted:
            await _recall_horse(ctx)
        else:
            expected = 'N, R, or C' if bolted else "'N' or 'R'"
            await ctx.send(f"Please choose {expected}.")

    def _roster_label(a) -> str:
        return f'{a.name:<22}  Str {a.strength:>2}  {a.to_hit * 10:>3}%  [{_status_label(a)}]'

    async def _list_owned_allies(ctx) -> None:
        allies = owned_allies(p)
        if not allies:
            await ctx.send('No allies owned.')
            return
        await _send_labeled_list(ctx, 'Owned allies', allies, _roster_label)

    async def _add_ally_by_name(ctx) -> None:
        """[a] Add Ally: name-search variant of the empty-slot _add_ally()
        flow above -- same SERVANT assignment/hit_points seeding/roster
        persistence, but reachable without hunting for an empty A1-A3 slot
        and with partial-name matching/'?' listing (see _give_ration()'s
        established pattern) instead of pick_ally()'s numbered-only prompt.
        """
        # This path is reachable directly from the top-level [a] menu item,
        # unlike _add_ally() above which can only ever fire from an empty
        # A1-A3 slot and is therefore structurally capped at 3 -- without
        # this check here, a player already holding 3 allies could still
        # be handed a 4th, breaking the 3-ally cap enforced everywhere else
        # (see ally_events/capture_horse.py's mount_slot_available()).
        if len(_regular_allies()) >= 3:
            await ctx.send('Already has 3 allies -- remove one first.')
            return

        from bar.ally_data import load_allies, save_ally_roster
        from bar.allies import filter_allies

        master_list = load_allies()
        owned_names = {a.name for a in _regular_allies()}
        available = [a for a in filter_allies(master_list, AllyStatus.FREE)
                     if a.name not in owned_names]

        # Cross-check against every player's actual party (online or save
        # file), not just the roster's status field -- see
        # _exclude_held_by_others()/_scan_party_ally_owners() for why the
        # roster alone can't be trusted.
        available = await _exclude_held_by_others(ctx, available)

        if not available:
            await ctx.send('No allies available to add.')
            return

        while True:
            raw = await ctx.prompt(
                'Ally name',
                preamble_lines=[f"Ally name to add (or part of name, '?' to list all, {ctx.player.return_key} to cancel)"],
            )
            if raw and raw.strip() == '?':
                await _send_labeled_list(ctx, 'Available allies', available, _roster_label)
                continue
            break
        if not raw or not raw.strip():
            return

        term    = raw.strip().lower()
        matches = [a for a in available if term in a.name.lower()]
        if not matches:
            await ctx.send(f'No available allies matching "{raw.strip()}".')
            return

        chosen = await _pick_from_matches(ctx, matches, _roster_label)
        if chosen is None:
            return

        chosen.status = AllyStatus.SERVANT
        chosen.owner  = p.name
        if not chosen.hit_points:
            chosen.hit_points = chosen.strength * 2
        save_ally_roster(master_list)
        await p.party.add(ctx, p, chosen)
        p.unsaved_changes = True

    async def _remove_ally_by_name(ctx) -> None:
        """[r] Remove Ally: reverts the chosen owned ally to AllyStatus.FREE
        (same desertion semantics as bar/fat_olaf.py's _sell_servant(), minus
        the silver refund/honour penalty -- this is an admin edit, not a
        sale) and drops them from the player's party.

        Accepts a slot number (1-3) or 'h' for horse -- the same slots as
        the Ally 1-3/Horse items above -- as an alternative to name search.
        This is the escape hatch for an ally literally *named* "?" (a real
        bug that renamed one that way): typing "?" always means "[?] list"
        here, so a "?"-named ally can never be reached by name search, only
        by its slot number.
        """
        from bar.ally_data import load_allies, save_ally_roster

        allies_all = owned_allies(p)
        if not allies_all:
            await ctx.send('No allies owned.')
            return
        # Slot numbers 1-3 index the non-horse allies specifically -- 'h'
        # is the separate path to the horse -- same split as _regular_allies()
        # above, needed so a horse-only party doesn't put the horse under "1".
        allies = _regular_allies()

        preamble = (
            'Enter a name (or part of a name), ally number (1-3, h for '
            f'horse), [?] to list, or {ctx.player.return_key} to abort.'
        )

        while True:
            raw = await ctx.prompt('Remove which ally', preamble_lines=[preamble])
            if raw and raw.strip() == '?':
                await _send_labeled_list(ctx, 'Owned allies', allies_all, _roster_label)
                continue
            break
        if not raw or not raw.strip():
            return

        term = raw.strip()

        if term.lower() == 'h':
            chosen = next((a for a in allies_all if AllyFlags.MOUNT in (a.flags or [])), None)
            if chosen is None:
                await ctx.send('No horse owned.')
                return
        elif term.isdigit() and 1 <= int(term) <= 3:
            slot = int(term) - 1
            if slot >= len(allies):
                await ctx.send('No ally in that slot.')
                return
            chosen = allies[slot]
        else:
            matches = [a for a in allies_all if term.lower() in a.name.lower()]
            if not matches:
                await ctx.send(f'No owned allies matching "{term}".')
                return
            chosen = await _pick_from_matches(ctx, matches, _roster_label)
            if chosen is None:
                return

        p.party.remove(chosen)
        chosen.status = AllyStatus.FREE
        chosen.owner  = None

        # chosen comes from owned_allies(p) (the player's live party), a
        # different Ally instance than load_allies()'s freshly-built master
        # list -- resync the matching master-list entry before persisting.
        master_list = load_allies()
        _sync_roster_status(master_list, chosen.name, AllyStatus.FREE, None, chosen.strength)
        save_ally_roster(master_list)
        p.unsaved_changes = True
        await ctx.send(f'{chosen.name} removed from party.')

    menu.add_item(MenuItem(
        'Player Name', shortcuts='p',
        dot_leader_handler=lambda ctx: p.name,
        action=edit_name,
    ))
    for i in range(3):
        menu.add_item(MenuItem(
            f'Ally {i + 1}', shortcuts="A" + str(i + 1),
            dot_leader_handler=lambda ctx, s=i: _ally_label(s),
            action=lambda ctx, s=i: edit_ally(ctx, s),
        ))
    menu.add_item(MenuItem('Horse', shortcuts='h', dot_leader_handler=_horse_label, action=edit_horse))
    menu.add_item(MenuItem('List Allies',   shortcuts='?', action=_list_owned_allies))
    menu.add_item(MenuItem('Add Ally',      shortcuts='a', action=_add_ally_by_name))
    menu.add_item(MenuItem('Remove Ally',   shortcuts='r', action=_remove_ally_by_name))
    return menu


def _combinations_menu(ctx) -> Menu:
    from base_classes import Combination, CombinationTypes
    p    = ctx.player
    menu = _titled_menu(ctx, 'Combinations')

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
                'Enter three numbers like 04-05-09, R to randomize, X to '
                f'clear, or {ctx.player.return_key} to cancel:',
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
        if raw.strip().lower() == 'r':
            # Combination.__init__() already rolls a random 1-99 triple --
            # reuse that instead of duplicating the random.randrange() call.
            if not hasattr(p, 'combinations') or not isinstance(p.combinations, dict):
                p.combinations = {}
            combo = Combination(combo_type)
            p.combinations[combo_type] = combo
            p.combinations[combo_type.value] = combo
            p.combinations[combo_type.name]  = combo
            await ctx.send(f'{combo_type.value} randomized to {_fmt(combo_type)}.')
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


def _survival_counter_items(p) -> list[MenuItem]:
    """Food/Drink editors -- survival.py's actual 0-config.survival_max
    hunger/thirst counters that drive EAT/DRINK and survival_tick()'s
    starvation check, distinct from PlayerFlags.HUNGER/THIRST below
    (those are just the boolean "currently hungry/thirsty" display
    flags SPUR also had, not the counters themselves). New in TADA --
    the "Flags/Counters" menu previously had no counters at all despite
    its own name. Ryan's request. Upper bound reads config.survival_max
    (also Ryan's call) rather than a hardcoded 20, so this stays correct
    if a sysop raises/lowers that setting."""
    from config import config

    def make_action(attr: str, label: str):
        async def action(ctx):
            max_value = config.survival_max
            cur = int(getattr(p, attr, max_value) or 0)
            val = await _prompt_int(ctx, label, cur, 0, max_value)
            if val is not None:
                setattr(p, attr, val)
                p.unsaved_changes = True
                await ctx.send(f'{label} set to {val}.')
        return action

    return [
        MenuItem(
            'Food (Hunger)', shortcuts='fo',
            dot_leader_handler=lambda ctx: str(int(getattr(p, 'food', config.survival_max) or 0)),
            action=make_action('food', 'Food'),
        ),
        MenuItem(
            'Drink (Thirst)', shortcuts='dr',
            dot_leader_handler=lambda ctx: str(int(getattr(p, 'drink', config.survival_max) or 0)),
            action=make_action('drink', 'Drink'),
        ),
    ]


def _flags_menu(ctx) -> Menu:
    p    = ctx.player
    menu = _titled_menu(ctx, 'Flags/Counters')

    # Groups mirror the BASIC's two-page layout (lines {:3010} and {:3115}).
    _groups = [
        ('Option Toggles', [
            PlayerFlags.EXPERT_MODE,
            PlayerFlags.HOURGLASS,
            PlayerFlags.MORE_PROMPT,
            PlayerFlags.ROOM_DESCRIPTIONS,
            PlayerFlags.DEBUG_MODE,
            PlayerFlags.PROMPT_MODE,
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

    # Appended after the flag groups (not before) so existing item
    # positions/shortcuts for the flags above stay stable for anyone
    # used to navigating this menu by number.
    menu.add_item(MenuItem(text='— Survival Counters —'))
    for item in _survival_counter_items(p):
        menu.add_item(item)

    return menu


def _statistics_menu(ctx) -> Menu:
    p    = ctx.player
    menu = _titled_menu(ctx, 'Statistics')

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
        from tada_utilities import class_display_name
        options  = list(PlayerClass)
        preamble = [f'Current: {player_class_display_name(p)}'] + [
            f'{i+1}: {class_display_name(c, getattr(p, "gender", None))}' for i, c in enumerate(options)
        ]
        raw = await ctx.prompt('Class', preamble_lines=preamble)
        if not raw or not raw.strip().isdigit():
            await ctx.send('Class unchanged.')
            return
        idx = int(raw.strip()) - 1
        if 0 <= idx < len(options):
            p.char_class = options[idx]
            p.unsaved_changes = True
            await ctx.send(f'Class set to {player_class_display_name(p)}.')
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

    async def edit_honor(ctx) -> None:
        # player.honor (player.py:285, default 1_000) -- drives the
        # *current* alignment label shown on the stats screen (commands/
        # stats.py's _current_alignment(), SPUR.MISC5.S lines 199-201) and
        # is spent/earned by bar/fat_olaf.py and ally_events/starvation.py.
        # Doesn't touch player.natural_alignment (race-derived) or the
        # separately-stored player.current_alignment field edited under
        # Alignment above. Bound is SPUR.ANNEX.S:301's real sysop-editor
        # check ("if (vk>2000) or (vk<1) print 'Invalid input'") -- vk is
        # also capped below 2000 by every in-game honor gain (e.g.
        # SPUR.GUILD.S, SPUR.MISC6.S:200, SPUR.MAIN.S:202). tep.lbl's own
        # "h=2^16" bound for this field was wrong; don't trust it here.
        from commands.stats import _current_alignment
        cur = int(getattr(p, 'honor', 0) or 0)
        val = await _prompt_int(ctx, 'Honor', cur, 1, 2_000)
        if val is not None:
            p.honor = val
            p.unsaved_changes = True
            await ctx.send(f'Honor set to {val} ({_current_alignment(val)}).')

    async def toggle_gender(ctx) -> None:
        from base_classes import Gender
        p.gender = Gender.FEMALE if p.gender == Gender.MALE else Gender.MALE
        p.unsaved_changes = True
        await ctx.send(f'Gender set to {p.gender.value}.')

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
        from characters import birthday_for_age, parse_month
        cur = getattr(p, 'birthday', None)
        cur_str = cur.strftime('%B %d, %Y') if cur else '(not set)'
        raw = await ctx.prompt(
            'Birthday (MM-DD)',
            preamble_lines=[
                f'Current: {cur_str}',
                f"Birth year is derived from age ({getattr(p, 'age', 0) or 0}); enter month/day only.",
                "For the month, type the number or at least the first "
                "three letters of the month name (e.g. 09-16 or Sep-16).",
                'Blank to cancel:',
            ],
        )
        if not raw or not raw.strip():
            await ctx.send('Birthday unchanged.')
            return
        parts = raw.strip().split('-')
        try:
            month = parse_month(parts[0])
            day   = int(parts[1])
            if month is None:
                raise ValueError
            # Validate against a leap year so Feb 29 is always accepted here;
            # birthday_for_age() falls back to Feb 28 if the derived year
            # (from age) isn't itself a leap year.
            max_day = calendar.monthrange(2000, month)[1]
            if not (1 <= day <= max_day):
                raise ValueError
        except (ValueError, IndexError):
            await ctx.send('Invalid date — expected MM-DD (or Month-DD).')
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

    async def edit_duel_wins(ctx) -> None:
        cur = int(getattr(p, 'duel_wins', 0) or 0)
        val = await _prompt_int(ctx, 'Duel Wins', cur, 0, 999_999)
        if val is not None:
            p.duel_wins = val
            p.unsaved_changes = True
            await ctx.send(f'Duel wins set to {val}.')

    async def edit_duel_losses(ctx) -> None:
        cur = int(getattr(p, 'duel_losses', 0) or 0)
        val = await _prompt_int(ctx, 'Duel Losses', cur, 0, 999_999)
        if val is not None:
            p.duel_losses = val
            p.unsaved_changes = True
            await ctx.send(f'Duel losses set to {val}.')

    async def edit_defeated_by(ctx) -> None:
        # Pairs with PlayerFlags.UNCONSCIOUS (Flags/Counters menu) -- set
        # together by combat/duel.py's DuelSession._end() on a duel loss,
        # cleared together by logon_events/unconscious_wake.py at the
        # player's next login. Free text since it just names whoever most
        # recently knocked them out, not a cross-reference to a live
        # Player object.
        cur = getattr(p, 'defeated_by', None)
        raw = await ctx.prompt(
            'Defeated by',
            preamble_lines=[
                f'Current: {cur or "(not set)"}',
                f"Type 'clear' to unset, {ctx.player.return_key} to cancel:",
            ],
        )
        if not raw or not raw.strip():
            await ctx.send('Defeated by unchanged.')
            return
        if raw.strip().lower() == 'clear':
            p.defeated_by = None
            p.unsaved_changes = True
            await ctx.send('Defeated by cleared.')
            return
        p.defeated_by = raw.strip()
        p.unsaved_changes = True
        await ctx.send(f'Defeated by set to {p.defeated_by}.')

    async def edit_monsters_killed(ctx) -> None:
        monsters = getattr(ctx.server, 'monsters', []) or []
        killed = getattr(p, 'dead_monsters', None)
        if killed is None:
            killed = []
            p.dead_monsters = killed

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

            raw = await ctx.prompt('Command', preamble_lines=['[A]dd  [R]emove  [Q]uit'])
            if not raw or not raw.strip():
                break
            cmd = raw.strip().lower()[:1]

            if cmd == 'q':
                break
            elif cmd == 'a':
                term_raw = await ctx.prompt('Monster name', preamble_lines=['Monster name (or part of name)'])
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
                idx_raw = await ctx.prompt('#', preamble_lines=[f'Remove which (1-{len(killed)})'])
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
        dot_leader_handler=lambda ctx: player_class_display_name(p),
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
        'Honor', shortcuts='ho',
        dot_leader_handler=lambda ctx: str(getattr(p, 'honor', '?')),
        action=edit_honor,
    ))
    menu.add_item(MenuItem(
        'Gender', shortcuts='ge',
        dot_leader_handler=lambda ctx: str(getattr(p, 'gender', '?')),
        action=toggle_gender,
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
        dot_leader_handler=lambda ctx: str(len(getattr(p, 'dead_monsters', []) or [])),
        action=edit_monsters_killed,
    ))
    menu.add_item(MenuItem(
        'Duel wins', shortcuts='dw',
        dot_leader_handler=lambda ctx: str(getattr(p, 'duel_wins', '?')),
        action=edit_duel_wins,
    ))
    menu.add_item(MenuItem(
        'Duel losses', shortcuts='dl',
        dot_leader_handler=lambda ctx: str(getattr(p, 'duel_losses', '?')),
        action=edit_duel_losses,
    ))
    menu.add_item(MenuItem(
        'Defeated by', shortcuts='db',
        dot_leader_handler=lambda ctx: str(getattr(p, 'defeated_by', None) or '(not set)'),
        action=edit_defeated_by,
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

    raw = await ctx.prompt('Choice', preamble_lines=[f'Choose 1-{len(matches)}, or {ctx.player.return_key} to cancel'])
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
                    '[T]ransfer  [D]rop  [L]ist weapons  [I]nventory  [Q]uit',
                    '(Weapon/Object/Book/Ration/Transfer will ask who receives it -- you,',
                    ' an ally, the mount, or another character by name; Drop deletes it)',
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
                # 'misc' covers quest/utility items objects.json has no
                # more specific type for (communicator, tool kit,
                # spacesuit, Palantir, Amulet of Life, Crown of Midas,
                # ruby slippers, keys, etc.) -- omitted here until Ryan
                # found "broken communicator" unreachable via [O]bject
                # search, which is what this type is actually for.
                _OBJ_TYPES = {'treasure', 'compass', 'container', 'ammunition',
                              'power', 'cursed', 'misc'}
                await _give_object(ctx, _OBJ_TYPES, 'object')
            elif cmd == 's':
                await ctx.send('Spell giving not ready yet.')
            elif cmd == 't':
                await _transfer_item(ctx)
            elif cmd == 'd':
                await _drop_item(ctx)
            else:
                await ctx.send('Unknown option.')

    return action


async def _show_inventory(ctx) -> None:
    """Display the player's current inventory, numbered so 'r<#>' can
    read a book straight out of this list (see _inventory_action()) --
    plus each owned ally's pack underneath (New in TADA, Ryan's request:
    EditPlayer's inventory menu previously had no idea allies/the mount
    could carry anything at all, now that they can -- see
    _pick_recipient()/_deliver_item()). Ally items are NOT part of the
    'r<#>' numbering -- that stays keyed to the player's own inventory
    only, reusing commands/inv.py's _ally_inventory_lines() for the
    ally section rather than duplicating its formatting."""
    inv = getattr(ctx.player, 'inventory', None)
    entries = list(inv.entries()) if inv and hasattr(inv, 'entries') else []
    lines: list[str] = []
    if not entries:
        lines.append('Inventory is empty.')
    else:
        lines.append('Current inventory:')
        for i, e in enumerate(entries, 1):
            name = getattr(e.item, 'name', '?')
            qty  = getattr(e, 'quantity', 1)
            lines.append(f'  {i:>2}. {name}' + (f' ×{qty}' if qty > 1 else ''))

    from commands.inv import _ally_inventory_lines
    ally_lines = _ally_inventory_lines(ctx.player)
    if ally_lines:
        lines.append('')
        lines.extend(ally_lines)

    await ctx.send(lines)


async def _transfer_item(ctx) -> None:
    """[T]ransfer: move an *existing* item out of ctx.player's own
    inventory into another recipient's -- an owned ally, the mount (if
    it has saddlebags), or any other character (online or offline,
    searched by name) via the same _pick_recipient()/_deliver_item()
    picker the give-flows use, rather than the name-only prompt this
    used to have. Distinct from _give_weapon()/_give_ration()/
    _give_object(), which grant a brand-new item from a catalog; this
    moves something the player already has. Checks the destination has
    room *before* removing anything from the source (via _deliver_item()'s
    return value), so a full/ineligible target can't strand the item in
    neither place. New in TADA, Ryan's request; ally/mount picker added
    per Ryan's follow-up request."""
    inv = getattr(ctx.player, 'inventory', None)
    entries = list(inv.entries()) if inv and hasattr(inv, 'entries') else []
    if not entries:
        await ctx.send('Inventory is empty -- nothing to transfer.')
        return

    await _show_inventory(ctx)
    raw = await ctx.prompt('Item #', preamble_lines=[f'Transfer which item # ({ctx.player.return_key} to cancel)'])
    if not raw or not raw.strip():
        return
    try:
        idx = int(raw.strip()) - 1
        if not (0 <= idx < len(entries)):
            raise ValueError
    except ValueError:
        await ctx.send('Invalid selection.')
        return
    entry = entries[idx]
    item = entry.item
    item_name = getattr(item, 'name', '?')

    recipient = await _pick_recipient(ctx)
    if recipient[0] == 'player':
        await ctx.send(f"{item_name} is already {ctx.player.name}'s.")
        return
    recipient_name = recipient[1].name

    confirm = await ctx.prompt(
        'Confirm',
        preamble_lines=[f'Transfer {item_name} to {recipient_name}? (y/N)'])
    if not confirm or confirm.strip().lower() != 'y':
        await ctx.send('Cancelled.')
        return

    # Check room at the destination *before* touching the source -- an
    # item removed here and rejected there would just vanish.
    delivered = await _deliver_item(ctx, item, recipient, item_name)
    if not delivered:
        return
    if not inv.remove(item):
        # Destination already has it added; undo rather than duplicate.
        await _undo_delivery(recipient, item)
        await ctx.send('Something went wrong removing the item -- transfer cancelled.')
        return

    ctx.player.unsaved_changes = True
    await ctx.send(f"Transferred {item_name} to {recipient_name}.")


async def _undo_delivery(recipient, item) -> None:
    """Roll back a successful _deliver_item() -- used by _transfer_item()
    in the (very unlikely) case the source removal itself fails after
    the destination add already succeeded."""
    kind = recipient[0]
    if kind == 'other':
        target_inv = getattr(recipient[1], 'inventory', None)
        if target_inv is not None:
            target_inv.remove(item)
    elif kind == 'ally':
        ally = recipient[1]
        if getattr(ally, 'items', None):
            ally.items = [e for e in ally.items if e.item is not item]


async def _drop_item(ctx) -> None:
    """[D]rop: delete an item from ctx.player's own inventory outright --
    for clearing out sysop test/mistake items without having to route
    them through [T]ransfer to nowhere. Confirms before removing since
    this is destructive and, unlike Transfer, unrecoverable from within
    this menu. New in TADA, Ryan's request."""
    inv = getattr(ctx.player, 'inventory', None)
    entries = list(inv.entries()) if inv and hasattr(inv, 'entries') else []
    if not entries:
        await ctx.send('Inventory is empty -- nothing to drop.')
        return

    await _show_inventory(ctx)
    raw = await ctx.prompt('Item #', preamble_lines=[f'Drop which item # ({ctx.player.return_key} to cancel)'])
    if not raw or not raw.strip():
        return
    try:
        idx = int(raw.strip()) - 1
        if not (0 <= idx < len(entries)):
            raise ValueError
    except ValueError:
        await ctx.send('Invalid selection.')
        return
    entry = entries[idx]
    item = entry.item
    item_name = getattr(item, 'name', '?')

    confirm = await ctx.prompt(
        'Confirm',
        preamble_lines=[f'Delete {item_name} from {ctx.player.name}? (y/N)'])
    if not confirm or confirm.strip().lower() != 'y':
        await ctx.send('Cancelled.')
        return

    if not inv.remove(item):
        await ctx.send('Something went wrong removing the item.')
        return
    ctx.player.unsaved_changes = True
    await ctx.send(f'Dropped {item_name}.')


async def _find_character(ctx, name: str):
    """Resolve *name* to a player character, online or offline.

    Checks ctx.server.clients first (case-insensitive, matching
    commands/messaging.py's find_online() convention); falls back to
    loading the character's save file directly if they're not currently
    connected. Returns (player, is_online), or None if no such
    character exists at all.

    The offline path checks the save file's existence *before*
    constructing a Player(id=name) -- Player.__init__ silently succeeds
    with a fresh, empty character if the id has no save file, which
    would otherwise make a typo'd name look like a real (if blank)
    character instead of "not found." New in TADA, Ryan's request to
    expand item-granting/[T]ransfer beyond "yourself or your own ally."
    """
    from pathlib import Path
    from player import Player

    lname = name.strip().lower()
    if not lname:
        return None

    for client in getattr(ctx.server, 'clients', {}).values():
        other_ctx = getattr(client, 'ctx', None)
        other_player = getattr(other_ctx, 'player', None)
        if other_player is not None and getattr(other_player, 'name', '').lower() == lname:
            return (other_player, True)

    if not Path(Player._json_path(name)).exists():
        return None
    return (Player(name=name, id=name,
                   weapons_data=getattr(ctx.server, 'weapons', None)), False)


async def _pick_recipient(ctx):
    """Let the admin choose who receives the next granted item: the
    player themself, one of their owned allies (bar.allies.
    owned_allies) -- including the mount, which needs AllyFlags.
    SADDLEBAGS before it can actually carry anything (see
    _deliver_item()) -- or any other character, online or offline,
    searched by name (_find_character()). Returns ('player', ctx.player),
    ('ally', ally), or ('other', player, is_online).

    Skips the ally/other-character prompt options when there's nothing
    to choose from, so this adds no extra step to the common case. New
    in TADA, Ryan's request."""
    from bar.allies import owned_allies

    allies = owned_allies(ctx.player)

    lines = ['', f'  0. {ctx.player.name} (yourself)']
    for i, a in enumerate(allies, 1):
        lines.append(f'  {i}. {a.name}')
    lines.append('  N. (search for another character by name)')
    lines.append('')
    await ctx.send(lines)

    raw = await ctx.prompt(preamble_lines=f'(0-{len(allies)}, N, {ctx.player.return_key} for yourself)',
                           prompt_text="Give to")
    if not raw or not raw.strip():
        return ('player', ctx.player)
    stripped = raw.strip()
    if stripped.lower() == 'n':
        name_raw = await ctx.prompt('Character name')
        if not name_raw or not name_raw.strip():
            await ctx.send('Cancelled -- giving to yourself instead.')
            return ('player', ctx.player)
        found = await _find_character(ctx, name_raw.strip())
        if found is None:
            await ctx.send(f'No character named "{name_raw.strip()}" -- giving to yourself instead.')
            return ('player', ctx.player)
        target_player, is_online = found
        return ('other', target_player, is_online)
    try:
        idx = int(stripped)
        if idx == 0:
            return ('player', ctx.player)
        if not (1 <= idx <= len(allies)):
            raise ValueError
    except ValueError:
        await ctx.send('Invalid selection -- giving to yourself instead.')
        return ('player', ctx.player)
    return ('ally', allies[idx - 1])


async def _deliver_item(ctx, item, recipient, item_name: str) -> bool:
    """Add *item* to *recipient* (from _pick_recipient()) -- the player's
    own Inventory, an ally's .items list (respecting mount carrying-
    capacity rules, commands/give.py's _mount_capacity()), or another
    character's Inventory entirely (online or offline -- an offline
    target has no live save-on-quit path, so it's saved immediately).
    Shared tail end of _give_weapon()/_give_ration()/_give_object(),
    replacing the three-times-duplicated "add straight to
    ctx.player.inventory" logic each had before EditPlayer's inventory
    menu could target allies/the mount/other characters. New in TADA,
    Ryan's request.

    Returns True if the item was actually added -- _transfer_item() uses
    this to decide whether it's safe to remove the item from its source,
    same "don't touch the source until the destination confirms room"
    ordering its own docstring already promises."""
    kind = recipient[0]

    if kind == 'player':
        inv = getattr(ctx.player, 'inventory', None)
        if inv is None:
            await ctx.send('Player has no inventory object.')
            return False
        if inv.add(item):
            ctx.player.unsaved_changes = True
            await ctx.send(f"Added {item_name} to {ctx.player.name}'s inventory.")
            return True
        await ctx.send('Inventory is full.')
        return False

    if kind == 'other':
        _, target_player, is_online = recipient
        inv = getattr(target_player, 'inventory', None)
        if inv is None:
            await ctx.send(f'{target_player.name} has no inventory object.')
            return False
        if not inv.add(item):
            await ctx.send(f"{target_player.name}'s inventory is full.")
            return False
        target_player.unsaved_changes = True
        if not is_online:
            target_player.save(force=True)
        await ctx.send(f"Added {item_name} to {target_player.name}'s inventory.")
        return True

    ally = recipient[1]
    from commands.give import _mount_capacity
    from bar.ally_data import add_ally_item, AllyFlags
    from commands.use import _SADDLEBAGS_ID

    if not hasattr(ally, 'items') or ally.items is None:
        ally.items = []

    # Saddlebags aren't carried, they're worn (same as commands/use.py's
    # USE saddlebags equip flow) -- transferring them straight to the
    # mount must equip the SADDLEBAGS flag rather than going through the
    # capacity check below, which would always reject them (a mount has
    # zero capacity *until* it has saddlebags). Ryan's bug report: this
    # previously said "has nowhere to carry it" when transferring
    # saddlebags to the horse itself.
    if getattr(item, 'id_number', None) == _SADDLEBAGS_ID:
        if AllyFlags.MOUNT not in (ally.flags or []):
            await ctx.send(f'{ally.name} has no back to strap them to -- saddlebags are for a mount.')
            return False
        if AllyFlags.SADDLEBAGS in (ally.flags or []):
            await ctx.send(f'{ally.name} already has saddlebags.')
            return False
        if ally.flags is None:
            ally.flags = []
        ally.flags.append(AllyFlags.SADDLEBAGS)
        ctx.player.unsaved_changes = True
        await ctx.send(f'Strapped the saddlebags onto {ally.name}.')
        return True

    capacity = _mount_capacity(ally)
    if capacity is not None:
        if capacity == 0:
            await ctx.send(f'{ally.name} has nowhere to carry it -- needs saddlebags first.')
            return False
        if len(ally.items) >= capacity:
            await ctx.send(f"{ally.name}'s saddlebags are full.")
            return False
    # add_ally_item(), not a raw ally.items.append(entry) -- stacks onto a
    # matching existing entry instead of always creating a new one (same
    # bug/fix as commands/give.py's ally branches: repeated grants of the
    # same item type were piling up as separate quantity-1 entries).
    add_ally_item(ally, item)
    ctx.player.unsaved_changes = True
    await ctx.send(f"Added {item_name} to {ally.name}'s pack.")
    return True


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
    """Search for a weapon by name and add it to the player's inventory,
    or an owned ally's pack (see _pick_recipient())."""
    weapons = getattr(ctx.server, 'weapons', []) or []
    if not weapons:
        await ctx.send('No weapon data loaded on server.')
        return

    while True:
        raw = await ctx.prompt(
            'Weapon name',
            preamble_lines=["Weapon name (or part of name, '?' to list all)"])
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

    recipient = await _pick_recipient(ctx)
    await _deliver_item(ctx, _weapon_from_dict(chosen), recipient, chosen['name'])


async def _give_ration(ctx) -> None:
    """Search for a ration by name and add it to the player's inventory,
    or an owned ally's pack (see _pick_recipient())."""
    from items import Rations
    rations = getattr(ctx.server, 'rations', []) or []
    if not rations:
        await ctx.send('No ration data loaded on server.')
        return

    def _label(r):
        return f'{r.get("name","?"):<24}  [{r.get("kind","?")}]'

    while True:
        raw = await ctx.prompt(
            'Ration name',
            preamble_lines=["Ration name (or part of name, blank = show all, '?' to list all)"])
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

    item = Rations(
        number = chosen.get('number', 0),
        name   = chosen.get('name', '?'),
        kind   = chosen.get('kind', 'food'),
        price  = chosen.get('price', 0),
    )
    recipient = await _pick_recipient(ctx)
    await _deliver_item(ctx, item, recipient, chosen['name'])


async def _give_object(ctx, type_filter: set, label: str) -> None:
    """Search objects.json for items matching type_filter and add to the
    player's inventory, or an owned ally's pack (see _pick_recipient()).

    Use this for any item category sourced from objects.json (server.items):
        armor/shield → _give_object(ctx, {'armor','shield'}, 'armor/shield')
        books        → _give_object(ctx, {'book'}, 'book')
        misc objects → _give_object(ctx, {'treasure','compass',...}, 'object')
    """
    from items import Item, ItemCategory
    from item_system import ItemType
    all_objects = getattr(ctx.server, 'items', []) or []
    pool = [o for o in all_objects if (o.get('type') or '').lower() in type_filter]
    if not pool:
        await ctx.send(f'No {label} data loaded on server.')
        return

    def _label(o):
        return f'{o.get("name","?"):<28}  [{o.get("type","?")}]'

    while True:
        raw = await ctx.prompt(
            f'{label.capitalize()} name',
            preamble_lines=[f"{label.capitalize()} name (or part of name, '?' to list all)"])
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

    item = Item(
        id_number = chosen.get('number', 0),
        name      = chosen.get('name', '?'),
        flags     = chosen.get('flags', {}),
        category  = ItemCategory.ITEM,
    )
    # Preserve objects.json's own "type" field (e.g. "book") as a real
    # ItemType -- read.py's book list keys off this (same fix as
    # commands/get.py's pickup path); without it an admin-granted book
    # would never show up as readable.
    raw_type = chosen.get('type')
    if raw_type:
        try:
            item.type = ItemType(raw_type)
        except ValueError:
            pass
    # Armor/shield need a starting condition (2026-08-08 durability
    # redesign) or WEAR/USE would divide by nothing meaningful -- a fresh
    # grant starts at 100, same as one bought at the armory.
    if getattr(item, 'type', None) in (ItemType.ARMOR, ItemType.SHIELD):
        item.condition = 100

    recipient = await _pick_recipient(ctx)
    await _deliver_item(ctx, item, recipient, chosen['name'])
