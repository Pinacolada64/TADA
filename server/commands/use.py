"""commands/use.py — USE: activate or apply an item from inventory.

Mirrors SPUR.USE.S. Supported item types:
  compass    — toggle compass on/off (session state)
  shield     — add to shield rating; class/race caps apply; item consumed
  ammunition — load rounds into readied weapon; item consumed
  power      — same as ammunition (energy-weapon charges)
  grenade    — hurl at monster; single-use explosive (SPUR.USE.S:91)
  ring       — ring of invisibility toggle; CON penalty when worn (SPUR.USE.S use4)
  book       — redirect to READ
  (other)    — "You play with the <name>.."

Not yet implemented (deferred — level 6 or requires unbuilt systems):
  rocket — single-use ranged explosive; needs rocket item type
  security cards — level-6 items
  spacesuit assembly, communicator repair — level-6 crafting
  slippers of Galad / crystal vial / palintar — special room items
"""
from __future__ import annotations

import random

from commands.base_command import Command, CommandResult, Mode
from commands.help import Help, HelpCategory
from item_system import Item, ItemType
from items import ItemCategory
from network_context import GameContext

_GRENADE_ID     = 16    # hand grenade (objects.json)
_RING_ID        = 67    # ring of invisibility (objects.json)
_SADDLE_ID      = 162   # saddle (objects.json) -- Jake's Stable
_HORSE_ARMOR_ID = 163   # horse armour (objects.json) -- Jake's Stable


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


def _apply_item(item: Item, player) -> list[str]:
    """Apply item effect to player; return message lines. Removes item from inventory on use."""
    inv   = getattr(player, 'inventory', None)
    itype = item.type
    name  = item.name

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
        rating_add = item.price * 10 or 20   # proxy: price maps to ~20-80% rating
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
    if item.is_ammo_carrier:
        weapon = getattr(player, 'readied_weapon', None)
        if weapon is None:
            return ['YOU MUST READY YOUR WEAPON FIRST!']
        wname_upper = (getattr(weapon, 'name', '') or '').upper()
        if 'STORM' in wname_upper:
            return [f'THE {wname_upper} DOES NOT USE PHYSICAL AMMO!']
        used_with = ((item.flags or {}).get('used_with') or '').strip().upper()
        if used_with and used_with not in wname_upper:
            return [f'THIS AMMO IS NOT FOR THE {wname_upper}!']
        rounds = int((item.flags or {}).get('rounds', 0))
        damage = int((item.flags or {}).get('damage', 0))
        player.ammo_rounds = rounds
        player.ammo_damage = damage
        player.ammo_max    = rounds
        player.unsaved_changes = True
        if inv:
            inv.remove(item)
        return [f'{rounds} ROUNDS NOW READY: +{damage} DAMAGE']

    # ---- Book --------------------------------------------------------------
    if itype == ItemType.BOOK:
        return [f'(Use the `read` command to read the {name}.)']

    # ---- Fallback ----------------------------------------------------------
    return [f'You play with the {name}..']


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
            game_map = getattr(ctx.server, 'game_map', None)
            room     = game_map.rooms.get(int(room_no)) if game_map and room_no else None
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
                mname = session.monster.get('name', 'the monster')
                await ctx.send(f'{mname} takes {dmg} damage..')
                new_hp = _monster_hp(session.monster) - dmg
                _set_monster_hp(session.monster, new_hp)
                if new_hp <= 0:
                    await session._monster_dies(ctx, player_killed=True)
            return CommandResult.ok()

        # ---- Ring of invisibility (#67): toggle worn (SPUR.USE.S use4) -------
        if item_no == _RING_ID:
            worn = getattr(player, 'ring_worn', False)
            if not worn:
                player.ring_worn = True
                player.unsaved_changes = True
                await ctx.send('Ring worn!  You are hard to see!')
                await ctx.send('(USE again to remove)')
                await ctx.send('THE EVIL SENSES YOU MORE CLEARLY!')
                stats = getattr(player, 'stats', None) or {}
                pt = int(stats.get('Constitution', 10))
                if pt > 5:
                    stats['Constitution'] = pt - 2
                    player.stats = stats
                    await ctx.send('(You feel a bit less healthy!)')
            else:
                player.ring_worn = False
                player.unsaved_changes = True
                await ctx.send('Ring returned to your pack.')
            return CommandResult.ok()

        # ---- Saddle (#162) / Horse Armor (#163): equip a mount ally ----------
        # (SPUR.USE.S eq.horse)
        if item_no in (_SADDLE_ID, _HORSE_ARMOR_ID):
            from bar.ally_data import AllyFlags
            from bar.allies import owned_allies

            allies = owned_allies(player)
            mount = next((a for a in allies if AllyFlags.MOUNT in (a.flags or [])), None)
            if mount is None:
                await ctx.send('Need a mount first..')
                return CommandResult.ok()

            flag  = AllyFlags.SADDLED if item_no == _SADDLE_ID else AllyFlags.ARMORED
            label = 'Saddle' if item_no == _SADDLE_ID else 'Horse Armor'
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
            await ctx.send(f'You put the {label} on the horse..')
            return CommandResult.ok()

        if not isinstance(item, Item):
            await ctx.send(f'You play with the {getattr(item, "name", "it")}..')
            return CommandResult.ok()

        for line in _apply_item(item, player):
            await ctx.send(line)
        return CommandResult.ok()
