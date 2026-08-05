"""commands/use.py — USE: activate or apply an item from inventory.

Mirrors SPUR.USE.S. Supported item types:
  compass    — toggle compass on/off (session state)
  shield     — add to shield rating; class/race caps apply; item consumed
  ammunition — load rounds into readied weapon; item consumed
  power      — same as ammunition (energy-weapon charges)
  grenade    — hurl at monster; single-use explosive (SPUR.USE.S:91)
  tool kit   — repairs a broken spacesuit + spacesuit parts into a
               spacesuit, and/or a broken communicator into a
               communicator; not consumed (SPUR.USE.S 'tool' label)
  communicator — "beam aboard" to level 6 room 1; escalating malfunction
               risk breaks it back into a broken communicator and
               teleports somewhere random instead (SPUR.USE.S 'comm')
  book       — redirect to READ
  (other)    — "You play with the <name>.."

Not yet implemented (deferred — level 6 or requires unbuilt systems):
  rocket — single-use ranged explosive; needs rocket item type
  security cards — level-6 items
  ruby slippers / crystal vial / palintar — special room items

The ring of invisibility (#67) is handled by commands/wear.py instead --
SPUR toggles it via USE (SPUR.USE.S use4), but Ryan's call was that WEAR
reads better for a ring than USE does, so it moved there.
"""
from __future__ import annotations

import random
from typing import Optional

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from item_system import ItemType
from items import Item, ItemCategory
from network_context import GameContext
from tada_utilities import is_or_are

_GRENADE_ID     = 16    # hand grenade (objects.json)
_SADDLE_ID      = 162   # saddle (objects.json) -- Jake's Stable
_HORSE_ARMOR_ID = 163   # horse armour (objects.json) -- Jake's Stable
_SADDLEBAGS_ID  = 165   # saddlebags (objects.json) -- New in TADA, gives a
                        # mount carrying capacity (see commands/give.py)

# Tool kit (#133): repairs a broken spacesuit and/or a broken communicator
# (SPUR.USE.S's 'tool' label, ~lines 58-70). The tool kit itself is never
# consumed -- SPUR only clr.item's the broken parts and the repaired
# communicator's own broken predecessor, never 133 -- so it's reusable.
_TOOL_KIT_ID             = 133  # tool kit (objects.json)
_BROKEN_SPACESUIT_ID     = 134  # broken spacesuit (objects.json)
_SPACESUIT_PARTS_ID      = 135  # spacesuit parts (objects.json)
_SPACESUIT_ID            = 122  # spacesuit (objects.json) -- repair result
_BROKEN_COMMUNICATOR_ID  = 141  # broken communicator (objects.json)
_COMMUNICATOR_ID         = 66   # communicator (objects.json) -- repair result


def _char_level(player) -> int:
    """Character XP level (SPUR's xp/yn; separate from map_level, the dungeon floor)."""
    return int(getattr(player, 'xp_level', 1) or 1)

# SPUR.USE.S: max shield % by class/race (sh cap).
# cap_bonus is added for BATTLE SHIELD and LAZER SHIELD (a=20 in SPUR).
_CAP_LOW_CLASS  = {'Wizard'}               # 25 + bonus
_CAP_MID_CLASS  = {'Thief', 'Assassin'}    # 35 + bonus
_CAP_MID_RACE   = {'Pixie'}               # 35 + bonus
_CAP_HIGH_RACE  = {'Hobbit', 'Gnome'}     # 50 + bonus


def _shield_cap(player, cap_bonus: int) -> int:
    """Max shield rating for this player (SPUR.USE.S shield section)."""
    cls  = str(getattr(player, 'char_class', '') or '')
    race = str(getattr(player, 'char_race',  '') or '')
    if cls in _CAP_LOW_CLASS:
        return 25 + cap_bonus
    if cls in _CAP_MID_CLASS or race in _CAP_MID_RACE:
        return 35 + cap_bonus
    if race in _CAP_HIGH_RACE:
        return 50 + cap_bonus
    return 100 + cap_bonus


def is_ammo_item(flags) -> bool:
    """True if *flags* (an item's .flags) describe an ammo/power-pak item.

    Duck-typed on the flags shape (rounds + used_with) rather than
    item_system.Item.is_ammo_carrier -- items.Item (what shops actually
    construct) has no such property, just a flags dict/list. Shared by
    _apply_item() below and commands/give.py's ally-ammo path so both
    recognise the same items as ammo.
    """
    return isinstance(flags, dict) and 'rounds' in flags and 'used_with' in flags


def ammo_load_error(weapon, flags: dict) -> Optional[str]:
    """Validate loading ammo *flags* into an already-readied *weapon*.

    Returns a reason code ('storm' / 'wrong_weapon' / 'empty') if the load
    is invalid, or None if it's fine to proceed. Assumes weapon is not
    None -- callers check that themselves, since the "no weapon readied"
    message differs between this module's player-facing ALL-CAPS SPUR
    style and commands/give.py's sentence-case ally messages (CLAUDE.md:
    don't convert existing style, but don't spread ALL-CAPS to new text
    either). Shared so a weapon/ammo pairing is judged the same way
    whether reached via USE (player) or GIVE (ally) -- see give.py bug
    fixed 2026-08-01, where a duplicated copy of these same checks had
    drifted out of sync with this one.
    """
    wname_upper = (getattr(weapon, 'name', '') or '').upper()
    if 'STORM' in wname_upper:
        return 'storm'
    used_with = (flags.get('used_with') or '').strip().upper()
    if used_with and used_with not in wname_upper:
        return 'wrong_weapon'
    if 'capacity' in flags and int(flags.get('rounds', 0)) <= 0:
        return 'empty'
    return None


def _apply_item(item, player) -> list[str]:
    """Apply item effect to player; return message lines. Removes item from inventory on use.

    *item* is a real items.Item (the class every shop/inventory path actually
    constructs) -- NOT item_system.Item, a separate, unrelated dataclass this
    function used to require via an isinstance() gate at the call site. That
    gate meant every branch below was live only in tests that constructed
    item_system.Item objects directly; no shop-bought item could ever reach
    it (items.Item has no .type attribute at all, and isn't the same class),
    so USE-ing shop-bought ammo silently fell through to "You play with the
    X.." instead of loading rounds. Fixed by reading .type/.flags off
    whatever's actually there (getattr, not an isinstance gate) and having
    the ammo branch duck-type on the flags shape (rounds/used_with) instead
    of item_system.Item's is_ammo_carrier property.
    """
    inv   = getattr(player, 'inventory', None)
    itype = getattr(item, 'type', None)
    name  = getattr(item, 'name', 'it')
    flags = getattr(item, 'flags', None)

    # ---- Compass -----------------------------------------------------------
    if itype == ItemType.COMPASS:
        active = not getattr(player, 'compass_active', False)
        player.compass_active = active
        if active:
            return ['Compass used.', '(USE again to return to pack)']
        return ['Compass placed in pack.']

    # ---- Shield ------------------------------------------------------------
    if itype == ItemType.SHIELD:
        name_upper = name.upper()
        cap_bonus  = 20 if ('BATTLE' in name_upper or 'LAZER' in name_upper) else 0
        rating_add = getattr(item, 'price', 0) * 10 or 20   # proxy: price maps to ~20-80% rating
        cap        = _shield_cap(player, cap_bonus)
        current    = int(getattr(player, 'shield', 0) or 0)
        if current >= cap:
            return [f'(Max shield rating for you is {cap}%)']
        new_shield     = min(cap, current + rating_add)
        player.shield  = new_shield
        player.unsaved_changes = True
        if inv:
            inv.remove(item)
        msgs = []
        if 'BATTLE' in name_upper:
            msgs.append('THE BATTLE SHIELD GLOWS!')
        msgs.append(f'(New shield rating: {new_shield}%)')
        msgs.append(f'{name} used.')
        return msgs

    # ---- Ammo / power pak --------------------------------------------------
    if is_ammo_item(flags):
        weapon = getattr(player, 'readied_weapon', None)
        if weapon is None:
            return ['YOU MUST READY YOUR WEAPON FIRST!']
        wname_upper = (getattr(weapon, 'name', '') or '').upper()
        reason = ammo_load_error(weapon, flags)
        if reason == 'storm':
            return [f'THE {wname_upper} DOES NOT USE PHYSICAL AMMO!']
        if reason == 'wrong_weapon':
            return [f'THIS AMMO IS NOT FOR THE {wname_upper}!']
        if reason == 'empty':
            return [f'THE {name.upper()} {is_or_are(name).upper()} EMPTY!']

        # 'capacity' marks this as a reusable carrier (shoppe/ollys.py) --
        # it stays in inventory and empties into the weapon, rather than
        # being consumed like a single-use ammo box.
        is_carrier = 'capacity' in flags
        rounds = int((flags or {}).get('rounds', 0))
        damage = int((flags or {}).get('damage', 0))
        player.ammo_rounds = rounds
        player.ammo_damage = damage
        player.ammo_max    = rounds
        player.unsaved_changes = True
        if is_carrier:
            flags['rounds'] = 0
        elif inv:
            inv.remove(item)
        return [f'{rounds} ROUNDS NOW READY: +{damage} DAMAGE']

    # ---- Book --------------------------------------------------------------
    if itype == ItemType.BOOK:
        return [f'(Use the `read` command to read the {name}.)']

    # ---- Fallback ----------------------------------------------------------
    return [f'You play with the {name}..']


def _craft_item(ctx, inv, item_id: int) -> None:
    """Add the finished item *item_id* to *inv*, looking up its real name
    from ctx.server.items (objects.json) rather than hardcoding it, same
    as commands/get.py's own pickup path."""
    raw = next((it for it in (getattr(ctx.server, 'items', None) or [])
                if it.get('number') == item_id), None)
    name = raw.get('name') if raw else f'item {item_id}'
    inv.add(Item(id_number=item_id, name=name, category=ItemCategory.ITEM))


def _consume_one(inv, item_id: int) -> None:
    entries = inv.find(item_id=item_id)
    if entries:
        inv.remove(entries[0].item)


async def _use_tool_kit(ctx, player) -> list[str]:
    """SPUR.USE.S's 'tool' label (~lines 58-70): the tool kit can repair
    two independent things in one use, checked unconditionally (not
    mutually exclusive) --

      - A broken spacesuit (#134) + spacesuit parts (#135), together,
        become a spacesuit (#122). Having only one of the two prints a
        "don't have all the parts" line instead (SPUR's z==1 case);
        having neither says nothing about the spacesuit at all.
      - A broken communicator (#141) alone becomes a communicator (#66).

    If neither repair actually happens, "Playing with the tools does no
    good..".
    """
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return ["Playing with the tools does no good.."]

    lines = []
    repaired = False

    has_broken_suit = bool(inv.find(item_id=_BROKEN_SPACESUIT_ID))
    has_suit_parts  = bool(inv.find(item_id=_SPACESUIT_PARTS_ID))
    if has_broken_suit and has_suit_parts:
        lines.append('Bingo! Using the tools, you repair the spacesuit!')
        _consume_one(inv, _BROKEN_SPACESUIT_ID)
        _consume_one(inv, _SPACESUIT_PARTS_ID)
        _craft_item(ctx, inv, _SPACESUIT_ID)
        repaired = True
    elif has_broken_suit or has_suit_parts:
        lines.append("You don't have all the parts to the spacesuit.")

    if inv.find(item_id=_BROKEN_COMMUNICATOR_ID):
        _consume_one(inv, _BROKEN_COMMUNICATOR_ID)
        _craft_item(ctx, inv, _COMMUNICATOR_ID)
        lines.append('You repair the communicator!')
        repaired = True

    if not repaired:
        lines.append('Playing with the tools does no good..')

    player.unsaved_changes = True
    return lines


_COMM_ONCE_TOKEN = 'CM*'  # player.once_per_day token (SPUR's ys$ "CM*")
_TOTAL_LEVELS    = 7


async def _use_communicator(ctx, player) -> None:
    """SPUR.USE.S's comm label (~lines 128-140): "beam aboard" to level 6
    room 1, with an escalating malfunction risk. Traced from source, not
    invented -- see RoomFlag.NO_COMM_SIGNAL's own docstring in
    convert_from_gbbs_tool.py for the level-6-only "only static" gate.

    Malfunction chance: a flat ~1-in-10 (SPUR's `a=3` check against a
    1-10 roll) the *first* time the player reaches this point (even if
    they then cancel the confirm prompt below -- the once_per_day token
    is set unconditionally before the prompt, matching SPUR's own
    ys$=ys$+"CM*" placement). Every attempt *after* the first jumps to
    roughly 4-in-10 (an additional a<5 check) -- the device visibly gets
    less reliable the more you rely on it.
    """
    room_no = getattr(ctx.client, 'room', None)
    level   = int(getattr(player, 'map_level', 1) or 1)
    game_map = getattr(ctx.server, 'game_map', None)
    room = game_map.get_room(level, int(room_no)) if game_map and room_no else None
    if room and 'no_comm_signal' in (getattr(room, 'flags', None) or []):
        await ctx.send('You hear only static from the communicator..')
        return

    once = getattr(player, 'once_per_day', None)
    if once is None:
        once = []
        player.once_per_day = once
    threshold = 5 if _COMM_ONCE_TOKEN in once else 0
    roll = random.randint(1, 10)
    if roll < threshold or roll == 3:
        await _communicator_malfunction(ctx, player)
        return

    if _COMM_ONCE_TOKEN not in once:
        once.append(_COMM_ONCE_TOKEN)
        player.unsaved_changes = True

    await ctx.send('The device hums strangely!')
    raw = await ctx.prompt('Still want to use it? y/[N]')
    if not raw or raw.strip().lower() != 'y':
        return

    await ctx.send([
        'A tiny voice comes from the device!',
        "'Standby to beam aboard..'",
        'The area fades from view!!',
        'To be replaced by metal walls!',
    ])
    await ctx.server._teleport_to(ctx, 6, 1)


async def _communicator_malfunction(ctx, player) -> None:
    """SPUR.USE.S's malfunction label (~lines 221-232): the communicator
    breaks (swapped back to a broken communicator, #141 -- USE the tool
    kit again to fix it) and teleports the player to a random level and
    room instead of the intended level 6 room 1. SPUR's own ASCII
    "[] MALFUNCTION []" typewriter/erase animation (a C64-terminal-timing
    effect) isn't ported -- this codebase has no equivalent transport,
    and it carries no gameplay meaning to preserve."""
    inv = getattr(player, 'inventory', None)
    await ctx.send([
        'A strange buzzing comes from the communicator!!',
        'A red light starts flashing urgently!',
    ])
    if inv:
        _consume_one(inv, _COMMUNICATOR_ID)
        _craft_item(ctx, inv, _BROKEN_COMMUNICATOR_ID)
        player.unsaved_changes = True
    await ctx.send('*** MALFUNCTION ***')

    game_map = getattr(ctx.server, 'game_map', None)
    target_level = random.randint(1, _TOTAL_LEVELS)
    rooms = (game_map.levels.get(target_level, {}) if game_map else {}) or {}
    target_room = (random.choice(list(rooms.keys())) if rooms
                   else getattr(player, 'map_room', 1))
    await ctx.server._teleport_to(ctx, target_level, target_room)


def _usable_entries(player):
    """Return inventory entries that are not weapons (weapons use `ready`)."""
    inv = getattr(player, 'inventory', None)
    if inv is None:
        return []
    weapon_cat = str(ItemCategory.WEAPON)
    return [e for e in inv.entries() if str(getattr(e.item, 'category', '')) != weapon_cat]


class UseCommand(Command):
    name    = 'use'
    modes   = {Mode.GAME}

    help = Help(
        summary  = 'Use an item from your inventory.',
        category = HelpCategory.GENERAL,
        usage    = [
            ('use',          'List usable items and choose one'),
            ('use <name>',   'Use the item matching name'),
        ],
        examples = [
            ('use',          'Pick from item list'),
            ('use compass',  'Toggle compass'),
            ('use shield',   'Activate a shield'),
        ],
    )

    async def execute(self, ctx: GameContext, *args) -> CommandResult:
        args, _ = self.parse_args(*args)
        player  = ctx.player

        # ---- Fireplace: room feature detected via description (SPUR.USE.S:8,187) --
        # If the player types 'use fireplace' or is in a fireplace room and types 'use'
        # with no args, handle the fire before showing the item list.
        _use_fireplace = False
        if args and 'fireplace'.startswith(' '.join(args).lower()):
            _use_fireplace = True
        elif not args:
            room_no  = getattr(ctx.client, 'room', None)
            level    = int(getattr(ctx.player, 'map_level', 1) or 1)
            game_map = getattr(ctx.server, 'game_map', None)
            room     = game_map.get_room(level, int(room_no)) if game_map and room_no else None
            if room and 'fireplace' in (getattr(room, 'desc', '') or '').lower():
                _use_fireplace = True

        if _use_fireplace:
            pname = getattr(player, 'name', 'Someone')
            await ctx.send('You sit and warm yourself by the fire..')
            await ctx.send_room(f'{pname} sits by the fireplace.', exclude_self=True)
            stats = getattr(player, 'stats', None) or {}
            ps = int(stats.get('Strength', 10))
            if ps < 20:
                stats['Strength'] = 20
                player.stats = stats
                player.unsaved_changes = True
                await ctx.send('Feeling the strength return..')
                hp = int(getattr(player, 'hit_points', 1) or 1)
                if hp < 20:
                    player.hit_points = hp + 4
            return CommandResult.ok()

        entries = _usable_entries(player)

        if not entries:
            await ctx.send('You have nothing to use.')
            return CommandResult.ok()

        # Resolve by name arg or interactive prompt
        if args:
            pattern = ' '.join(args).lower()
            matches = [e for e in entries
                       if pattern in (getattr(e.item, 'name', '') or '').lower()]
            if not matches:
                await ctx.send(f'You are not carrying anything matching "{" ".join(args)}".')
                return CommandResult.ok()
            entry = matches[0]
        else:
            lines = ['', 'Items:']
            for i, e in enumerate(entries, 1):
                lines.append(f'  {i:>2}. {getattr(e.item, "name", "?")}')
            lines.append('')
            await ctx.send(lines)
            raw = await ctx.prompt(f'Use which item (1-{len(entries)}, Enter to cancel)')
            if not raw or not raw.strip():
                return CommandResult.ok()
            try:
                idx = int(raw.strip()) - 1
                if not (0 <= idx < len(entries)):
                    raise ValueError
            except ValueError:
                await ctx.send("You don't have that item.")
                return CommandResult.ok()
            entry = entries[idx]

        item    = entry.item
        item_no = getattr(item, 'number', None) or getattr(item, 'id_number', None)

        # ---- Grenade (#16): hurl at monster (SPUR.USE.S:91 grenade) ----------
        if item_no == _GRENADE_ID:
            inv = getattr(player, 'inventory', None)
            if inv:
                inv.remove(item)
            await ctx.send('You hurl the grenade!')
            room_no = getattr(ctx.client, 'room', None)
            session = (getattr(ctx.server, 'active_combats', {}) or {}).get(room_no)
            if session is None or session._done.is_set():
                await ctx.send('It explodes harmlessly.')
            else:
                from combat.engine import _monster_hp, _set_monster_hp
                await ctx.send('KABOOM!!')
                xp = _char_level(player)
                dmg = random.randint(1, 10) + 5 + (xp * 2)
                from monsters import monster_display_name
                mname = monster_display_name(session.monster, capitalize=True)
                await ctx.send(f'{mname} takes {dmg} damage..')
                new_hp = _monster_hp(session.monster) - dmg
                _set_monster_hp(session.monster, new_hp)
                if new_hp <= 0:
                    await session._monster_dies(ctx, player_killed=True)
            return CommandResult.ok()

        # ---- Tool kit (#133): repair a broken spacesuit and/or a broken
        # communicator (SPUR.USE.S 'tool' label) -- not consumed on use. ----
        if item_no == _TOOL_KIT_ID:
            for line in await _use_tool_kit(ctx, player):
                await ctx.send(line)
            return CommandResult.ok()

        # ---- Communicator (#66): beam aboard level 6, with an escalating
        # malfunction risk (SPUR.USE.S 'comm' label) ----------------------
        if item_no == _COMMUNICATOR_ID:
            await _use_communicator(ctx, player)
            return CommandResult.ok()

        # ---- Saddle (#162) / Horse Armor (#163) / Saddlebags (#165): equip
        # a mount ally ---- (SPUR.USE.S eq.horse; Saddlebags is New in
        # TADA, no SPUR precedent -- see AllyFlags.SADDLEBAGS's docstring)
        if item_no in (_SADDLE_ID, _HORSE_ARMOR_ID, _SADDLEBAGS_ID):
            from bar.ally_data import AllyFlags
            from bar.allies import owned_allies

            allies = owned_allies(player)
            mount = next((a for a in allies if AllyFlags.MOUNT in (a.flags or [])), None)
            if mount is None:
                await ctx.send('Need a mount first..')
                return CommandResult.ok()

            flag, label, verb = {
                _SADDLE_ID:      (AllyFlags.SADDLED,    'Saddle',      'put the {label} on'),
                _HORSE_ARMOR_ID: (AllyFlags.ARMORED,    'Horse Armor', 'put the {label} on'),
                _SADDLEBAGS_ID:  (AllyFlags.SADDLEBAGS, 'Saddlebags',  'strap the {label} onto'),
            }[item_no]
            if flag in (mount.flags or []):
                await ctx.send('Horse already has one.')
                return CommandResult.ok()

            if mount.flags is None:
                mount.flags = []
            mount.flags.append(flag)
            player.unsaved_changes = True
            inv = getattr(player, 'inventory', None)
            if inv:
                inv.remove(item)
            await ctx.send(f'You {verb.format(label=label)} the horse..')
            return CommandResult.ok()

        for line in _apply_item(item, player):
            await ctx.send(line)
        return CommandResult.ok()
